"""Guided-speaking and strict pronunciation scoring endpoints."""

from __future__ import annotations

import asyncio
import os
import tempfile

import numpy as np
import soundfile as sf
from fastapi import File, Form, HTTPException, UploadFile

from speakflow.features.language_tools.infrastructure.tts import (
    _remove_temporary_file,
)
from speakflow.features.learning_plan.application import (
    pronunciation_assignment_service,
)
from speakflow.features.learning_plan.engine.schemas import ActivityAttemptInput
from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
)
from speakflow.features.pronunciation.domain import (
    annotate_phone_verification,
    assess_pronunciation_evidence,
    learner_attention_evidence,
    phone_status_summary,
)
from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    PronunciationScoringError,
    calculate_overall_score,
    normalized_english_words,
)
from speakflow.runtime import models as runtime

from .pronunciation_audio import (
    _apply_sentence_word_alignment,
    _decode_wav_16k,
    _read_upload_limited,
    _single_word_acoustically_contradicted,
    _single_word_transcript_is_one_attempt,
    _single_word_transcript_relation,
    _speech_activity,
    _transcribe_practice_audio,
)
from .pronunciation_text import (
    get_pronunciation_coaching,
    local_pronunciation_coaching,
    normalize_pronunciation_text,
)


async def transcribe_guided_speaking(file: UploadFile = File(...)) -> dict:
    content = await _read_upload_limited(file, 15 * 1024 * 1024)
    if not content:
        raise HTTPException(status_code=400, detail="audio file is empty")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(content)
        path = temp_audio.name
    try:
        try:
            audio_array, _ = await asyncio.to_thread(_decode_wav_16k, path)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="could not decode the WAV recording",
            ) from exc
        if not np.isfinite(audio_array).all():
            raise HTTPException(
                status_code=400, detail="audio contains invalid samples"
            )
        duration_seconds = len(audio_array) / 16000.0
        if duration_seconds < 1:
            raise HTTPException(
                status_code=422,
                detail="Speak for at least one second before stopping.",
            )
        if duration_seconds > 120:
            raise HTTPException(
                status_code=422,
                detail="Guided speaking recordings must be two minutes or shorter.",
            )
        activity = await asyncio.to_thread(_speech_activity, audio_array, 16000)
        if not activity["has_speech"]:
            raise HTTPException(status_code=422, detail="No clear speech was detected.")
        if runtime.whisper_model is None and not await asyncio.to_thread(
            runtime._load_whisper_models
        ):
            raise HTTPException(
                status_code=503,
                detail="Local speech recognition is unavailable.",
            )
        transcript, confidence, error = await asyncio.to_thread(
            _transcribe_practice_audio,
            audio_array,
        )
        if error:
            raise HTTPException(
                status_code=503,
                detail="Local speech recognition failed.",
            )
        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="No intelligible English speech was recognized.",
            )
        return {
            "transcript": transcript,
            "duration_seconds": round(duration_seconds, 2),
            "confidence": confidence,
        }
    finally:
        _remove_temporary_file(path)


async def check_pronunciation(
    target_word: str = Form(..., min_length=1, max_length=120),
    file: UploadFile = File(...),
    activity_id: str | None = Form(
        default=None,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    ),
    attempt_session_id: str | None = Form(
        default=None,
        min_length=8,
        max_length=80,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    ),
    submission_id: str | None = Form(
        default=None,
        min_length=8,
        max_length=180,
        pattern=r"^[a-zA-Z0-9_\-:.]+$",
    ),
    timezone_offset_minutes: int = Form(default=0, ge=-720, le=840),
):
    # FastAPI injects strings over HTTP, while direct unit-test calls retain
    # the ``Form`` marker defaults. Only real, non-empty strings opt into PLP
    # grading; the standalone Practice tab must remain target-only.
    activity_id = activity_id.strip() if isinstance(activity_id, str) else None
    attempt_session_id = (
        attempt_session_id.strip() if isinstance(attempt_session_id, str) else None
    )
    submission_id = submission_id.strip() if isinstance(submission_id, str) else None
    timezone_offset_minutes = (
        timezone_offset_minutes if isinstance(timezone_offset_minutes, int) else 0
    )
    target_word = target_word.strip()
    if not normalize_pronunciation_text(target_word):
        raise HTTPException(status_code=400, detail="target_word must not be empty")
    if len(target_word) > 120:
        raise HTTPException(status_code=400, detail="target_word is too long")
    if activity_id:
        try:
            target_word = await asyncio.to_thread(
                pronunciation_assignment_service.validate_target,
                activity_id,
                target_word,
            )
        except PlpNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PlpInvalidAttemptError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PlpUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    content = await _read_upload_limited(file, 15 * 1024 * 1024)
    if not content:
        raise HTTPException(status_code=400, detail="audio file is empty")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(content)
        temp_audio_path = temp_audio.name

    try:
        try:
            audio_array, sample_rate = await asyncio.to_thread(
                _decode_wav_16k,
                temp_audio_path,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="could not decode the WAV recording",
            ) from exc

        audio_array = np.asarray(audio_array, dtype=np.float32)
        if not np.isfinite(audio_array).all():
            raise HTTPException(
                status_code=400, detail="audio contains non-finite samples"
            )
        peak = float(np.max(np.abs(audio_array))) if len(audio_array) else 0.0
        clipped_fraction = (
            float(np.mean(np.abs(audio_array) >= 0.999)) if len(audio_array) else 0.0
        )
        if clipped_fraction >= 0.05:
            raise HTTPException(
                status_code=422,
                detail="The recording is heavily clipped. Move away from the microphone and try again.",
            )
        dc_offset = float(np.mean(audio_array)) if len(audio_array) else 0.0
        audio_array = np.asarray(audio_array - dc_offset, dtype=np.float32)
        duration_seconds = len(audio_array) / 16000.0
        audio_rms = (
            float(np.sqrt(np.mean(np.square(audio_array)))) if len(audio_array) else 0.0
        )
        if duration_seconds < 0.15 or audio_rms < 0.001:
            raise HTTPException(
                status_code=422,
                detail="No clear speech was detected. Move closer to the microphone and try again.",
            )
        if duration_seconds > 30:
            raise HTTPException(
                status_code=422,
                detail="Practice recordings must be 30 seconds or shorter.",
            )
        speech_activity = await asyncio.to_thread(_speech_activity, audio_array)
        if not speech_activity["has_speech"]:
            raise HTTPException(
                status_code=422,
                detail="No speech was detected. Say the target clearly before stopping the recording.",
            )

        target_word_count = len(normalized_english_words(target_word))
        # WebRTC can mistake harmonic phone/microphone hum for speech. Require
        # WhisperX's independent
        # pyannote speech detector/decoder to find intelligible speech before
        # allowing the pronunciation model to score any recording, including a single word.
        if runtime.whisper_model is None and not await asyncio.to_thread(
            runtime._load_whisper_models
        ):
            raise HTTPException(
                status_code=503,
                detail="Local WhisperX is required to validate Practice speech but is not loaded.",
            )
        spoken_text, whisper_confidence, transcription_error = await asyncio.to_thread(
            _transcribe_practice_audio, audio_array
        )
        if transcription_error:
            print(f"Local Practice speech validation failed: {transcription_error}")
            raise HTTPException(
                status_code=503,
                detail="Local Practice speech validation failed.",
            )
        if not spoken_text:
            raise HTTPException(
                status_code=422,
                detail="No intelligible speech was recognized. Say the target clearly before stopping the recording.",
            )
        if not await asyncio.to_thread(runtime._load_pronunciation_scorer):
            raise HTTPException(
                status_code=503,
                detail=(
                    "The local CTC pronunciation scorer is not available. "
                    "Check the backend log."
                ),
            )
        if target_word_count == 1 and not _single_word_transcript_is_one_attempt(
            spoken_text
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f'Please say only the target word "{target_word}" and try again.'
                ),
            )
        transcript_relation = (
            _single_word_transcript_relation(target_word, spoken_text)
            if target_word_count == 1
            else None
        )
        single_word_gate_match = (
            target_word_count != 1 or transcript_relation != "mismatch"
        )

        # Give the selected acoustic model predictable 16 kHz mono PCM, independent of the
        # format produced by the phone's recorder.
        await asyncio.to_thread(
            sf.write,
            temp_audio_path,
            audio_array,
            16000,
            subtype="PCM_16",
        )
        try:
            result = await asyncio.to_thread(
                runtime.pronunciation_scorer.score, temp_audio_path, target_word
            )
        except PronunciationScoringError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            print(f"Unexpected production pronunciation scoring error: {exc}")
            raise HTTPException(
                status_code=503,
                detail="The local pronunciation engine failed. Check the backend log for details.",
            ) from exc

        if (
            target_word_count == 1
            and not single_word_gate_match
            and _single_word_acoustically_contradicted(result)
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "The target word could not be verified from this recording. "
                    f'Please say only "{target_word}" and try again.'
                ),
            )

        completeness_note = ""
        result["spoken"] = spoken_text
        result["whisper_confidence"] = whisper_confidence
        result["asr_gate_match"] = single_word_gate_match
        transcript_exact_match = tuple(normalized_english_words(target_word)) == tuple(
            normalized_english_words(spoken_text)
        )
        result["transcript_exact_match"] = transcript_exact_match
        if target_word_count == 1 and transcript_relation not in {
            "exact",
            "phonetic_compatible",
        }:
            result.setdefault("warnings", []).append(
                "The local recognizer did not verify the target transcript. "
                "Acoustic phone evidence is shown for guidance, but this "
                "attempt cannot count as mastery."
            )
        if target_word_count >= 2:
            _apply_sentence_word_alignment(result, target_word, spoken_text)
            result["scores"]["overall_score"] = calculate_overall_score(
                result["scores"]
            )
            if result["scores"]["completeness"] < 90:
                omitted = result.get("omitted_words") or []
                omission_detail = (
                    " Likely omitted: " + ", ".join(omitted) + "." if omitted else ""
                )
                completeness_note = (
                    "Some target words may be missing. The local recognizer heard: "
                    f'"{spoken_text}".{omission_detail} '
                )
                result["feedback"] = completeness_note + result["feedback"]

        transcript_verified = (
            transcript_relation in {"exact", "phonetic_compatible"}
            if target_word_count == 1
            else result["scores"]["completeness"] >= 90
        )
        if target_word_count >= 2:
            transcript_relation = (
                "exact"
                if transcript_exact_match
                else "compatible"
                if transcript_verified
                else "incomplete"
            )
        result["transcript_relation"] = transcript_relation
        result["transcript_verified"] = transcript_verified
        result["assessment"] = assess_pronunciation_evidence(
            analysis=result.get("analysis"),
            completeness=result["scores"]["completeness"],
            transcript_verified=transcript_verified,
        )
        result["analysis"] = annotate_phone_verification(
            result.get("analysis"),
            transcript_verified=transcript_verified,
            transcript_contradicted=(
                target_word_count == 1
                and transcript_relation in {"near_match", "mismatch"}
            ),
        )
        attention_evidence = learner_attention_evidence(result["analysis"])
        result["phone_summaries"] = {
            "acoustic": phone_status_summary(
                result["analysis"], status_key="acoustic_status"
            ),
            "learner_facing": phone_status_summary(
                result["analysis"], status_key="display_status"
            ),
        }
        result["learner_attention_phones"] = attention_evidence
        verified_corrections = [
            item
            for item in attention_evidence
            if item.get("verification_reason")
            == "transcript_and_phone_identity_contradict"
        ]
        if verified_corrections:
            descriptions = []
            for item in verified_corrections[:3]:
                expected = item.get("char") or "?"
                alternative = item.get("closest_ipa") or item.get("likely_arpabet")
                descriptions.append(f"/{expected}/ sounded closer to /{alternative}/")
            result["feedback"] = (
                "The word and phone recognizers agree on this correction: "
                + "; ".join(descriptions)
                + ". Try the target again."
            )
            result["feedback_source"] = "local_cross_model_correction"
            result["feedback_kind"] = "correction"
        elif attention_evidence:
            confirmed_errors = [
                item
                for item in attention_evidence
                if item.get("display_status") == "incorrect"
            ]
            coaching_error = None
            if confirmed_errors:
                coaching, coaching_error, coaching_source = await asyncio.to_thread(
                    get_pronunciation_coaching,
                    target_word,
                    confirmed_errors,
                )
            else:
                coaching, coaching_source = None, None
            coaching = coaching or local_pronunciation_coaching(attention_evidence)
            if coaching:
                result["feedback"] = completeness_note + coaching
            result["feedback_source"] = coaching_source or (
                "local_acoustic_correction"
                if confirmed_errors
                else "local_acoustic_guidance"
            )
            result["feedback_kind"] = (
                "correction" if confirmed_errors else "guidance"
            )
            if coaching_error:
                result.setdefault("warnings", []).append(
                    "AI pronunciation coaching was unavailable; showing local acoustic feedback."
                )
        elif result["assessment"]["passed"] is True:
            if result["assessment"]["acoustic_uncertain_phone_count"]:
                result["feedback"] = (
                    "Target verified by transcript and phone identity. The acoustic "
                    "quality estimate remains advisory."
                )
                result["feedback_source"] = "local_conservative_assessment"
            else:
                result["feedback_source"] = "local_acoustic_summary"
            result["feedback_kind"] = "verified"
        else:
            result["feedback_source"] = "local_acoustic_summary"
            result["feedback_kind"] = "assessment"

        result["audio"] = {
            "duration_seconds": round(duration_seconds, 3),
            "rms": round(audio_rms, 5),
            "peak": round(peak, 5),
            "clipped_fraction": round(clipped_fraction, 5),
            "dc_offset": round(dc_offset, 6),
            **speech_activity,
        }
        if activity_id:
            try:
                lesson_attempt = await asyncio.to_thread(
                    pronunciation_assignment_service.record_attempt,
                    activity_id,
                    ActivityAttemptInput(
                        attempt_kind="initial",
                        attempt_session_id=attempt_session_id,
                        submission_id=submission_id,
                        transcript=spoken_text,
                        duration_seconds=duration_seconds,
                        timezone_offset_minutes=timezone_offset_minutes,
                    ),
                    trusted_pronunciation={
                        "target": target_word,
                        "accuracy": result["scores"]["accuracy"],
                        "completeness": result["scores"]["completeness"],
                        "transcript_verified": transcript_verified,
                        "analysis": result.get("analysis", []),
                    },
                )
            except PlpNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PlpConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except PlpInvalidAttemptError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except PlpUnavailableError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            result["lesson_attempt"] = lesson_attempt.model_dump(mode="json")
            if lesson_attempt.pronunciation_mastery_verified is True:
                result["feedback"] = (
                    "The assigned sound was verified. Other acoustic quality "
                    "estimates are advisory for this focused sound check."
                )
                result["feedback_source"] = "local_focused_assessment"
                result["feedback_kind"] = "verified"
        return result
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
