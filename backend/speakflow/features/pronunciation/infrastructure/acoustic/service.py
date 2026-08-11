"""XLSR-53 CTC-GOP, GOPT, and XGBoost pronunciation scoring.

All acoustic, GOPT, and Arabic-L1 model schemas must match before a score can
be returned.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch
from xgboost import XGBClassifier, XGBRegressor

from gopt_models.gopt import GOPT
from speakflow.config import BACKEND_ROOT
from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    GOPT_PHONE_TO_ID,
    MAX_GOPT_PHONES,
    LocalG2pCanonicalizer,
    PronunciationScoringError,
)
from speakflow.features.pronunciation.infrastructure.acoustic.features import (
    GOP_FEATURE_DIM,
    PHONE_CONTEXT_FEATURE_DIM,
    XGB_ACOUSTIC_FEATURE_DIM,
    normalize_gop_features,
)
from speakflow.features.pronunciation.infrastructure.acoustic.gop import (
    CTC_GOP_FEATURE_DIM,
    CtcGopError,
    Wav2Vec2CtcGopExtractor,
)
from speakflow.features.pronunciation.infrastructure.acoustic.scoring import (
    Wav2Vec2ScoringMixin,
)

ARABIC_MODEL_FORMAT_REVISION = 3
GOPT_MODEL_FORMAT_REVISION = 1
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


class Wav2Vec2GoptScorer(Wav2Vec2ScoringMixin):
    """Strict production scorer with no legacy acoustic fallback."""

    def __init__(
        self,
        backend_dir: Path | None = None,
        *,
        extractor: Wav2Vec2CtcGopExtractor | None = None,
    ):
        self.backend_dir = backend_dir or BACKEND_ROOT
        if CTC_GOP_FEATURE_DIM != GOP_FEATURE_DIM:
            raise PronunciationScoringError(
                "CTC-GOP and pronunciation feature schemas disagree"
            )
        self._load_gopt()
        self._load_arabic_models()
        model_dir = self.backend_dir / "pretrained_models" / "wav2vec2_xlsr53_cmu39_ctc"
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
            if int(metadata["version"]) != GOPT_MODEL_FORMAT_REVISION:
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
            self.backend_dir / "pretrained_models" / "arabic_pronunciation_ctc_v3"
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
            if int(metadata["version"]) != ARABIC_MODEL_FORMAT_REVISION:
                raise ValueError("unsupported Arabic pronunciation model version")
            calibration = metadata["calibration"]
            self.probability_slope = float(calibration["error"]["slope"])
            self.probability_intercept = float(calibration["error"]["intercept"])
            self.severe_probability_slope = float(calibration["severe_error"]["slope"])
            self.severe_probability_intercept = float(
                calibration["severe_error"]["intercept"]
            )
            self.severity_slope = float(calibration["phone_severity"]["slope"])
            self.severity_intercept = float(calibration["phone_severity"]["intercept"])
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
            self.red_minimum_severity = float(status_policy["red_min_error_severity"])
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
        if (
            self.phone_classifier.get_booster().num_features()
            != LEGACY_PHONE_FEATURE_DIM
        ):
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
                np.clip(
                    round(float(np.average(values, weights=weights)) * 50.0), 0, 100
                )
            )

        return percent(fluency), percent(prosody)
