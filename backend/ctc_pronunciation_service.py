"""XLSR-53 CTC-GOP, GOPT, and XGBoost pronunciation scoring.

All acoustic, GOPT, and Arabic-L1 model schemas must match before a score can
be returned.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from xgboost import XGBClassifier, XGBRegressor

from ctc_gop import (
    CTC_GOP_FEATURE_DIM,
    CtcGopError,
    CtcGopResult,
    Wav2Vec2CtcGopExtractor,
)
from gopt_models.gopt import GOPT
from pronunciation_features import (
    GOP_FEATURE_DIM,
    PHONE_CONTEXT_FEATURE_DIM,
    XGB_ACOUSTIC_FEATURE_DIM,
    build_ctc_evidence_features,
    build_phone_context_features,
    normalize_gop_features,
)
from pronunciation_core import (
    GOPT_PHONE_TO_ID,
    MAX_GOPT_PHONES,
    OVERALL_SCORE_WEIGHTS,
    WORD_OVERALL_SCORE_WEIGHTS,
    LocalG2pCanonicalizer,
    PronunciationScoringError,
    arpabet_to_ipa,
    calculate_overall_score,
    calculate_word_overall_score,
)


SCORING_METHOD = "xlsr53_ctc_gop_arabic_loso_severity_gopt_v3"
ARABIC_MODEL_VERSION = 3
GOPT_MODEL_VERSION = 1
LEGACY_PHONE_FEATURE_DIM = XGB_ACOUSTIC_FEATURE_DIM + 40 + 2


def _normalization_vector(
    value: float | Sequence[float],
    *,
    name: str,
) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 0:
        array = np.full(GOP_FEATURE_DIM, float(array), dtype=np.float32)
    if array.shape != (GOP_FEATURE_DIM,) or not np.isfinite(array).all():
        raise ValueError(f"{name} must contain {GOP_FEATURE_DIM} finite values")
    return array


class Wav2Vec2GoptScorer:
    """Strict production scorer with no legacy acoustic fallback."""

    def __init__(
        self,
        backend_dir: Path | None = None,
        *,
        extractor: Wav2Vec2CtcGopExtractor | None = None,
    ):
        self.backend_dir = backend_dir or Path(__file__).resolve().parent
        if CTC_GOP_FEATURE_DIM != GOP_FEATURE_DIM:
            raise PronunciationScoringError(
                "CTC-GOP and pronunciation feature schemas disagree"
            )
        self._load_gopt()
        self._load_arabic_models()
        model_dir = (
            self.backend_dir
            / "pretrained_models"
            / "wav2vec2_xlsr53_cmu39_ctc"
        )
        try:
            self.extractor = extractor or Wav2Vec2CtcGopExtractor(model_dir)
        except CtcGopError as exc:
            raise PronunciationScoringError(str(exc)) from exc
        self.canonicalizer = LocalG2pCanonicalizer()

    def _load_gopt(self) -> None:
        model_dir = self.backend_dir / "pretrained_models" / "gopt_ctc"
        weights_path = model_dir / "best_audio_model.pth"
        metadata_path = model_dir / "metadata.json"
        if not weights_path.is_file() or not metadata_path.is_file():
            raise PronunciationScoringError(
                f"CTC-GOPT assets are missing under: {model_dir}"
            )
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if int(metadata["version"]) != GOPT_MODEL_VERSION:
                raise ValueError("unsupported CTC-GOPT version")
            if int(metadata["input_dim"]) != GOP_FEATURE_DIM:
                raise ValueError("CTC-GOPT input width does not match runtime")
            phone_to_id = {
                str(phone): int(phone_id)
                for phone, phone_id in metadata["phone_to_id"].items()
            }
            if phone_to_id != GOPT_PHONE_TO_ID:
                raise ValueError("CTC-GOPT phone mapping does not match runtime")
            self.gopt_norm_mean = _normalization_vector(
                metadata["normalization"]["mean"],
                name="CTC-GOPT normalization mean",
            )
            self.gopt_norm_std = _normalization_vector(
                metadata["normalization"]["std"],
                name="CTC-GOPT normalization std",
            )
            if np.any(self.gopt_norm_std <= 0):
                raise ValueError("CTC-GOPT normalization std must be positive")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PronunciationScoringError(
                f"CTC-GOPT metadata is malformed: {metadata_path}"
            ) from exc

        model = GOPT(
            embed_dim=24,
            num_heads=1,
            depth=3,
            input_dim=GOP_FEATURE_DIM,
        )
        try:
            state = torch.load(weights_path, map_location="cpu", weights_only=True)
            if state and all(str(key).startswith("module.") for key in state):
                state = {str(key)[7:]: value for key, value in state.items()}
            model.load_state_dict(state, strict=True)
        except Exception as exc:
            raise PronunciationScoringError(
                f"CTC-GOPT weights are incompatible: {weights_path}"
            ) from exc
        self.model = model.float().eval()

    def _load_arabic_models(self) -> None:
        model_dir = (
            self.backend_dir
            / "pretrained_models"
            / "arabic_pronunciation_ctc_v3"
        )
        classifier_path = model_dir / "phone_error_model.json"
        severe_classifier_path = model_dir / "phone_severe_error_model.json"
        severity_path = model_dir / "phone_severity_model.json"
        metadata_path = model_dir / "metadata.json"
        if not all(
            path.is_file()
            for path in (
                classifier_path,
                severe_classifier_path,
                severity_path,
                metadata_path,
            )
        ):
            raise PronunciationScoringError(
                f"Arabic pronunciation CTC-v3 assets are missing under: {model_dir}"
            )

        self.phone_classifier = XGBClassifier()
        self.phone_classifier.load_model(classifier_path)
        self.phone_severe_classifier = XGBClassifier()
        self.phone_severe_classifier.load_model(severe_classifier_path)
        self.phone_severity_model = XGBRegressor()
        self.phone_severity_model.load_model(severity_path)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if int(metadata["version"]) != ARABIC_MODEL_VERSION:
                raise ValueError("unsupported Arabic pronunciation model version")
            calibration = metadata["calibration"]
            self.probability_slope = float(calibration["error"]["slope"])
            self.probability_intercept = float(calibration["error"]["intercept"])
            self.severe_probability_slope = float(
                calibration["severe_error"]["slope"]
            )
            self.severe_probability_intercept = float(
                calibration["severe_error"]["intercept"]
            )
            self.severity_slope = float(calibration["phone_severity"]["slope"])
            self.severity_intercept = float(
                calibration["phone_severity"]["intercept"]
            )
            self.quality_severity_regressor_weight = float(
                calibration["quality_severity_regressor_weight"]
            )
            self.global_red_severe_probability = float(
                calibration["global_red_severe_probability"]
            )
            self.red_severe_probability_by_phone_id = {
                int(phone_id): float(threshold)
                for phone_id, threshold in calibration[
                    "red_severe_probability_by_phone_id"
                ].items()
            }
            status_policy = metadata["status_policy"]
            self.warning_probability_threshold = float(
                status_policy["green_max_error_probability"]
            )
            self.warning_severity_threshold = float(
                status_policy["green_max_error_severity"]
            )
            self.red_minimum_severity = float(
                status_policy["red_min_error_severity"]
            )
            self.substitution_confidence_threshold = float(
                status_policy.get("substitution_confidence_threshold", 0.20)
            )
            feature_schema = metadata["feature_schema"]
            if int(feature_schema["phone_error_legacy"]) != LEGACY_PHONE_FEATURE_DIM:
                raise ValueError("phone-error feature width does not match runtime")
            if int(feature_schema["phone_context"]) != PHONE_CONTEXT_FEATURE_DIM:
                raise ValueError("phone-context feature width does not match runtime")
            phone_to_id = {
                str(phone): int(phone_id)
                for phone, phone_id in metadata["phone_to_id"].items()
            }
            if phone_to_id != GOPT_PHONE_TO_ID:
                raise ValueError("Arabic model phone mapping does not match runtime")
            self.xgb_norm_mean = _normalization_vector(
                metadata["normalization"]["mean"],
                name="Arabic model normalization mean",
            )
            self.xgb_norm_std = _normalization_vector(
                metadata["normalization"]["std"],
                name="Arabic model normalization std",
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PronunciationScoringError(
                f"Arabic pronunciation CTC-v3 metadata is malformed: {metadata_path}"
            ) from exc

        numeric_policy = (
            self.probability_slope,
            self.probability_intercept,
            self.severe_probability_slope,
            self.severe_probability_intercept,
            self.severity_slope,
            self.severity_intercept,
            self.quality_severity_regressor_weight,
            self.global_red_severe_probability,
            self.warning_probability_threshold,
            self.warning_severity_threshold,
            self.red_minimum_severity,
            self.substitution_confidence_threshold,
            *self.red_severe_probability_by_phone_id.values(),
        )
        if not all(np.isfinite(value) for value in numeric_policy):
            raise PronunciationScoringError(
                "Arabic pronunciation CTC-v3 policy contains non-finite values"
            )
        if not all(
            0.0 <= value <= 1.0
            for value in (
                self.quality_severity_regressor_weight,
                self.global_red_severe_probability,
                self.warning_probability_threshold,
                self.warning_severity_threshold,
                self.red_minimum_severity,
                self.substitution_confidence_threshold,
                *self.red_severe_probability_by_phone_id.values(),
            )
        ):
            raise PronunciationScoringError(
                "Arabic pronunciation CTC-v3 thresholds must be probabilities"
            )
        if self.phone_classifier.get_booster().num_features() != LEGACY_PHONE_FEATURE_DIM:
            raise PronunciationScoringError(
                "Phone-error CTC-v3 model feature width is incompatible"
            )
        if (
            self.phone_severe_classifier.get_booster().num_features()
            != PHONE_CONTEXT_FEATURE_DIM
            or self.phone_severity_model.get_booster().num_features()
            != PHONE_CONTEXT_FEATURE_DIM
        ):
            raise PronunciationScoringError(
                "Phone-context CTC-v3 model feature width is incompatible"
            )

    @staticmethod
    def _calibrated_probability(
        raw_probability: np.ndarray,
        slope: float,
        intercept: float,
        *,
        count: int,
        name: str,
    ) -> np.ndarray:
        values = np.asarray(raw_probability, dtype=np.float64)
        if values.shape != (count,) or not np.isfinite(values).all():
            raise PronunciationScoringError(
                f"The {name} model returned malformed probabilities"
            )
        clipped = np.clip(values, 1e-6, 1.0 - 1e-6)
        logits = np.log(clipped / (1.0 - clipped))
        calibrated = np.clip((slope * logits) + intercept, -30.0, 30.0)
        return 1.0 / (1.0 + np.exp(-calibrated))

    def _gopt_scores(
        self,
        raw_features: np.ndarray,
        phone_ids: np.ndarray,
        word_phone_lengths: Sequence[int],
    ) -> tuple[int, int]:
        normalized = normalize_gop_features(
            raw_features,
            self.gopt_norm_mean,
            self.gopt_norm_std,
        )
        chunk_ranges: list[tuple[int, int]] = []
        chunk_start = 0
        chunk_length = 0
        phone_offset = 0
        for word_length in word_phone_lengths:
            if chunk_length and chunk_length + word_length > MAX_GOPT_PHONES:
                chunk_ranges.append((chunk_start, phone_offset))
                chunk_start = phone_offset
                chunk_length = 0
            chunk_length += word_length
            phone_offset += word_length
        chunk_ranges.append((chunk_start, phone_offset))

        chunk_count = len(chunk_ranges)
        features = np.zeros(
            (chunk_count, MAX_GOPT_PHONES, GOP_FEATURE_DIM), dtype=np.float32
        )
        chunks = np.full((chunk_count, MAX_GOPT_PHONES), -1, dtype=np.int64)
        chunk_lengths: list[int] = []
        for chunk_index, (start, end) in enumerate(chunk_ranges):
            length = end - start
            features[chunk_index, :length] = normalized[start:end]
            chunks[chunk_index, :length] = phone_ids[start:end]
            chunk_lengths.append(length)
        with torch.inference_mode():
            outputs = self.model(
                torch.from_numpy(features),
                torch.from_numpy(chunks),
            )
        fluency, prosody = outputs[2], outputs[3]
        weights = np.asarray(chunk_lengths, dtype=np.float32)

        def percent(value: torch.Tensor) -> int:
            values = value[:, 0].detach().cpu().numpy()
            if values.shape != (chunk_count,) or not np.isfinite(values).all():
                raise PronunciationScoringError(
                    "CTC-GOPT returned malformed fluency/prosody values"
                )
            return int(
                np.clip(round(float(np.average(values, weights=weights)) * 50.0), 0, 100)
            )

        return percent(fluency), percent(prosody)

    def score(self, audio_path: str | Path, target_text: str) -> dict:
        pronunciation = self.canonicalizer.canonicalize(target_text)
        try:
            extraction = self.extractor.extract(
                audio_path,
                pronunciation.pure_phones,
            )
        except CtcGopError as exc:
            raise PronunciationScoringError(str(exc)) from exc
        if not isinstance(extraction, CtcGopResult):
            raise PronunciationScoringError("CTC-GOP extractor returned malformed data")
        raw_features = extraction.features
        count = len(pronunciation.phones)
        if raw_features.shape != (count, GOP_FEATURE_DIM):
            raise PronunciationScoringError(
                f"CTC-GOP returned {raw_features.shape}; expected {(count, GOP_FEATURE_DIM)}"
            )
        phone_ids = np.asarray(
            [GOPT_PHONE_TO_ID[phone] for phone in pronunciation.pure_phones],
            dtype=np.int64,
        )
        word_lengths = tuple(len(phones) for phones in pronunciation.word_phones)
        fluency, prosody = self._gopt_scores(
            raw_features,
            phone_ids,
            word_lengths,
        )

        normalized = build_ctc_evidence_features(
            raw_features,
            pronunciation.pure_phones,
            normalization_mean=self.xgb_norm_mean,
            normalization_std=self.xgb_norm_std,
        )
        one_hot = np.eye(40, dtype=np.float32)[phone_ids + 1]
        position = np.arange(count, dtype=np.float32)[:, None] / max(1, count - 1)
        length = np.full(
            (count, 1),
            min(count, MAX_GOPT_PHONES) / MAX_GOPT_PHONES,
            dtype=np.float32,
        )
        classifier_features = np.concatenate(
            (normalized, one_hot, position, length),
            axis=1,
        )
        context_features = build_phone_context_features(
            raw_features,
            phone_ids,
            pronunciation.phones,
            word_lengths,
            normalization_mean=self.xgb_norm_mean,
            normalization_std=self.xgb_norm_std,
        )
        error_probability = self._calibrated_probability(
            self.phone_classifier.predict_proba(classifier_features)[:, 1],
            self.probability_slope,
            self.probability_intercept,
            count=count,
            name="phone-error",
        )
        severe_error_probability = self._calibrated_probability(
            self.phone_severe_classifier.predict_proba(context_features)[:, 1],
            self.severe_probability_slope,
            self.severe_probability_intercept,
            count=count,
            name="severe-phone-error",
        )
        raw_severity = np.asarray(
            self.phone_severity_model.predict(context_features),
            dtype=np.float64,
        )
        if raw_severity.shape != (count,) or not np.isfinite(raw_severity).all():
            raise PronunciationScoringError(
                "The phone-severity model returned malformed values"
            )
        model_severity = np.clip(
            (self.severity_slope * raw_severity) + self.severity_intercept,
            0.0,
            1.0,
        )
        error_severity = np.clip(
            self.quality_severity_regressor_weight * model_severity
            + (1.0 - self.quality_severity_regressor_weight) * error_probability,
            0.0,
            1.0,
        )
        phone_scores = np.rint(100.0 * (1.0 - error_severity)).astype(int)

        analysis: list[dict] = []
        mistakes: list[dict] = []
        uncertain: list[dict] = []
        for index, (arpabet, ipa, phone_id) in enumerate(
            zip(pronunciation.phones, pronunciation.ipa_phones, phone_ids.tolist())
        ):
            error_chance = float(error_probability[index])
            severe_chance = float(severe_error_probability[index])
            severity = float(error_severity[index])
            red_threshold = self.red_severe_probability_by_phone_id.get(
                int(phone_id),
                self.global_red_severe_probability,
            )
            if severe_chance >= red_threshold and severity >= self.red_minimum_severity:
                status = "incorrect"
            elif (
                error_chance > self.warning_probability_threshold + 1e-9
                or severity > self.warning_severity_threshold + 1e-9
            ):
                status = "warning"
            else:
                status = "correct"

            likely_phone = extraction.likely_phones[index]
            likely_probability = float(extraction.likely_phone_probabilities[index])
            deletion_probability = float(extraction.deletion_probabilities[index])
            expected_phone = pronunciation.pure_phones[index]
            is_confident_substitution = (
                likely_phone is not None
                and likely_phone != expected_phone
                and likely_probability > self.substitution_confidence_threshold
            )
            is_confident_deletion = (
                likely_phone is None
                and deletion_probability > self.substitution_confidence_threshold
            )
            # A replacement/deletion threshold is calibrated separately from
            # XGBoost severity. When it passes, the diagnosis is actionable
            # even if the conservative severe-error model only returned an
            # orange warning.
            if is_confident_substitution or is_confident_deletion:
                status = "incorrect"
            heard_as_ipa = (
                arpabet_to_ipa(likely_phone)
                if is_confident_substitution and likely_phone is not None
                else None
            )
            closest_ipa = (
                arpabet_to_ipa(likely_phone)
                if likely_phone is not None and likely_phone != expected_phone
                else None
            )
            item = {
                "phone_index": index,
                "char": ipa,
                "arpabet": arpabet,
                "status": status,
                "score": int(phone_scores[index]),
                "correct_probability": round((1.0 - error_chance) * 100.0, 1),
                "error_probability": round(error_chance * 100.0, 1),
                "severe_error_probability": round(severe_chance * 100.0, 1),
                "error_severity": round(severity * 100.0, 1),
                "model_error_severity": round(float(model_severity[index]) * 100.0, 1),
                "likely_arpabet": likely_phone,
                "likely_ipa": heard_as_ipa,
                "likely_phone_probability": round(likely_probability * 100.0, 1),
                "deletion_probability": round(deletion_probability * 100.0, 1),
                "closest_arpabet": (
                    likely_phone if likely_phone != expected_phone else None
                ),
                "closest_ipa": closest_ipa,
                "replacement_verified": bool(
                    is_confident_substitution or is_confident_deletion
                ),
                "error_type": (
                    "substitution"
                    if is_confident_substitution
                    else "deletion"
                    if is_confident_deletion
                    else None
                ),
            }
            analysis.append(item)
            evidence = {
                "phone_index": index,
                "phoneme": ipa,
                "arpabet": arpabet,
                "status": status,
                "score": int(phone_scores[index]),
                "error_probability": item["error_probability"],
                "severe_error_probability": item["severe_error_probability"],
                "error_severity": item["error_severity"],
                "likely_arpabet": item["likely_arpabet"],
                "likely_ipa": item["likely_ipa"],
                "likely_phone_probability": item["likely_phone_probability"],
                "deletion_probability": item["deletion_probability"],
                "closest_arpabet": item["closest_arpabet"],
                "closest_ipa": item["closest_ipa"],
                "replacement_verified": item["replacement_verified"],
                "error_type": item["error_type"],
            }
            if status == "incorrect":
                mistakes.append(evidence)
            elif status == "warning":
                uncertain.append(evidence)

        word_scores: list[dict] = []
        offset = 0
        for word, phones in zip(pronunciation.words, pronunciation.word_phones):
            phone_count = len(phones)
            segment_scores = phone_scores[offset : offset + phone_count]
            word_severity = float(
                np.mean(error_severity[offset : offset + phone_count])
            )
            word_scores.append(
                {
                    "word": word.lower(),
                    "accuracy": int(
                        np.clip(round(100.0 * (1.0 - word_severity)), 0, 100)
                    ),
                    "weakest_phone_score": int(np.min(segment_scores)),
                    "error_severity": round(word_severity * 100.0, 1),
                    "phone_start": offset,
                    "phone_end": offset + phone_count,
                }
            )
            offset += phone_count

        word_weights = np.asarray(word_lengths, dtype=np.float64)
        scores = {
            "accuracy": int(
                round(
                    float(
                        np.average(
                            [item["accuracy"] for item in word_scores],
                            weights=word_weights,
                        )
                    )
                )
            ),
            "completeness": 100,
            "fluency": fluency,
            "prosody": prosody,
        }
        if len(pronunciation.words) == 1:
            scores["overall_score"] = calculate_word_overall_score(scores)
            overall_weights = WORD_OVERALL_SCORE_WEIGHTS
        else:
            scores["overall_score"] = calculate_overall_score(scores)
            overall_weights = OVERALL_SCORE_WEIGHTS
        scores["gop_score"] = scores["overall_score"]

        feedback = "Strong pronunciation across the analyzed sounds."
        if mistakes:
            descriptions = []
            for item in mistakes[:5]:
                if item["likely_ipa"]:
                    descriptions.append(
                        f"/{item['phoneme']}/ sounded closer to /{item['likely_ipa']}/"
                    )
                elif item["error_type"] == "deletion":
                    descriptions.append(f"/{item['phoneme']}/ may have been omitted")
                else:
                    descriptions.append(
                        f"/{item['phoneme']}/ ({item['score']}/100)"
                    )
            feedback = "Focus on: " + "; ".join(descriptions) + "."
        elif uncertain:
            focus = ", ".join(f"/{item['phoneme']}/" for item in uncertain[:5])
            feedback = (
                f"The evidence is uncertain for {focus}. Repeat the target "
                "before treating these as mistakes."
            )

        return {
            "target": target_text.strip(),
            "spoken": None,
            "target_ipa": list(pronunciation.ipa_phones),
            "analysis": analysis,
            "word_scores": word_scores,
            "feedback": feedback,
            "scores": scores,
            "scoring_method": SCORING_METHOD,
            "flagged_phones": mistakes,
            "uncertain_phones": uncertain,
            "calibration": {
                "green_max_error_probability": round(
                    self.warning_probability_threshold * 100.0, 1
                ),
                "green_max_error_severity": round(
                    self.warning_severity_threshold * 100.0, 1
                ),
                "global_red_severe_probability": round(
                    self.global_red_severe_probability * 100.0, 1
                ),
                "red_minimum_error_severity": round(
                    self.red_minimum_severity * 100.0, 1
                ),
                "substitution_confidence_threshold": round(
                    self.substitution_confidence_threshold * 100.0, 1
                ),
                "orange_means": (
                    "uncertain; only red phones receive articulation coaching"
                ),
                "quality_scale": (
                    "100 minus the calibrated Arabic-L1 severity/error blend"
                ),
                "overall_weights": overall_weights,
            },
            "warnings": [],
        }
