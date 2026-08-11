"""Speech activity, alignment, and transcript scoring helpers."""

from __future__ import annotations

import difflib
import math
import re

import librosa
import numpy as np
import soundfile as sf
import webrtcvad
from fastapi import HTTPException, UploadFile

from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    PronunciationScoringError,
    normalized_english_words,
)
from speakflow.runtime import models as runtime

from .pronunciation_text import normalize_pronunciation_text


def _decode_wav_16k(path: str) -> tuple[np.ndarray, int]:
    audio_array, sample_rate = sf.read(path, dtype="float32")
    if audio_array.ndim > 1:
        audio_array = audio_array.mean(axis=1)
    if not isinstance(sample_rate, (int, np.integer)) or sample_rate <= 0:
        raise ValueError("invalid audio sample rate")
    if sample_rate != 16000:
        audio_array = librosa.resample(
            np.asarray(audio_array, dtype=np.float32),
            orig_sr=int(sample_rate),
            target_sr=16000,
            res_type="soxr_hq",
        )
    return np.asarray(audio_array, dtype=np.float32), 16000


def _transcribe_practice_audio(audio_array):
    if runtime.whisper_model is None and not runtime._load_whisper_models():
        return "", 0.0, "WhisperX is not loaded."

    try:
        result = runtime.whisper_model.transcribe(
            audio_array,
            batch_size=4 if runtime.device == "cpu" else 16,
        )
        segments = result.get("segments", [])
        text = " ".join(
            segment.get("text", "").strip()
            for segment in segments
            if segment.get("text", "").strip()
        )
        confidence = 0.0
        if segments:
            durations = [
                max(0.01, float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)))
                for segment in segments
            ]
            avg_logprob = float(np.average(
                [float(segment.get("avg_logprob", -5.0)) for segment in segments],
                weights=durations,
            ))
            confidence = float(np.clip(math.exp(avg_logprob) * 100, 0, 100))
        return normalize_pronunciation_text(text), round(confidence, 1), None
    except Exception as exc:
        print(f"Practice transcription failed: {exc}")
        return "", 0.0, str(exc)


def _speech_activity(audio_array: np.ndarray, sample_rate: int = 16000) -> dict:
    """Return conservative WebRTC speech-presence diagnostics.

    Noise can still produce overconfident acoustic posteriors. This gate must
    pass before any pronunciation score is allowed.
    """
    if sample_rate != 16000:
        raise ValueError("speech activity detection requires 16 kHz audio")
    audio = np.asarray(audio_array, dtype=np.float32)
    frame_samples = 480  # 30 ms, one of WebRTC VAD's supported frame sizes.
    frame_count = len(audio) // frame_samples
    if frame_count == 0:
        return {
            "has_speech": False,
            "voiced_frames": 0,
            "total_frames": 0,
            "voiced_duration_seconds": 0.0,
            "longest_voiced_run_seconds": 0.0,
        }

    pcm = np.clip(audio, -1.0, 1.0)
    pcm = np.rint(pcm * 32767.0).astype("<i2", copy=False)
    vad = webrtcvad.Vad(2)
    voiced = []
    voiced_rms = []
    voiced_flatness = []
    voiced_concentration = []
    voiced_entropy = []
    voiced_flux = []
    previous_spectrum = None
    for frame_index in range(frame_count):
        start = frame_index * frame_samples
        end = start + frame_samples
        is_speech = bool(vad.is_speech(pcm[start:end].tobytes(), sample_rate))
        voiced.append(is_speech)
        if is_speech:
            frame = audio[start:end]
            voiced_rms.append(float(np.sqrt(np.mean(np.square(frame)))))
            windowed = frame * np.hanning(frame_samples)
            power = np.square(np.abs(np.fft.rfft(windowed))) + 1e-12
            speech_band = power[3:-10]
            flatness = float(
                np.exp(np.mean(np.log(speech_band))) / max(float(np.mean(speech_band)), 1e-12)
            )
            voiced_flatness.append(flatness)
            normalized_spectrum = speech_band / max(float(np.sum(speech_band)), 1e-12)
            voiced_concentration.append(float(np.max(normalized_spectrum)))
            voiced_entropy.append(float(
                -np.sum(normalized_spectrum * np.log(normalized_spectrum))
                / np.log(len(normalized_spectrum))
            ))
            if previous_spectrum is not None:
                denominator = float(
                    np.linalg.norm(normalized_spectrum) * np.linalg.norm(previous_spectrum)
                )
                if denominator > 0:
                    voiced_flux.append(float(
                        1.0 - np.dot(normalized_spectrum, previous_spectrum) / denominator
                    ))
            previous_spectrum = normalized_spectrum

    longest_run = current_run = 0
    for is_speech in voiced:
        current_run = current_run + 1 if is_speech else 0
        longest_run = max(longest_run, current_run)
    voiced_frames = sum(voiced)
    # Require at least 120 ms total and 60 ms continuously voiced. The energy
    # check rejects tiny microphone/codec artifacts that WebRTC occasionally
    # labels as speech while remaining permissive for quiet real speakers.
    # A stationary electronic tone can fool both WebRTC and an ASR decoder
    # (for example, Whisper may literally transcribe it as "beep"). Speech has
    # moving formants and a broader spectrum; reject highly concentrated,
    # low-entropy audio whose spectrum is effectively unchanged over time.
    stationary_tone = (
        len(voiced_concentration) >= 4
        and bool(voiced_flux)
        and float(np.median(voiced_concentration)) >= 0.55
        and float(np.median(voiced_entropy)) <= 0.25
        and float(np.median(voiced_flux)) <= 0.01
    )
    has_speech = (
        voiced_frames >= 4
        and longest_run >= 2
        and bool(voiced_rms)
        and max(voiced_rms) >= 0.003
        and sum(value < 0.35 for value in voiced_flatness) >= 2
        and not stationary_tone
    )
    return {
        "has_speech": has_speech,
        "voiced_frames": voiced_frames,
        "total_frames": frame_count,
        "voiced_duration_seconds": round(voiced_frames * 0.03, 3),
        "longest_voiced_run_seconds": round(longest_run * 0.03, 3),
        "harmonic_voiced_frames": sum(value < 0.35 for value in voiced_flatness),
        "stationary_tone": stationary_tone,
    }


def _word_match_similarity(
    expected: str,
    candidate: str,
    phone_cache: dict[str, tuple[str, ...] | None] | None = None,
) -> float:
    """Compare ASR words with spelling and the same local Practice G2P."""
    if expected == candidate:
        return 1.0
    orthographic = difflib.SequenceMatcher(None, expected, candidate).ratio()
    canonicalizer = getattr(runtime.pronunciation_scorer, "canonicalizer", None)
    if canonicalizer is None:
        return orthographic

    cache = phone_cache if phone_cache is not None else {}

    def phones(word: str) -> tuple[str, ...] | None:
        if word not in cache:
            try:
                cache[word] = canonicalizer.canonicalize(word).pure_phones
            except PronunciationScoringError:
                cache[word] = None
        return cache[word]

    try:
        expected_phones = phones(expected)
        candidate_phones = phones(candidate)
        if expected_phones is None or candidate_phones is None:
            return orthographic
        phonetic = difflib.SequenceMatcher(
            None, expected_phones, candidate_phones
        ).ratio()
    except PronunciationScoringError:
        phonetic = 0.0
    return max(orthographic, phonetic)


def _sentence_word_alignment(target: str, spoken: str) -> dict:
    """Monotonically align ASR words and report evidence for each target word."""
    target_words = normalized_english_words(target)
    spoken_words = normalized_english_words(spoken)
    if not target_words or not spoken_words:
        return {
            "score": 0,
            "target_words": target_words,
            "spoken_words": spoken_words,
            "matches": tuple(None for _ in target_words),
            "similarities": tuple(0.0 for _ in target_words),
        }

    phone_cache: dict[str, tuple[str, ...] | None] = {}
    similarities = np.asarray(
        [
            [
                _word_match_similarity(expected, candidate, phone_cache)
                for candidate in spoken_words
            ]
            for expected in target_words
        ],
        dtype=np.float64,
    )

    def credit(similarity: float) -> float:
        if similarity >= 0.85:
            return 1.0
        if similarity >= 0.65:
            return 0.90
        if similarity >= 0.55:
            return 0.75
        return 0.0

    rows, columns = len(target_words), len(spoken_words)
    values = np.zeros((rows + 1, columns + 1), dtype=np.float64)
    choices = np.zeros((rows + 1, columns + 1), dtype=np.int8)
    # 1 skips a target, 2 skips a spoken word, 3 matches the pair.
    for row in range(1, rows + 1):
        choices[row, 0] = 1
    for column in range(1, columns + 1):
        choices[0, column] = 2
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            options = [
                (values[row - 1, column], 1),
                (values[row, column - 1], 2),
            ]
            match_credit = credit(float(similarities[row - 1, column - 1]))
            if match_credit:
                # Prefer a real match over a skip when totals tie.
                options.append((values[row - 1, column - 1] + match_credit + 1e-9, 3))
            best_value, best_choice = max(options, key=lambda item: item[0])
            values[row, column] = best_value
            choices[row, column] = best_choice

    matches: list[int | None] = [None] * rows
    matched_similarities = [0.0] * rows
    row, column = rows, columns
    while row or column:
        choice = int(choices[row, column])
        if choice == 3:
            matches[row - 1] = column - 1
            matched_similarities[row - 1] = float(similarities[row - 1, column - 1])
            row -= 1
            column -= 1
        elif choice == 1:
            row -= 1
        elif choice == 2:
            column -= 1
        else:
            break

    total_credit = sum(credit(value) for value in matched_similarities)
    return {
        "score": int(np.clip(round(100 * total_credit / rows), 0, 100)),
        "target_words": target_words,
        "spoken_words": spoken_words,
        "matches": tuple(matches),
        "similarities": tuple(matched_similarities),
    }


def _sentence_completeness(target: str, spoken: str) -> int:
    """Use local ASR to estimate which requested sentence words were present."""
    return int(_sentence_word_alignment(target, spoken)["score"])


def _apply_sentence_word_alignment(result: dict, target: str, spoken: str) -> dict:
    """Keep omitted words out of pronunciation colors and acoustic accuracy."""
    alignment = _sentence_word_alignment(target, spoken)
    result["scores"]["completeness"] = alignment["score"]
    word_scores = result.get("word_scores") or []
    analysis = result.get("analysis") or []
    if len(word_scores) != len(alignment["target_words"]):
        return alignment

    omitted_phone_indices: set[int] = set()
    present_scores: list[float] = []
    present_weights: list[int] = []
    omitted_words: list[str] = []
    for index, (word_score, spoken_index, similarity) in enumerate(
        zip(word_scores, alignment["matches"], alignment["similarities"])
    ):
        word_score["asr_similarity"] = round(float(similarity), 3)
        if spoken_index is not None:
            word_score["spoken_word"] = alignment["spoken_words"][spoken_index]
            word_score["omitted"] = False
            if isinstance(word_score.get("accuracy"), (int, float)):
                start = int(word_score.get("phone_start", 0))
                end = int(word_score.get("phone_end", start + 1))
                present_scores.append(float(word_score["accuracy"]))
                present_weights.append(max(1, end - start))
            continue

        word_score["spoken_word"] = None
        word_score["omitted"] = True
        omitted_words.append(str(word_score.get("word", alignment["target_words"][index])))
        start = int(word_score.get("phone_start", -1))
        end = int(word_score.get("phone_end", -1))
        if start < 0 or end <= start or end > len(analysis):
            continue
        for phone_index in range(start, end):
            omitted_phone_indices.add(phone_index)
            item = analysis[phone_index]
            item["acoustic_score_before_omission"] = item.get("score")
            item["status"] = "omitted"
            item["score"] = None
            item["correct_probability"] = None
            item["error_probability"] = None
            item["severe_error_probability"] = None
            item["error_severity"] = None

    if present_scores:
        result["scores"]["accuracy"] = int(
            np.clip(round(np.average(present_scores, weights=present_weights)), 0, 100)
        )
    elif omitted_words:
        result["scores"]["accuracy"] = 0

    result["omitted_words"] = omitted_words
    if omitted_phone_indices:
        result["acoustic_flagged_phones"] = [
            item
            for item in (result.get("acoustic_flagged_phones") or [])
            if item.get("phone_index") not in omitted_phone_indices
        ]
    return alignment


def _single_word_transcript_matches(target: str, spoken: str) -> bool:
    """Reject unrelated utterances without making ASR the phone scorer.

    Orthographic fuzziness preserves common accent/ASR variants such as
    ``car`` -> ``caw``. A local G2P comparison also preserves differently
    spelled homophones such as ``two`` -> ``too``.
    """
    return _single_word_transcript_relation(target, spoken) != "mismatch"


def _single_word_transcript_relation(target: str, spoken: str) -> str:
    """Classify exact, homophonic, fuzzy-near, and unrelated transcripts."""
    target_words = normalized_english_words(target)
    spoken_words = normalized_english_words(spoken)
    if len(target_words) != 1 or not spoken_words:
        return "mismatch"

    expected = target_words[0]
    candidates = list(spoken_words)
    if len(candidates) == 2:
        fillers = {"a", "the", "uh", "um", "hmm"}
        candidates = [
            candidate
            for candidate in candidates
            if candidate == expected or candidate not in fillers
        ]
    # A target word appearing somewhere in a longer sentence is not a valid
    # one-word attempt; otherwise a short target can match only one fragment of
    # a longer recording and return an inflated score.
    if len(candidates) != 1:
        return "mismatch"
    candidate = candidates[0]
    if expected == candidate:
        return "exact"

    canonicalizer = getattr(runtime.pronunciation_scorer, "canonicalizer", None)
    if canonicalizer is not None:
        try:
            if (
                canonicalizer.canonicalize(expected).pure_phones
                == canonicalizer.canonicalize(candidate).pure_phones
            ):
                return "phonetic_compatible"
        except PronunciationScoringError:
            pass
    return (
        "near_match"
        if _word_match_similarity(expected, candidate) >= 0.55
        else "mismatch"
    )


def _single_word_transcript_is_one_attempt(spoken: str) -> bool:
    """Allow one decoded word plus at most one ordinary hesitation filler."""
    words = list(normalized_english_words(spoken))
    if len(words) == 2:
        fillers = {"a", "the", "uh", "um", "hmm"}
        words = [word for word in words if word not in fillers]
    return len(words) == 1


def _single_word_acoustically_contradicted(result: dict) -> bool:
    """Return true only when CTC confidently contradicts every target phone.

    Incomplete/test results without CTC counterfactual phone evidence cannot
    independently justify rejecting an intelligible single-word attempt.
    """
    analysis = result.get("analysis")
    if not isinstance(analysis, list) or not analysis:
        return False
    calibration = result.get("calibration") or {}
    try:
        confidence_threshold = float(
            calibration.get("substitution_confidence_threshold", 20.0)
        )
    except (TypeError, ValueError):
        confidence_threshold = 20.0
    if confidence_threshold <= 1.0:
        confidence_threshold *= 100.0

    for item in analysis:
        if not isinstance(item, dict):
            return False
        expected = re.sub(r"\d+$", "", str(item.get("arpabet", "")).upper())
        if not expected:
            return False
        likely_value = item.get("likely_arpabet")
        likely = (
            re.sub(r"\d+$", "", str(likely_value).upper())
            if likely_value is not None
            else None
        )
        if likely == expected:
            return False
        try:
            likely_confidence = float(item.get("likely_phone_probability", 0.0))
            deletion_confidence = float(item.get("deletion_probability", 0.0))
        except (TypeError, ValueError):
            return False
        if max(likely_confidence, deletion_confidence) <= confidence_threshold:
            return False
    return True


async def _read_upload_limited(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(min(1024 * 1024, limit + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="audio file is too large")
        chunks.append(chunk)
    return b"".join(chunks)
