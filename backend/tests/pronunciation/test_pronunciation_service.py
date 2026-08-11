import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

from speakflow.config import BACKEND_ROOT
from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    GOPT_PHONE_TO_ID,
    CmuCanonicalizer,
    PronunciationScoringError,
    calculate_overall_score,
    calculate_word_overall_score,
    normalized_english_words,
)
from speakflow.features.pronunciation.infrastructure.acoustic.features import (
    GOP_FEATURE_DIM,
)
from speakflow.features.pronunciation.infrastructure.acoustic.gop import (
    CTC_GOP_FEATURE_DIM,
    CtcGopResult,
)
from speakflow.features.pronunciation.infrastructure.acoustic.scoring import (
    SCORING_METHOD,
)
from speakflow.features.pronunciation.infrastructure.acoustic.service import (
    Wav2Vec2GoptScorer,
)


class CanonicalizerTests(unittest.TestCase):
    def test_car_uses_cmu_arpabet_and_ipa(self):
        result = CmuCanonicalizer().canonicalize("car")

        self.assertEqual(result.phones, ("K", "AA1", "R"))
        self.assertEqual(result.pure_phones, ("K", "AA", "R"))
        self.assertEqual(result.ipa_phones, ("k", "ˈɑ", "ɹ"))

    def test_unknown_word_uses_the_local_neural_g2p(self):
        result = CmuCanonicalizer().canonicalize("uncharacteristically")

        self.assertGreater(len(result.phones), 10)
        self.assertTrue(all(result.phones))

    def test_sentence_can_exceed_one_gopt_window(self):
        result = CmuCanonicalizer().canonicalize(
            "I would like to practice a complete sentence and then practice another sentence"
        )

        self.assertGreater(len(result.phones), 50)

    def test_written_numbers_and_hyphens_have_consistent_words(self):
        text = "In 2026, say hello-world"
        self.assertEqual(
            normalized_english_words(text),
            ("in", "twenty", "twenty", "six", "say", "hello", "world"),
        )
        result = CmuCanonicalizer().canonicalize(text)
        self.assertEqual(
            tuple(word.lower() for word in result.words),
            normalized_english_words(text),
        )

    def test_oov_uppercase_acronym_is_spelled_as_letters(self):
        result = CmuCanonicalizer().canonicalize("ChatGPT")

        self.assertEqual(result.words, ("CHAT", "GPT"))
        self.assertEqual(
            result.word_phones[1],
            ("JH", "IY1", "P", "IY1", "T", "IY1"),
        )

    def test_single_word_longer_than_a_gopt_window_is_rejected_cleanly(self):
        with self.assertRaisesRegex(
            PronunciationScoringError,
            "single word supports at most 50",
        ):
            CmuCanonicalizer().canonicalize("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_score_helpers_retain_visible_contract(self):
        scores = {
            "accuracy": 80,
            "fluency": 70,
            "prosody": 60,
            "completeness": 50,
        }
        self.assertEqual(calculate_overall_score(scores), 69)
        self.assertEqual(
            calculate_word_overall_score(scores),
            round((80 * 0.8) + (60 * 0.2)),
        )


class FakeExtractor:
    def __init__(self, likely=None):
        self.likely = likely

    def extract(self, audio_path, canonical_phones):
        count = len(canonical_phones)
        likely = (
            tuple(self.likely) if self.likely is not None else tuple(canonical_phones)
        )
        return CtcGopResult(
            features=np.zeros((count, CTC_GOP_FEATURE_DIM), dtype=np.float32),
            likely_phones=likely,
            likely_phone_probabilities=np.full(count, 0.8, dtype=np.float32),
            deletion_probabilities=np.full(count, 0.01, dtype=np.float32),
        )


class FakeGopt(torch.nn.Module):
    def forward(self, features, phone_ids):
        batch = features.shape[0]
        utterance = [
            torch.full((batch, 1), value, dtype=torch.float32)
            for value in (1.6, 2.0, 1.5, 1.4, 1.5)
        ]
        phone = torch.zeros(
            (batch, features.shape[1], 1),
            dtype=torch.float32,
        )
        return (*utterance, phone, phone, phone, phone)


class FakeClassifier:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, features):
        count = len(features)
        values = np.resize(np.asarray(self.probability, dtype=np.float64), count)
        return np.column_stack((1.0 - values, values))


class FakeRegressor:
    def __init__(self, severity):
        self.severity = severity

    def predict(self, features):
        return np.resize(np.asarray(self.severity, dtype=np.float64), len(features))


def fake_scorer(
    *,
    error=(0.02,),
    severe=(0.01,),
    severity=(0.05,),
    likely=None,
) -> Wav2Vec2GoptScorer:
    scorer = object.__new__(Wav2Vec2GoptScorer)
    scorer.backend_dir = Path(".")
    scorer.extractor = FakeExtractor(likely)
    scorer.canonicalizer = CmuCanonicalizer()
    scorer.model = FakeGopt().eval()
    scorer.gopt_norm_mean = np.zeros(GOP_FEATURE_DIM, dtype=np.float32)
    scorer.gopt_norm_std = np.ones(GOP_FEATURE_DIM, dtype=np.float32)
    scorer.xgb_norm_mean = np.zeros(GOP_FEATURE_DIM, dtype=np.float32)
    scorer.xgb_norm_std = np.ones(GOP_FEATURE_DIM, dtype=np.float32)
    scorer.phone_classifier = FakeClassifier(error)
    scorer.phone_severe_classifier = FakeClassifier(severe)
    scorer.phone_severity_model = FakeRegressor(severity)
    scorer.probability_slope = 1.0
    scorer.probability_intercept = 0.0
    scorer.severe_probability_slope = 1.0
    scorer.severe_probability_intercept = 0.0
    scorer.severity_slope = 1.0
    scorer.severity_intercept = 0.0
    scorer.quality_severity_regressor_weight = 1.0
    scorer.global_red_severe_probability = 0.30
    scorer.red_severe_probability_by_phone_id = {}
    scorer.warning_probability_threshold = 0.15
    scorer.warning_severity_threshold = 0.15
    scorer.red_minimum_severity = 0.30
    scorer.substitution_confidence_threshold = 0.20
    return scorer


class Wav2Vec2ScorerTests(unittest.TestCase):
    def test_default_model_root_is_stable_across_module_moves(self):
        with (
            patch.object(Wav2Vec2GoptScorer, "_load_gopt"),
            patch.object(Wav2Vec2GoptScorer, "_load_arabic_models"),
        ):
            scorer = Wav2Vec2GoptScorer(extractor=FakeExtractor())

        self.assertEqual(scorer.backend_dir, BACKEND_ROOT)
        self.assertTrue((scorer.backend_dir / "pretrained_models").is_dir())

    def test_missing_ctc_assets_fail_closed_without_loading_legacy_models(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                PronunciationScoringError,
                "CTC-GOPT assets are missing",
            ):
                Wav2Vec2GoptScorer(Path(directory))

    def test_production_contract_combines_ctc_xgboost_and_gopt(self):
        result = fake_scorer().score("unused.wav", "car")

        self.assertEqual(result["scoring_method"], SCORING_METHOD)
        self.assertEqual(
            [item["arpabet"] for item in result["analysis"]],
            ["K", "AA1", "R"],
        )
        self.assertEqual(
            set(result["scores"]),
            {
                "accuracy",
                "completeness",
                "fluency",
                "prosody",
                "overall_score",
            },
        )
        self.assertEqual(result["scores"]["completeness"], 100)
        self.assertEqual(
            result["scores"]["overall_score"],
            calculate_word_overall_score(result["scores"]),
        )
        for item in result["analysis"]:
            self.assertIn("likely_arpabet", item)
            self.assertIn("deletion_probability", item)

    def test_confident_substitution_is_grounded_in_ctc_counterfactuals(self):
        scorer = fake_scorer(
            error=(0.4,),
            severe=(0.9,),
            severity=(0.5,),
            likely=("S", "AA", "R"),
        )

        result = scorer.score("unused.wav", "car")

        first = result["analysis"][0]
        self.assertEqual(first["status"], "incorrect")
        self.assertEqual(first["error_type"], "substitution")
        self.assertEqual(first["likely_arpabet"], "S")
        self.assertEqual(first["likely_ipa"], "s")
        self.assertIn("sounded closer to /s/", result["feedback"])

    def test_confident_substitution_promotes_warning_to_actionable_error(self):
        scorer = fake_scorer(
            error=(0.20,),
            severe=(0.10,),
            severity=(0.20,),
            likely=("S", "AA", "R"),
        )

        result = scorer.score("unused.wav", "car")

        first = result["analysis"][0]
        self.assertEqual(first["status"], "incorrect")
        self.assertTrue(first["replacement_verified"])
        self.assertEqual(first["likely_ipa"], "s")
        self.assertEqual(result["acoustic_flagged_phones"][0]["phone_index"], 0)

    def test_unverified_closest_phone_does_not_become_a_definite_diagnosis(self):
        scorer = fake_scorer(
            error=(0.20,),
            severe=(0.10,),
            severity=(0.20,),
            likely=("S", "AA", "R"),
        )
        scorer.substitution_confidence_threshold = 1.0

        result = scorer.score("unused.wav", "car")

        first = result["analysis"][0]
        self.assertEqual(first["status"], "warning")
        self.assertFalse(first["replacement_verified"])
        self.assertIsNone(first["likely_ipa"])
        self.assertEqual(first["closest_ipa"], "s")

    def test_green_warning_and_red_states_are_distinct(self):
        scorer = fake_scorer(
            error=(0.02, 0.15, 0.20, 0.40),
            severe=(0.01, 0.01, 0.20, 0.90),
            severity=(0.05, 0.15, 0.20, 0.50),
        )

        result = scorer.score("unused.wav", "test")

        self.assertEqual(
            [item["status"] for item in result["analysis"]],
            ["correct", "correct", "warning", "incorrect"],
        )
        self.assertEqual(len(result["acoustic_flagged_phones"]), 1)
        self.assertEqual(len(result["acoustic_uncertain_phones"]), 1)

    def test_long_sentence_is_batched_at_word_boundaries(self):
        scorer = fake_scorer()
        target = (
            "I would like to practice a complete sentence and then practice "
            "another sentence"
        )
        pronunciation = scorer.canonicalizer.canonicalize(target)

        result = scorer.score("unused.wav", target)

        self.assertGreater(len(pronunciation.phones), 50)
        self.assertEqual(len(result["analysis"]), len(pronunciation.phones))
        self.assertEqual(len(result["word_scores"]), len(pronunciation.words))

    def test_non_finite_model_output_is_rejected(self):
        scorer = fake_scorer(severity=(0.1, np.nan, 0.2))

        with self.assertRaisesRegex(
            PronunciationScoringError,
            "malformed values",
        ):
            scorer.score("unused.wav", "car")

    def test_phone_mapping_still_contains_all_cmu39_phones(self):
        self.assertEqual(len(GOPT_PHONE_TO_ID), 39)
        self.assertEqual(set(GOPT_PHONE_TO_ID.values()), set(range(39)))


if __name__ == "__main__":
    unittest.main()
