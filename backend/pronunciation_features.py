"""Shared feature builders for compact Arabic-L1 pronunciation models.

The training and runtime paths import these functions directly so a model
cannot silently receive a different feature ordering after deployment.
"""

from __future__ import annotations

import re
from typing import Sequence

import numpy as np

from ctc_gop import CTC_CLASS_COUNT, CTC_PHONE_TO_ID


GOP_FEATURE_DIM = 41
PHONE_CLASS_COUNT = 40  # Padding plus the 39 canonical GOPT phones.
PURE_PHONE_COUNT = 39
CTC_DERIVED_SCALAR_DIM = 8
XGB_ACOUSTIC_FEATURE_DIM = (
    GOP_FEATURE_DIM + CTC_DERIVED_SCALAR_DIM + CTC_CLASS_COUNT
)
PHONE_CONTEXT_FEATURE_DIM = (
    (3 * XGB_ACOUSTIC_FEATURE_DIM) + (3 * PHONE_CLASS_COUNT) + 13
)
WORD_CONTEXT_FEATURE_DIM = (
    (5 * XGB_ACOUSTIC_FEATURE_DIM)
    + PURE_PHONE_COUNT
    + (2 * PHONE_CLASS_COUNT)
    + 3
)


def normalize_gop_features(
    raw_gop: np.ndarray,
    normalization_mean: float | Sequence[float],
    normalization_std: float | Sequence[float],
) -> np.ndarray:
    """Apply a scalar or feature-wise training normalization contract."""
    raw = np.asarray(raw_gop, dtype=np.float32)
    mean = np.asarray(normalization_mean, dtype=np.float32)
    std = np.asarray(normalization_std, dtype=np.float32)
    if mean.ndim > 1 or std.ndim > 1:
        raise ValueError("normalization values must be scalars or vectors")
    if mean.ndim == 1 and mean.shape != (GOP_FEATURE_DIM,):
        raise ValueError(
            f"normalization mean must contain {GOP_FEATURE_DIM} values"
        )
    if std.ndim == 1 and std.shape != (GOP_FEATURE_DIM,):
        raise ValueError(
            f"normalization standard deviation must contain {GOP_FEATURE_DIM} values"
        )
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise ValueError("normalization values must be finite")
    if np.any(std <= 0):
        raise ValueError("normalization standard deviation must be positive")
    normalized = (raw - mean) / std
    if not np.isfinite(normalized).all():
        raise ValueError("normalized GOP features contain non-finite values")
    return normalized.astype(np.float32, copy=False)


def build_ctc_evidence_features(
    raw_gop: np.ndarray,
    canonical_phones: Sequence[str],
    *,
    normalization_mean: float | Sequence[float],
    normalization_std: float | Sequence[float],
) -> np.ndarray:
    """Expose target-relative CTC evidence to compact tree models.

    The 41 published alignment-free values remain first. Derived fields avoid
    asking a shallow tree to discover an argmin, softmax, and target exclusion
    across all 40 counterfactual hypotheses.
    """
    raw = np.asarray(raw_gop, dtype=np.float32)
    phones = tuple(re.sub(r"[012]$", "", str(phone).upper()) for phone in canonical_phones)
    if raw.ndim != 2 or raw.shape[1] != GOP_FEATURE_DIM:
        raise ValueError(f"GOP features must have shape N x {GOP_FEATURE_DIM}")
    if raw.shape[0] != len(phones):
        raise ValueError("canonical phones and GOP rows must have equal length")
    try:
        canonical_ids = np.asarray(
            [CTC_PHONE_TO_ID[phone] for phone in phones],
            dtype=np.int64,
        )
    except KeyError as exc:
        raise ValueError(f"unsupported canonical phone: {exc.args[0]}") from exc

    normalized = normalize_gop_features(
        raw,
        normalization_mean,
        normalization_std,
    )
    ratios = raw[:, 1:].astype(np.float64)
    hypothesis_logits = -ratios
    hypothesis_logits -= np.max(hypothesis_logits, axis=1, keepdims=True)
    hypothesis_probability = np.exp(hypothesis_logits)
    hypothesis_probability /= np.sum(
        hypothesis_probability,
        axis=1,
        keepdims=True,
    )
    alternative_mask = np.ones_like(ratios, dtype=bool)
    alternative_mask[np.arange(len(raw)), canonical_ids] = False
    alternative_ratios = np.where(alternative_mask, ratios, np.inf)
    sorted_alternatives = np.sort(alternative_ratios, axis=1)
    best_alternative_id = np.argmin(alternative_ratios, axis=1)
    best_hypothesis_id = np.argmax(hypothesis_probability, axis=1)
    entropy = -np.sum(
        hypothesis_probability
        * np.log(np.clip(hypothesis_probability, 1e-12, 1.0)),
        axis=1,
    ) / np.log(CTC_CLASS_COUNT)
    canonical_probability = hypothesis_probability[
        np.arange(len(raw)),
        canonical_ids,
    ]
    best_alternative_probability = hypothesis_probability[
        np.arange(len(raw)),
        best_alternative_id,
    ]
    derived = np.column_stack(
        (
            ratios[:, 0],
            sorted_alternatives[:, 0],
            -sorted_alternatives[:, 0],
            sorted_alternatives[:, 1],
            canonical_probability,
            hypothesis_probability[:, 0],
            best_alternative_probability,
            entropy,
        )
    ).astype(np.float32)
    best_one_hot = np.eye(CTC_CLASS_COUNT, dtype=np.float32)[
        best_hypothesis_id
    ]
    features = np.concatenate(
        (normalized, derived, best_one_hot),
        axis=1,
    ).astype(np.float32, copy=False)
    if features.shape != (len(raw), XGB_ACOUSTIC_FEATURE_DIM):
        raise AssertionError(f"unexpected CTC evidence shape: {features.shape}")
    if not np.isfinite(features).all():
        raise ValueError("CTC evidence features contain non-finite values")
    return features


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
    normalization_mean: float | Sequence[float],
    normalization_std: float | Sequence[float],
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
    if np.any(ids < 0) or np.any(ids >= PURE_PHONE_COUNT):
        raise ValueError("canonical phone id is outside the supported table")

    word_index, phone_in_word, word_length = _word_layout(word_lengths, count)
    acoustic = build_ctc_evidence_features(
        raw,
        phones,
        normalization_mean=normalization_mean,
        normalization_std=normalization_std,
    )

    previous = np.zeros_like(acoustic)
    following = np.zeros_like(acoustic)
    if count > 1:
        previous[1:] = acoustic[:-1]
        following[:-1] = acoustic[1:]

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
            acoustic,
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
    canonical_phones: Sequence[str],
    word_lengths: Sequence[int],
    *,
    normalization_mean: float | Sequence[float],
    normalization_std: float | Sequence[float],
) -> np.ndarray:
    """Aggregate canonical-phone GOP evidence into one row per target word."""
    raw = np.asarray(raw_gop, dtype=np.float32)
    ids = np.asarray(phone_ids, dtype=np.int64)
    phones = tuple(str(value).upper() for value in canonical_phones)
    if raw.ndim != 2 or raw.shape[1] != GOP_FEATURE_DIM:
        raise ValueError(f"GOP features must have shape N x {GOP_FEATURE_DIM}")
    count = raw.shape[0]
    if ids.shape != (count,) or len(phones) != count:
        raise ValueError("phone ids, symbols, and GOP rows must have equal length")
    if np.any(ids < 0) or np.any(ids >= PURE_PHONE_COUNT):
        raise ValueError("canonical phone id is outside the supported table")
    _word_layout(word_lengths, count)
    normalized = build_ctc_evidence_features(
        raw,
        phones,
        normalization_mean=normalization_mean,
        normalization_std=normalization_std,
    )

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
            else np.zeros(XGB_ACOUSTIC_FEATURE_DIM, dtype=np.float32)
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
