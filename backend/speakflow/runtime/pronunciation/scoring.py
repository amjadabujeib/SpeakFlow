"""Runtime scoring and response assembly for the CTC-GOPT scorer."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from speakflow.runtime.pronunciation.gop import CtcGopError, CtcGopResult
from speakflow.runtime.pronunciation.features import (
    GOP_FEATURE_DIM,
    build_ctc_evidence_features,
    build_phone_context_features,
)
from speakflow.runtime.pronunciation.core import (
    GOPT_PHONE_TO_ID,
    MAX_GOPT_PHONES,
    OVERALL_SCORE_WEIGHTS,
    WORD_OVERALL_SCORE_WEIGHTS,
    PronunciationScoringError,
    arpabet_to_ipa,
    calculate_overall_score,
    calculate_word_overall_score,
)


SCORING_METHOD = "xlsr53_ctc_gop_arabic_loso_severity_gopt_v3"


class Wav2Vec2ScoringMixin:
    """Scores one utterance using models initialized by the host scorer."""

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
