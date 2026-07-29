"""Train compact context-aware Arabic-L1 CTC-GOP pronunciation models.

Evaluation is leave-one-speaker-out.  Every reported prediction therefore
comes from a model that did not train on that speaker.  Clean/noisy copies are
kept in the same fold and receive half weight so augmentation does not double
the effective annotation count.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

from ctc_gop import CTC_PHONE_TO_ID
from pronunciation_features import (
    GOP_FEATURE_DIM,
    PHONE_CONTEXT_FEATURE_DIM,
    WORD_CONTEXT_FEATURE_DIM,
    XGB_ACOUSTIC_FEATURE_DIM,
    build_ctc_evidence_features,
    build_phone_context_features,
    build_word_context_features,
)
from pronunciation_core import GOPT_PHONE_TO_ID
from training.pronunciation_data import DEFAULT_ARABIC_DATASET, load_examples


RED_PHONE_THRESHOLD_SHRINKAGE = 0.75
QUALITY_SEVERITY_REGRESSOR_WEIGHT = 0.50
CTC_XGB_NORM_MEAN = 0.0
CTC_XGB_NORM_STD = 1.0
LEGACY_PHONE_FEATURE_DIM = XGB_ACOUSTIC_FEATURE_DIM + 40 + 2
SUBSTITUTION_MINIMUM_PRECISION = 0.60
SUBSTITUTION_MINIMUM_PREDICTIONS = 20


@dataclass(frozen=True)
class PhoneData:
    features: np.ndarray
    legacy_features: np.ndarray
    error: np.ndarray
    severity: np.ndarray
    phone_ids: np.ndarray
    word_keys: np.ndarray
    utterance_ids: np.ndarray
    speakers: np.ndarray
    variants: np.ndarray


@dataclass(frozen=True)
class WordData:
    features: np.ndarray
    severity: np.ndarray
    phone_counts: np.ndarray
    word_keys: np.ndarray
    utterance_ids: np.ndarray
    utterance_severity: np.ndarray
    speakers: np.ndarray
    variants: np.ndarray


def _speaker(utterance_id: str) -> str:
    return utterance_id.split("_", 1)[0]


def _safe_logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probability, dtype=np.float64), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1.0 - clipped))


def _sigmoid(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(value, dtype=np.float64), -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _correlation(truth: np.ndarray, prediction: np.ndarray) -> float:
    if len(truth) < 2 or np.std(truth) == 0 or np.std(prediction) == 0:
        return 0.0
    return float(np.corrcoef(truth, prediction)[0, 1])


def _classification_metrics(labels: np.ndarray, probability: np.ndarray, threshold: float) -> dict:
    predicted = probability >= threshold
    true_positive = int(np.sum(predicted & (labels == 1)))
    precision = true_positive / max(1, int(np.sum(predicted)))
    recall = true_positive / max(1, int(np.sum(labels == 1)))
    return {
        "average_precision": float(average_precision_score(labels, probability)),
        "roc_auc": float(roc_auc_score(labels, probability)),
        "precision": precision,
        "recall": recall,
        "f1": 2.0 * precision * recall / max(1e-12, precision + recall),
        "brier": float(np.mean((probability - labels) ** 2)),
        "predicted_positive": int(np.sum(predicted)),
        "actual_positive": int(np.sum(labels)),
    }


def _regression_metrics(truth: np.ndarray, prediction: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(truth, prediction)),
        "pcc": _correlation(truth, prediction),
        "mean_truth": float(np.mean(truth)),
        "mean_prediction": float(np.mean(prediction)),
    }


def _error_model(seed: int) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=700,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.82,
        colsample_bytree=0.72,
        min_child_weight=7,
        reg_lambda=8.0,
        reg_alpha=0.2,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=8,
        random_state=seed,
    )


def _severity_model(seed: int) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=650,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.82,
        colsample_bytree=0.72,
        min_child_weight=7,
        reg_lambda=9.0,
        reg_alpha=0.2,
        objective="reg:squarederror",
        tree_method="hist",
        n_jobs=8,
        random_state=seed,
    )


def _severe_error_model(seed: int) -> XGBClassifier:
    """Detect clearly wrong/deleted phones for the learner-facing red tier."""
    return XGBClassifier(
        n_estimators=700,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.82,
        colsample_bytree=0.72,
        min_child_weight=7,
        reg_lambda=8.0,
        reg_alpha=0.2,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=8,
        random_state=seed,
    )


def _word_model(seed: int) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=750,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.82,
        colsample_bytree=0.70,
        min_child_weight=5,
        reg_lambda=10.0,
        reg_alpha=0.25,
        objective="reg:squarederror",
        tree_method="hist",
        n_jobs=8,
        random_state=seed,
    )


def _legacy_error_model(seed: int) -> XGBClassifier:
    """Train the compact current-phone baseline for a fair LOSO comparison."""
    return XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=5,
        reg_lambda=5.0,
        reg_alpha=0.1,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=8,
        random_state=seed,
    )


def _variant_weight(variants: np.ndarray) -> np.ndarray:
    # Clean and deterministic noisy copies represent the same human labels.
    return np.full(len(variants), 0.5, dtype=np.float32)


def _diagnosis_arrays(
    root: Path,
    rows: list[dict],
    *,
    speakers: set[str] | None = None,
    feature_root: Path | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    predictions: list[int] = []
    confidence: list[float] = []
    realized: list[int] = []
    canonical: list[int] = []
    diagnosis_root = (
        feature_root or (root / "ctc_gop_output")
    ) / "diagnosis"
    for row in rows:
        if row["variant"] != "clean":
            continue
        if speakers is not None and row["speaker"] not in speakers:
            continue
        with np.load(
            diagnosis_root / f"{row['id']}.npz",
            allow_pickle=False,
        ) as diagnosis:
            predicted = diagnosis["likely_phone_ids"].astype(np.int64)
            probability = diagnosis[
                "likely_phone_probabilities"
            ].astype(np.float64)
        expected_count = len(row["pure_phones"])
        if predicted.shape != (expected_count,) or probability.shape != (
            expected_count,
        ):
            raise ValueError(f"{row['id']}: diagnosis shape is malformed")
        realized_ids = np.asarray(
            [
                0 if phone is None else CTC_PHONE_TO_ID[phone]
                for phone in row["realized_phones"]
            ],
            dtype=np.int64,
        )
        predictions.extend(predicted.tolist())
        confidence.extend(probability.tolist())
        realized.extend(realized_ids.tolist())
        canonical.extend(
            CTC_PHONE_TO_ID[phone] for phone in row["pure_phones"]
        )
    return (
        np.asarray(predictions, dtype=np.int64),
        np.asarray(confidence, dtype=np.float64),
        np.asarray(realized, dtype=np.int64),
        np.asarray(canonical, dtype=np.int64),
    )


def _choose_substitution_threshold(
    prediction: np.ndarray,
    confidence: np.ndarray,
    realized: np.ndarray,
    canonical: np.ndarray,
) -> float:
    candidates = np.unique(
        np.concatenate(
            (
                np.linspace(0.05, 0.95, 91),
                confidence,
            )
        )
    )
    best: tuple[float, float] | None = None
    for threshold in candidates:
        emitted = (confidence >= threshold) & (prediction != canonical)
        predicted_count = int(np.sum(emitted))
        if predicted_count < SUBSTITUTION_MINIMUM_PREDICTIONS:
            continue
        precision = float(np.mean(prediction[emitted] == realized[emitted]))
        correct_count = int(np.sum(emitted & (prediction == realized)))
        if precision < SUBSTITUTION_MINIMUM_PRECISION:
            continue
        candidate = (float(correct_count), -float(threshold))
        if best is None or candidate > best:
            best = candidate
    return 1.0 if best is None else -best[1]


def substitution_evaluation(
    root: Path,
    rows: list[dict],
    feature_root: Path | None = None,
) -> tuple[float, dict]:
    speaker_names = sorted({row["speaker"] for row in rows})
    held_out_report = {}
    for held_out in speaker_names:
        train_speakers = set(speaker_names) - {held_out}
        train = _diagnosis_arrays(
            root,
            rows,
            speakers=train_speakers,
            feature_root=feature_root,
        )
        threshold = _choose_substitution_threshold(*train)
        prediction, confidence, realized, canonical = _diagnosis_arrays(
            root,
            rows,
            speakers={held_out},
            feature_root=feature_root,
        )
        emitted = (confidence >= threshold) & (prediction != canonical)
        predicted_count = int(np.sum(emitted))
        correct = int(np.sum(emitted & (prediction == realized)))
        actual_alternative = realized != canonical
        held_out_report[held_out] = {
            "threshold": threshold,
            "predicted": predicted_count,
            "precision": correct / max(1, predicted_count),
            "exact_matches": correct,
            "exact_match_recall": correct / max(1, int(np.sum(actual_alternative))),
        }
    final_arrays = _diagnosis_arrays(
        root,
        rows,
        feature_root=feature_root,
    )
    final_threshold = _choose_substitution_threshold(*final_arrays)
    return final_threshold, {
        "minimum_precision_target": SUBSTITUTION_MINIMUM_PRECISION,
        "minimum_predictions": SUBSTITUTION_MINIMUM_PREDICTIONS,
        "held_out_by_speaker": held_out_report,
        "final_threshold": final_threshold,
    }


def load_training_data(
    root: Path,
    feature_root: Path | None = None,
) -> tuple[PhoneData, WordData]:
    manifest = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    phone_features: list[np.ndarray] = []
    legacy_phone_features: list[np.ndarray] = []
    phone_error: list[np.ndarray] = []
    phone_severity: list[np.ndarray] = []
    phone_ids: list[np.ndarray] = []
    phone_word_keys: list[np.ndarray] = []
    phone_utterance_ids: list[np.ndarray] = []
    phone_speakers: list[np.ndarray] = []
    phone_variants: list[np.ndarray] = []
    word_features: list[np.ndarray] = []
    word_severity: list[np.ndarray] = []
    word_phone_counts: list[np.ndarray] = []
    word_keys: list[np.ndarray] = []
    word_utterance_ids: list[np.ndarray] = []
    word_utterance_severity: list[np.ndarray] = []
    word_speakers: list[np.ndarray] = []
    word_variants: list[np.ndarray] = []

    for example in load_examples(root, feature_root=feature_root):
        row = manifest[example.utterance_id]
        lengths = [len(value) for value in row["word_phones"]]
        canonical_phones = tuple(row["phones"])
        if len(canonical_phones) != len(example.phone_ids):
            raise ValueError(f"phone symbols do not cover {example.utterance_id}")
        speaker = row["speaker"]

        current_phone_features = build_phone_context_features(
            example.features,
            example.phone_ids,
            canonical_phones,
            lengths,
            normalization_mean=CTC_XGB_NORM_MEAN,
            normalization_std=CTC_XGB_NORM_STD,
        )
        count = len(example.phone_ids)
        normalized = build_ctc_evidence_features(
            example.features,
            canonical_phones,
            normalization_mean=CTC_XGB_NORM_MEAN,
            normalization_std=CTC_XGB_NORM_STD,
        )
        one_hot = np.eye(40, dtype=np.float32)[example.phone_ids + 1]
        position = np.arange(count, dtype=np.float32)[:, None] / max(1, count - 1)
        utterance_length = np.full(
            (count, 1), min(count, 50) / 50.0, dtype=np.float32
        )
        legacy_phone_features.append(
            np.concatenate((normalized, one_hot, position, utterance_length), axis=1)
        )
        severity = np.clip((2.0 - example.phone_targets) / 2.0, 0.0, 1.0)
        phone_features.append(current_phone_features)
        phone_error.append((severity > 0.0).astype(np.int32))
        phone_severity.append(severity.astype(np.float32))
        phone_ids.append(example.phone_ids.astype(np.int64))
        current_word_keys = np.concatenate(
            [
                np.full(length, f"{example.utterance_id}::{word_index}")
                for word_index, length in enumerate(lengths)
            ]
        )
        phone_word_keys.append(current_word_keys)
        phone_utterance_ids.append(np.full(count, example.utterance_id))
        phone_speakers.append(np.full(len(severity), speaker))
        phone_variants.append(np.full(len(severity), example.variant))

        current_word_features = build_word_context_features(
            example.features,
            example.phone_ids,
            canonical_phones,
            lengths,
            normalization_mean=CTC_XGB_NORM_MEAN,
            normalization_std=CTC_XGB_NORM_STD,
        )
        target_word_severity = np.clip(
            1.0 - (np.asarray(row["word_labels"], dtype=np.float32) / 2.0),
            0.0,
            1.0,
        )
        additions = np.asarray(row["addition_counts"], dtype=np.int64)
        effective_phone_counts = np.asarray(lengths, dtype=np.int64) + additions
        current_word_key_values = np.asarray(
            [f"{example.utterance_id}::{index}" for index in range(len(lengths))]
        )
        word_features.append(current_word_features)
        word_severity.append(target_word_severity)
        word_phone_counts.append(effective_phone_counts)
        word_keys.append(current_word_key_values)
        word_utterance_ids.append(
            np.full(len(target_word_severity), example.utterance_id)
        )
        word_utterance_severity.append(
            np.full(
                len(target_word_severity),
                np.clip(1.0 - (float(row["utterance_accuracy"]) / 2.0), 0.0, 1.0),
                dtype=np.float32,
            )
        )
        word_speakers.append(np.full(len(target_word_severity), speaker))
        word_variants.append(np.full(len(target_word_severity), example.variant))

    phones = PhoneData(
        features=np.concatenate(phone_features),
        legacy_features=np.concatenate(legacy_phone_features),
        error=np.concatenate(phone_error),
        severity=np.concatenate(phone_severity),
        phone_ids=np.concatenate(phone_ids),
        word_keys=np.concatenate(phone_word_keys),
        utterance_ids=np.concatenate(phone_utterance_ids),
        speakers=np.concatenate(phone_speakers),
        variants=np.concatenate(phone_variants),
    )
    words = WordData(
        features=np.concatenate(word_features),
        severity=np.concatenate(word_severity),
        phone_counts=np.concatenate(word_phone_counts),
        word_keys=np.concatenate(word_keys),
        utterance_ids=np.concatenate(word_utterance_ids),
        utterance_severity=np.concatenate(word_utterance_severity),
        speakers=np.concatenate(word_speakers),
        variants=np.concatenate(word_variants),
    )
    if phones.features.shape[1] != PHONE_CONTEXT_FEATURE_DIM:
        raise AssertionError(phones.features.shape)
    if phones.legacy_features.shape[1] != LEGACY_PHONE_FEATURE_DIM:
        raise AssertionError(phones.legacy_features.shape)
    if words.features.shape[1] != WORD_CONTEXT_FEATURE_DIM:
        raise AssertionError(words.features.shape)
    return phones, words


def _cross_calibrate_error(
    raw_probability: np.ndarray,
    labels: np.ndarray,
    speakers: np.ndarray,
) -> tuple[np.ndarray, LogisticRegression]:
    calibrated = np.zeros_like(raw_probability, dtype=np.float64)
    logits = _safe_logit(raw_probability)[:, None]
    for held_out in sorted(set(speakers)):
        train = speakers != held_out
        test = ~train
        model = LogisticRegression(C=10.0, solver="lbfgs", max_iter=1000)
        model.fit(logits[train], labels[train])
        calibrated[test] = model.predict_proba(logits[test])[:, 1]
    final = LogisticRegression(C=10.0, solver="lbfgs", max_iter=1000)
    final.fit(logits, labels)
    return calibrated, final


def _cross_calibrate_regression(
    raw_prediction: np.ndarray,
    labels: np.ndarray,
    speakers: np.ndarray,
) -> tuple[np.ndarray, LinearRegression]:
    calibrated = np.zeros_like(raw_prediction, dtype=np.float64)
    design = np.asarray(raw_prediction, dtype=np.float64)[:, None]
    for held_out in sorted(set(speakers)):
        train = speakers != held_out
        test = ~train
        model = LinearRegression()
        model.fit(design[train], labels[train])
        calibrated[test] = np.clip(model.predict(design[test]), 0.0, 1.0)
    final = LinearRegression()
    final.fit(design, labels)
    return calibrated, final


def _choose_red_threshold(
    labels: np.ndarray,
    probability: np.ndarray,
    severity: np.ndarray,
    *,
    minimum_precision: float,
    minimum_predictions: int,
) -> float | None:
    best: tuple[float, float] | None = None
    for threshold in np.unique(probability):
        if threshold < 0.30:
            continue
        predicted = (probability >= threshold) & (severity >= 0.30)
        count = int(np.sum(predicted))
        if count < minimum_predictions:
            continue
        true_positive = int(np.sum(predicted & (labels == 1)))
        precision = true_positive / count
        recall = true_positive / max(1, int(np.sum(labels == 1)))
        if precision >= minimum_precision and (best is None or recall > best[0]):
            best = (recall, float(threshold))
    return None if best is None else best[1]


def _select_red_policy(
    labels: np.ndarray,
    probability: np.ndarray,
    severity: np.ndarray,
    phone_ids: np.ndarray,
    *,
    minimum_precision: float,
) -> tuple[float, dict[int, float]]:
    global_threshold = _choose_red_threshold(
        labels,
        probability,
        severity,
        minimum_precision=minimum_precision,
        minimum_predictions=12,
    )
    if global_threshold is None:
        global_threshold = 1.0

    thresholds: dict[int, float] = {}
    for phone_id in sorted(set(phone_ids)):
        mask = phone_ids == phone_id
        if int(np.sum(labels[mask])) < 12:
            continue
        threshold = _choose_red_threshold(
            labels[mask],
            probability[mask],
            severity[mask],
            minimum_precision=minimum_precision,
            minimum_predictions=6,
        )
        if threshold is not None:
            thresholds[int(phone_id)] = threshold
    # Phone-specific samples are small with four speakers. Pull their cutoffs
    # toward the global cutoff so one speaker cannot create an extreme policy.
    thresholds = {
        phone_id: global_threshold
        + RED_PHONE_THRESHOLD_SHRINKAGE * (threshold - global_threshold)
        for phone_id, threshold in thresholds.items()
    }
    return float(global_threshold), thresholds


def _red_predictions(
    probability: np.ndarray,
    severity: np.ndarray,
    phone_ids: np.ndarray,
    thresholds: dict[int, float],
    global_threshold: float,
) -> np.ndarray:
    threshold = np.asarray(
        [thresholds.get(int(phone_id), global_threshold) for phone_id in phone_ids]
    )
    return (probability >= threshold) & (severity >= 0.30)


def _binary_status_metrics(labels: np.ndarray, predicted: np.ndarray) -> dict:
    true_positive = int(np.sum(predicted & (labels == 1)))
    precision = true_positive / max(1, int(np.sum(predicted)))
    recall = true_positive / max(1, int(np.sum(labels == 1)))
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(1e-12, precision + recall),
        "predicted": int(np.sum(predicted)),
    }


def _status_metrics(
    error_labels: np.ndarray,
    error_probability: np.ndarray,
    severe_labels: np.ndarray,
    severe_probability: np.ndarray,
    severity: np.ndarray,
    phone_ids: np.ndarray,
    red_thresholds: dict[int, float],
    global_red_threshold: float,
) -> dict:
    red = _red_predictions(
        severe_probability, severity, phone_ids, red_thresholds, global_red_threshold
    )
    warning_or_red = red | (error_probability > 0.15) | (severity > 0.15)
    return {
        "warning_or_red": _binary_status_metrics(error_labels, warning_or_red),
        "red": _binary_status_metrics(severe_labels, red),
    }


def _phone_to_word_prediction(
    phone_word_keys: np.ndarray,
    phone_prediction: np.ndarray,
    word_keys: np.ndarray,
) -> np.ndarray:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for key, value in zip(phone_word_keys, phone_prediction):
        text_key = str(key)
        sums[text_key] = sums.get(text_key, 0.0) + float(value)
        counts[text_key] = counts.get(text_key, 0) + 1
    missing = [str(key) for key in word_keys if str(key) not in sums]
    if missing:
        raise ValueError(f"phone predictions do not cover {len(missing)} words")
    return np.asarray(
        [sums[str(key)] / counts[str(key)] for key in word_keys], dtype=np.float64
    )


def _best_blend_weight(
    phone_prediction: np.ndarray,
    word_prediction: np.ndarray,
    truth: np.ndarray,
) -> float:
    best = (float("inf"), 0.5)
    for phone_weight in np.linspace(0.0, 1.0, 101):
        prediction = (phone_weight * phone_prediction) + (
            (1.0 - phone_weight) * word_prediction
        )
        mae = float(np.mean(np.abs(prediction - truth)))
        if mae < best[0]:
            best = (mae, float(phone_weight))
    return best[1]


def _cross_blend_word_predictions(
    phone_prediction: np.ndarray,
    word_prediction: np.ndarray,
    truth: np.ndarray,
    speakers: np.ndarray,
    variants: np.ndarray,
) -> tuple[np.ndarray, float]:
    blended = np.zeros_like(word_prediction, dtype=np.float64)
    clean = variants == "clean"
    for held_out in sorted(set(speakers)):
        train = clean & (speakers != held_out)
        test = speakers == held_out
        weight = _best_blend_weight(
            phone_prediction[train], word_prediction[train], truth[train]
        )
        blended[test] = (weight * phone_prediction[test]) + (
            (1.0 - weight) * word_prediction[test]
        )
    final_weight = _best_blend_weight(
        phone_prediction[clean], word_prediction[clean], truth[clean]
    )
    return np.clip(blended, 0.0, 1.0), final_weight


def _utterance_metrics(
    words: WordData,
    prediction: np.ndarray,
    mask: np.ndarray,
) -> dict:
    truth_values: list[float] = []
    prediction_values: list[float] = []
    for utterance_id in sorted(set(words.utterance_ids[mask])):
        current = mask & (words.utterance_ids == utterance_id)
        truth_values.append(float(words.utterance_severity[current][0]))
        prediction_values.append(
            float(
                np.average(
                    prediction[current], weights=words.phone_counts[current]
                )
            )
        )
    return _regression_metrics(
        np.asarray(truth_values), np.asarray(prediction_values)
    )


def train_and_evaluate(
    phones: PhoneData,
    words: WordData,
    *,
    seed: int,
    minimum_red_precision: float,
) -> tuple[
    dict,
    tuple[XGBClassifier, XGBClassifier, XGBRegressor, XGBRegressor],
    dict,
    dict[str, np.ndarray],
]:
    speakers = sorted(set(phones.speakers))
    error_oof = np.zeros(len(phones.error), dtype=np.float64)
    legacy_error_oof = np.zeros(len(phones.error), dtype=np.float64)
    severe_error_oof = np.zeros(len(phones.error), dtype=np.float64)
    severity_oof = np.zeros(len(phones.severity), dtype=np.float64)
    word_oof = np.zeros(len(words.severity), dtype=np.float64)

    for fold, held_out in enumerate(speakers):
        phone_train = phones.speakers != held_out
        phone_test = ~phone_train
        word_train = words.speakers != held_out
        word_test = ~word_train

        error_model = _error_model(seed + fold)
        error_weight = _variant_weight(phones.variants[phone_train]) * (
            1.0 + 2.0 * phones.error[phone_train]
        )
        error_model.fit(
            phones.features[phone_train],
            phones.error[phone_train],
            sample_weight=error_weight,
            verbose=False,
        )
        error_oof[phone_test] = error_model.predict_proba(phones.features[phone_test])[:, 1]

        legacy_model = _legacy_error_model(seed + fold)
        legacy_model.fit(
            phones.legacy_features[phone_train],
            phones.error[phone_train],
            verbose=False,
        )
        legacy_error_oof[phone_test] = legacy_model.predict_proba(
            phones.legacy_features[phone_test]
        )[:, 1]

        severe_model = _severe_error_model(seed + fold)
        severe_labels = (phones.severity[phone_train] >= 0.75).astype(np.int32)
        severe_weight = _variant_weight(phones.variants[phone_train]) * (
            1.0 + 2.0 * severe_labels
        )
        severe_model.fit(
            phones.features[phone_train],
            severe_labels,
            sample_weight=severe_weight,
            verbose=False,
        )
        severe_error_oof[phone_test] = severe_model.predict_proba(
            phones.features[phone_test]
        )[:, 1]

        severity_model = _severity_model(seed + fold)
        severity_weight = _variant_weight(phones.variants[phone_train]) * (
            1.0 + 3.0 * phones.severity[phone_train]
        )
        severity_model.fit(
            phones.features[phone_train],
            phones.severity[phone_train],
            sample_weight=severity_weight,
            verbose=False,
        )
        severity_oof[phone_test] = severity_model.predict(phones.features[phone_test])

        word_model = _word_model(seed + fold)
        word_weight = _variant_weight(words.variants[word_train]) * (
            1.0 + 3.0 * words.severity[word_train]
        )
        word_model.fit(
            words.features[word_train],
            words.severity[word_train],
            sample_weight=word_weight,
            verbose=False,
        )
        word_oof[word_test] = word_model.predict(words.features[word_test])

    calibrated_error, final_error_calibrator = _cross_calibrate_error(
        error_oof, phones.error, phones.speakers
    )
    calibrated_legacy_error, final_legacy_error_calibrator = _cross_calibrate_error(
        legacy_error_oof, phones.error, phones.speakers
    )
    severe_labels = (phones.severity >= 0.75).astype(np.int32)
    calibrated_severe_error, final_severe_error_calibrator = _cross_calibrate_error(
        severe_error_oof, severe_labels, phones.speakers
    )
    calibrated_severity, final_severity_calibrator = _cross_calibrate_regression(
        severity_oof, phones.severity, phones.speakers
    )
    quality_severity = np.clip(
        QUALITY_SEVERITY_REGRESSOR_WEIGHT * calibrated_severity
        + (1.0 - QUALITY_SEVERITY_REGRESSOR_WEIGHT) * calibrated_legacy_error,
        0.0,
        1.0,
    )
    calibrated_word, final_word_calibrator = _cross_calibrate_regression(
        word_oof, words.severity, words.speakers
    )

    phone_word_oof = _phone_to_word_prediction(
        phones.word_keys, quality_severity, words.word_keys
    )
    blended_word_oof, final_phone_word_blend = _cross_blend_word_predictions(
        phone_word_oof,
        calibrated_word,
        words.severity,
        words.speakers,
        words.variants,
    )

    clean = phones.variants == "clean"
    clean_word = words.variants == "clean"
    global_red, red_thresholds = _select_red_policy(
        severe_labels[clean],
        calibrated_severe_error[clean],
        quality_severity[clean],
        phones.phone_ids[clean],
        minimum_precision=minimum_red_precision,
    )

    nested_red_by_target: dict[str, dict] = {}
    nested_red_for_policy = None
    for precision_target in sorted({0.65, 0.75, 0.80, 0.85, minimum_red_precision}):
        nested_red = np.zeros(len(phones.error), dtype=bool)
        for held_out in speakers:
            policy_train = clean & (phones.speakers != held_out)
            policy_test = clean & (phones.speakers == held_out)
            fold_global_red, fold_red_thresholds = _select_red_policy(
                severe_labels[policy_train],
                calibrated_severe_error[policy_train],
                quality_severity[policy_train],
                phones.phone_ids[policy_train],
                minimum_precision=precision_target,
            )
            nested_red[policy_test] = _red_predictions(
                calibrated_severe_error[policy_test],
                quality_severity[policy_test],
                phones.phone_ids[policy_test],
                fold_red_thresholds,
                fold_global_red,
            )
        nested_red_by_target[f"{precision_target:.2f}"] = {
            "severe_error": _binary_status_metrics(
                severe_labels[clean], nested_red[clean]
            ),
            "any_error": _binary_status_metrics(
                phones.error[clean], nested_red[clean]
            ),
        }
        if precision_target == minimum_red_precision:
            nested_red_for_policy = nested_red
    assert nested_red_for_policy is not None

    by_speaker = {}
    for speaker in speakers:
        phone_mask = phones.speakers == speaker
        word_mask = words.speakers == speaker
        by_speaker[speaker] = {
            "phone_error_at_15_percent": _classification_metrics(
                phones.error[phone_mask], calibrated_legacy_error[phone_mask], 0.15
            ),
            "phone_severity": _regression_metrics(
                phones.severity[phone_mask], quality_severity[phone_mask]
            ),
            "phone_severity_regressor_only": _regression_metrics(
                phones.severity[phone_mask], calibrated_severity[phone_mask]
            ),
            "word_severity": _regression_metrics(
                words.severity[word_mask], blended_word_oof[word_mask]
            ),
            "utterance_severity_clean": _utterance_metrics(
                words,
                blended_word_oof,
                word_mask & (words.variants == "clean"),
            ),
            "status": _status_metrics(
                phones.error[phone_mask],
                calibrated_legacy_error[phone_mask],
                severe_labels[phone_mask],
                calibrated_severe_error[phone_mask],
                quality_severity[phone_mask],
                phones.phone_ids[phone_mask],
                red_thresholds,
                global_red,
            ),
        }

    report = {
        "evaluation": "leave-one-Arabic-speaker-out; calibration also cross-fitted by speaker",
        "speakers": speakers,
        "phones": int(len(phones.error)),
        "words": int(len(words.severity)),
        "phone_error_prevalence": float(np.mean(phones.error)),
        "phone_error_at_15_percent": _classification_metrics(
            phones.error, calibrated_legacy_error, 0.15
        ),
        "phone_error_ranking": {
            "average_precision": float(
                average_precision_score(phones.error, legacy_error_oof)
            ),
            "roc_auc": float(roc_auc_score(phones.error, legacy_error_oof)),
        },
        "context_error_classifier_candidate": {
            "phone_error_at_15_percent": _classification_metrics(
                phones.error, calibrated_error, 0.15
            ),
            "phone_error_ranking": {
                "average_precision": float(
                    average_precision_score(phones.error, error_oof)
                ),
                "roc_auc": float(roc_auc_score(phones.error, error_oof)),
            },
            "zhaa": _classification_metrics(
                phones.error[phones.speakers == "ZHAA"],
                calibrated_error[phones.speakers == "ZHAA"],
                0.15,
            ),
        },
        "severe_error_ranking": {
            "average_precision": float(
                average_precision_score(severe_labels, severe_error_oof)
            ),
            "roc_auc": float(roc_auc_score(severe_labels, severe_error_oof)),
        },
        "phone_severity": _regression_metrics(phones.severity, quality_severity),
        "phone_severity_regressor_only": _regression_metrics(
            phones.severity, calibrated_severity
        ),
        "word_severity_model_only": _regression_metrics(
            words.severity, calibrated_word
        ),
        "word_severity": _regression_metrics(words.severity, blended_word_oof),
        "word_blend_phone_weight": final_phone_word_blend,
        "clean_utterance_severity": _utterance_metrics(
            words, blended_word_oof, clean_word
        ),
        "clean_status": _status_metrics(
            phones.error[clean],
            calibrated_legacy_error[clean],
            severe_labels[clean],
            calibrated_severe_error[clean],
            quality_severity[clean],
            phones.phone_ids[clean],
            red_thresholds,
            global_red,
        ),
        "clean_red_nested_threshold_evaluation": _binary_status_metrics(
            severe_labels[clean], nested_red_for_policy[clean]
        ),
        "clean_red_nested_by_precision_target": nested_red_by_target,
        "clean_word_severity": _regression_metrics(
            words.severity[clean_word], blended_word_oof[clean_word]
        ),
        "by_speaker": by_speaker,
    }

    final_error = _legacy_error_model(seed + 100)
    final_error.fit(
        phones.legacy_features,
        phones.error,
        verbose=False,
    )
    final_severe_error = _severe_error_model(seed + 100)
    final_severe_error.fit(
        phones.features,
        severe_labels,
        sample_weight=_variant_weight(phones.variants) * (1.0 + 2.0 * severe_labels),
        verbose=False,
    )
    final_severity = _severity_model(seed + 100)
    final_severity.fit(
        phones.features,
        phones.severity,
        sample_weight=_variant_weight(phones.variants) * (1.0 + 3.0 * phones.severity),
        verbose=False,
    )
    calibrators = {
        "error": {
            "slope": float(final_legacy_error_calibrator.coef_[0, 0]),
            "intercept": float(final_legacy_error_calibrator.intercept_[0]),
        },
        "severe_error": {
            "slope": float(final_severe_error_calibrator.coef_[0, 0]),
            "intercept": float(final_severe_error_calibrator.intercept_[0]),
        },
        "phone_severity": {
            "slope": float(final_severity_calibrator.coef_[0]),
            "intercept": float(final_severity_calibrator.intercept_),
        },
        "word_severity": {
            "slope": float(final_word_calibrator.coef_[0]),
            "intercept": float(final_word_calibrator.intercept_),
        },
        "phone_word_blend_phone_weight": float(final_phone_word_blend),
        "quality_severity_regressor_weight": QUALITY_SEVERITY_REGRESSOR_WEIGHT,
        "global_red_severe_probability": float(global_red),
        "red_severe_probability_by_phone_id": {
            str(phone_id): float(threshold)
            for phone_id, threshold in sorted(red_thresholds.items())
        },
    }
    evaluation_arrays = {
        "error_labels": phones.error,
        "severe_labels": severe_labels,
        "error_probability": calibrated_legacy_error,
        "severe_probability": calibrated_severe_error,
        "severity_prediction": quality_severity,
        "severity_regressor_prediction": calibrated_severity,
        "phone_ids": phones.phone_ids,
        "speakers": phones.speakers,
        "variants": phones.variants,
    }
    return (
        report,
        (final_error, final_severe_error, final_severity),
        calibrators,
        evaluation_arrays,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=Path, default=DEFAULT_ARABIC_DATASET
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/pretrained_models/arabic_pronunciation_ctc_v3"),
    )
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--minimum-red-precision", type=float, default=0.65)
    parser.add_argument("--oof-output", type=Path)
    parser.add_argument("--feature-root", type=Path)
    args = parser.parse_args()

    phones, words = load_training_data(
        args.data,
        feature_root=args.feature_root,
    )
    manifest_rows = [
        json.loads(line)
        for line in (args.data / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    substitution_threshold, substitution_report = substitution_evaluation(
        args.data,
        manifest_rows,
        feature_root=args.feature_root,
    )
    report, models, calibration, evaluation_arrays = train_and_evaluate(
        phones,
        words,
        seed=args.seed,
        minimum_red_precision=args.minimum_red_precision,
    )
    error_model, severe_error_model, severity_model = models
    metadata = {
        "version": 3,
        "purpose": "Arabic-L1 phone error likelihood, severe-error evidence, and human-label phone severity",
        "data": str(args.data),
        "feature_root": str(
            (args.feature_root or (args.data / "ctc_gop_output")).resolve()
        ),
        "seed": args.seed,
        "normalization": {
            "mean": CTC_XGB_NORM_MEAN,
            "std": CTC_XGB_NORM_STD,
        },
        "feature_schema": {
            "phone_error_legacy": LEGACY_PHONE_FEATURE_DIM,
            "phone_context": PHONE_CONTEXT_FEATURE_DIM,
            "word_context": WORD_CONTEXT_FEATURE_DIM,
        },
        "phone_to_id": GOPT_PHONE_TO_ID,
        "status_policy": {
            "green_max_error_probability": 0.15,
            "green_max_error_severity": 0.15,
            "red_min_error_severity": 0.30,
            "substitution_confidence_threshold": substitution_threshold,
            "minimum_red_precision_target": args.minimum_red_precision,
            "phone_threshold_shrinkage": RED_PHONE_THRESHOLD_SHRINKAGE,
            "orange_means": "uncertain; articulation coaching is reserved for red phones",
        },
        "deployment": {
            "word_model_used": False,
            "reason": "speaker-held-out blending selected aggregated phone evidence; the insertion-aware word candidate did not improve validation",
        },
        "calibration": calibration,
        "report": report,
        "substitution_report": substitution_report,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    error_model.save_model(args.output / "phone_error_model.json")
    severe_error_model.save_model(args.output / "phone_severe_error_model.json")
    severity_model.save_model(args.output / "phone_severity_model.json")
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.oof_output is not None:
        args.oof_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.oof_output, **evaluation_arrays)
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"saved models to {args.output}")


if __name__ == "__main__":
    main()
