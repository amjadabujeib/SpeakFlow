"""Shared feature builders for compact Arabic-L1 pronunciation models.

The training and runtime paths import these functions directly so a model
cannot silently receive a different feature ordering after deployment.
"""

from __future__ import annotations

import re
from typing import Sequence

import numpy as np


GOP_FEATURE_DIM = 84
PHONE_CLASS_COUNT = 40  # Padding plus the 39 canonical GOPT phones.
PURE_PHONE_COUNT = 39
PHONE_CONTEXT_FEATURE_DIM = 385
WORD_CONTEXT_FEATURE_DIM = 542


def _stress_index(phone: str) -> int:
    match = re.search(r"([012])$", str(phone).upper())
    return 0 if match is None else int(match.group(1)) + 1


def _word_layout(word_lengths: Sequence[int], phone_count: int) -> tuple[np.ndarray, ...]:
    lengths = tuple(int(value) for value in word_lengths)
    if not lengths or any(value <= 0 for value in lengths):
        raise ValueError("word lengths must contain positive values")
    if sum(lengths) != phone_count:
        raise ValueError(
            f"word lengths cover {sum(lengths)} phones, expected {phone_count}"
        )

    word_index = np.empty(phone_count, dtype=np.int64)
    phone_in_word = np.empty(phone_count, dtype=np.int64)
    word_length = np.empty(phone_count, dtype=np.int64)
    offset = 0
    for index, length in enumerate(lengths):
        word_index[offset : offset + length] = index
        phone_in_word[offset : offset + length] = np.arange(length)
        word_length[offset : offset + length] = length
        offset += length
    return word_index, phone_in_word, word_length


def build_phone_context_features(
    raw_gop: np.ndarray,
    phone_ids: Sequence[int],
    canonical_phones: Sequence[str],
    word_lengths: Sequence[int],
    *,
    normalization_mean: float,
    normalization_std: float,
) -> np.ndarray:
    """Build one context-aware feature row per canonical phone."""
    raw = np.asarray(raw_gop, dtype=np.float32)
    ids = np.asarray(phone_ids, dtype=np.int64)
    phones = tuple(str(value).upper() for value in canonical_phones)
    if raw.ndim != 2 or raw.shape[1] != GOP_FEATURE_DIM:
        raise ValueError(f"GOP features must have shape N x {GOP_FEATURE_DIM}")
    count = raw.shape[0]
    if ids.shape != (count,) or len(phones) != count:
        raise ValueError("phone ids, symbols, and GOP rows must have equal length")
    if not np.isfinite(raw).all():
        raise ValueError("GOP features contain non-finite values")
    if not np.isfinite(normalization_mean) or not np.isfinite(normalization_std):
        raise ValueError("normalization values must be finite")
    if normalization_std <= 0:
        raise ValueError("normalization standard deviation must be positive")
    if np.any(ids < 0) or np.any(ids >= PURE_PHONE_COUNT):
        raise ValueError("canonical phone id is outside the supported table")

    word_index, phone_in_word, word_length = _word_layout(word_lengths, count)
    normalized = (raw - normalization_mean) / normalization_std

    previous = np.zeros_like(normalized)
    following = np.zeros_like(normalized)
    if count > 1:
        previous[1:] = normalized[:-1]
        following[:-1] = normalized[1:]

    padded_ids = ids + 1
    previous_ids = np.zeros(count, dtype=np.int64)
    following_ids = np.zeros(count, dtype=np.int64)
    if count > 1:
        previous_ids[1:] = padded_ids[:-1]
        following_ids[:-1] = padded_ids[1:]
    current_one_hot = np.eye(PHONE_CLASS_COUNT, dtype=np.float32)[padded_ids]
    previous_one_hot = np.eye(PHONE_CLASS_COUNT, dtype=np.float32)[previous_ids]
    following_one_hot = np.eye(PHONE_CLASS_COUNT, dtype=np.float32)[following_ids]

    stress = np.eye(4, dtype=np.float32)[
        np.asarray([_stress_index(phone) for phone in phones], dtype=np.int64)
    ]
    utterance_position = np.arange(count, dtype=np.float32)[:, None] / max(1, count - 1)
    utterance_length = np.full(
        (count, 1), min(count, 50) / 50.0, dtype=np.float32
    )
    word_position = word_index.astype(np.float32)[:, None] / max(1, len(word_lengths) - 1)
    within_word_position = phone_in_word.astype(np.float32)[:, None] / np.maximum(
        1, word_length - 1
    )[:, None]
    normalized_word_length = np.minimum(word_length, 15).astype(np.float32)[:, None] / 15.0
    boundary = np.zeros((count, 4), dtype=np.float32)
    for index, (position, length) in enumerate(zip(phone_in_word, word_length)):
        if length == 1:
            boundary[index, 3] = 1.0  # Single-phone word.
        elif position == 0:
            boundary[index, 0] = 1.0  # Beginning.
        elif position == length - 1:
            boundary[index, 2] = 1.0  # End.
        else:
            boundary[index, 1] = 1.0  # Interior.

    features = np.concatenate(
        (
            normalized,
            previous,
            following,
            current_one_hot,
            previous_one_hot,
            following_one_hot,
            stress,
            utterance_position,
            utterance_length,
            word_position,
            within_word_position,
            normalized_word_length,
            boundary,
        ),
        axis=1,
    ).astype(np.float32, copy=False)
    if features.shape != (count, PHONE_CONTEXT_FEATURE_DIM):
        raise AssertionError(f"unexpected phone feature shape: {features.shape}")
    if not np.isfinite(features).all():
        raise ValueError("phone context features contain non-finite values")
    return features


def build_word_context_features(
    raw_gop: np.ndarray,
    phone_ids: Sequence[int],
    word_lengths: Sequence[int],
    *,
    normalization_mean: float,
    normalization_std: float,
) -> np.ndarray:
    """Aggregate canonical-phone GOP evidence into one row per target word."""
    raw = np.asarray(raw_gop, dtype=np.float32)
    ids = np.asarray(phone_ids, dtype=np.int64)
    if raw.ndim != 2 or raw.shape[1] != GOP_FEATURE_DIM:
        raise ValueError(f"GOP features must have shape N x {GOP_FEATURE_DIM}")
    count = raw.shape[0]
    if ids.shape != (count,):
        raise ValueError("phone ids and GOP rows must have equal length")
    if np.any(ids < 0) or np.any(ids >= PURE_PHONE_COUNT):
        raise ValueError("canonical phone id is outside the supported table")
    if not np.isfinite(normalization_mean) or not np.isfinite(normalization_std):
        raise ValueError("normalization values must be finite")
    if normalization_std <= 0:
        raise ValueError("normalization standard deviation must be positive")
    _word_layout(word_lengths, count)
    normalized = (raw - normalization_mean) / normalization_std
    if not np.isfinite(normalized).all():
        raise ValueError("normalized GOP features contain non-finite values")

    rows: list[np.ndarray] = []
    offset = 0
    word_count = len(word_lengths)
    pure_phone_eye = np.eye(PURE_PHONE_COUNT, dtype=np.float32)
    padded_phone_eye = np.eye(PHONE_CLASS_COUNT, dtype=np.float32)
    for word_index, raw_length in enumerate(word_lengths):
        length = int(raw_length)
        segment = normalized[offset : offset + length]
        segment_ids = ids[offset : offset + length]
        deltas = np.diff(segment, axis=0)
        mean_delta = (
            np.mean(np.abs(deltas), axis=0)
            if len(deltas)
            else np.zeros(GOP_FEATURE_DIM, dtype=np.float32)
        )
        phone_composition = np.mean(pure_phone_eye[segment_ids], axis=0)
        first_phone = padded_phone_eye[segment_ids[0] + 1]
        last_phone = padded_phone_eye[segment_ids[-1] + 1]
        structural = np.asarray(
            [
                min(length, 15) / 15.0,
                word_index / max(1, word_count - 1),
                min(count, 50) / 50.0,
            ],
            dtype=np.float32,
        )
        rows.append(
            np.concatenate(
                (
                    np.mean(segment, axis=0),
                    np.std(segment, axis=0),
                    np.min(segment, axis=0),
                    np.max(segment, axis=0),
                    mean_delta,
                    phone_composition,
                    first_phone,
                    last_phone,
                    structural,
                )
            )
        )
        offset += length

    features = np.stack(rows).astype(np.float32, copy=False)
    if features.shape != (len(word_lengths), WORD_CONTEXT_FEATURE_DIM):
        raise AssertionError(f"unexpected word feature shape: {features.shape}")
    if not np.isfinite(features).all():
        raise ValueError("word context features contain non-finite values")
    return features
