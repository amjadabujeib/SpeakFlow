"""Speech delivery metrics and chat-audio transcription helpers."""

from __future__ import annotations

import math

import librosa
import numpy as np
from gector import predict as gector_predict

from . import models as runtime
from .language import _normalize_display_text


def _chat_delivery_metrics(
    audio_array: np.ndarray,
    speech_activity: dict,
    aligned_words: list[dict],
) -> tuple[int | None, int | None]:
    """Estimate free-speech fluency and pitch variation without a target text.

    These are intentionally separate from Practice's target-dependent acoustic/GOPT
    scores. A chat utterance has no canonical sentence to force-align against.
    """
    duration = len(audio_array) / 16000.0
    voiced_duration = float(speech_activity.get("voiced_duration_seconds", 0.0))
    if duration < 0.3 or voiced_duration <= 0:
        return None, None

    fluency = None
    timed_words = []
    for item in aligned_words:
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
            or end > duration + 0.25
        ):
            continue
        timed_words.append({**item, "start": start, "end": end})
    timed_words.sort(key=lambda item: (item["start"], item["end"]))
    if len(timed_words) >= 2:
        speech_ratio = voiced_duration / max(duration, 0.1)
        continuity_score = float(
            np.interp(speech_ratio, [0.2, 0.55, 0.85], [35, 78, 100])
        )
        words_per_second = len(timed_words) / max(voiced_duration, 0.1)
        rate_score = float(
            np.interp(
                words_per_second,
                [0.5, 1.4, 3.2, 5.0],
                [40, 85, 100, 65],
            )
        )
        long_pauses = sum(
            1
            for previous, current in zip(timed_words, timed_words[1:])
            if float(current["start"]) - float(previous["end"]) > 0.55
        )
        pause_penalty = min(25, long_pauses * 7)
        fluency = int(
            np.clip(round(continuity_score * 0.45 + rate_score * 0.55 - pause_penalty), 0, 100)
        )

    prosody = None
    try:
        f0, _, _ = librosa.pyin(
            audio_array.astype(float),
            sr=16000,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
        )
        valid_f0 = f0[np.isfinite(f0)] if f0 is not None else np.array([])
        if len(valid_f0) >= 5:
            median_f0 = float(np.median(valid_f0))
            semitones = 12.0 * np.log2(valid_f0 / max(median_f0, 1e-6))
            pitch_spread = float(np.std(semitones))
            prosody = int(
                np.clip(
                    round(
                        np.interp(
                            pitch_spread,
                            [0.25, 1.2, 4.5, 9.0, 15.0],
                            [40, 68, 100, 88, 65],
                        )
                    ),
                    0,
                    100,
                )
            )
    except Exception as exc:
        print(f"Chat pitch-variation estimate failed: {exc}")

    return fluency, prosody


def _chat_word_feedback(word: dict) -> dict:
    """Serialize a WhisperX word without inventing missing confidence."""
    raw_score = word.get("score")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None or not math.isfinite(score) or not 0.0 <= score <= 1.0:
        score = None
    else:
        score = round(score, 2)

    def timestamp(name: str) -> float | None:
        raw_value = word.get(name)
        try:
            value = float(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            return None
        return value if value is not None and math.isfinite(value) and value >= 0 else None

    start = timestamp("start")
    end = timestamp("end")
    if start is None or end is None or end <= start:
        start = end = None

    return {
        "word": str(word.get("word", "")),
        "score": score,
        "start": start,
        "end": end,
    }


def _transcribe_chat_audio(audio_path: str) -> tuple[str, list[dict]]:
    audio_for_whisper = runtime.whisperx.load_audio(audio_path)
    result = runtime.whisper_model.transcribe(audio_for_whisper, batch_size=16)
    aligned = runtime.whisperx.align(
        result["segments"],
        runtime.align_model,
        runtime.align_metadata,
        audio_for_whisper,
        runtime.device,
        return_char_alignments=False,
    )
    text = "".join(segment["text"] for segment in aligned["segments"]).strip()
    words = [
        _chat_word_feedback(word)
        for segment in aligned["segments"]
        for word in segment.get("words", [])
    ]
    return text, words


def _correct_chat_grammar(user_text: str) -> str | None:
    corrected_list = gector_predict(
        runtime.gector_model,
        runtime.gector_tokenizer,
        [user_text],
        runtime.gector_encode,
        runtime.gector_decode,
        keep_confidence=0.0,
        min_error_prob=0.0,
        n_iteration=5,
        batch_size=2,
    )
    if not corrected_list or not corrected_list[0]:
        return None
    corrected = _normalize_display_text(corrected_list[0])
    return corrected if corrected != user_text else None
