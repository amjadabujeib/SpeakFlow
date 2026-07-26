import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pronunciation_service import (
    CmuCanonicalizer,
    KaldiGoptScorer,
    PronunciationScoringError,
    _parse_kaldi_matrix,
    calculate_overall_score,
    calculate_word_overall_score,
    conservative_phone_aggregate,
    normalized_english_words,
    phone_quality_scores,
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
        self.assertTrue(all(phone for phone in result.phones))

    def test_sentence_can_exceed_one_gopt_window(self):
        result = CmuCanonicalizer().canonicalize(
            "I would like to practice a complete sentence and then practice another sentence"
        )

        self.assertGreater(len(result.phones), 50)

    def test_written_numbers_and_hyphens_have_consistent_words(self):
        self.assertEqual(
            normalized_english_words("In 2026, say hello-world"),
            ("in", "twenty", "twenty", "six", "say", "hello", "world"),
        )
        result = CmuCanonicalizer().canonicalize("In 2026, say hello-world")
        self.assertEqual(tuple(word.lower() for word in result.words), normalized_english_words("In 2026, say hello-world"))

    def test_oov_uppercase_acronym_is_spelled_as_letters(self):
        result = CmuCanonicalizer().canonicalize("ChatGPT")

        self.assertEqual(result.words, ("CHAT", "GPT"))
        self.assertEqual(result.word_phones[1], ("JH", "IY1", "P", "IY1", "T", "IY1"))

    def test_single_word_longer_than_a_gopt_window_is_rejected_cleanly(self):
        with self.assertRaisesRegex(
            PronunciationScoringError, "single word supports at most 50"
        ):
            CmuCanonicalizer().canonicalize("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_overall_score_matches_the_four_visible_metrics(self):
        scores = {"accuracy": 80, "fluency": 70, "prosody": 60, "completeness": 50}

        self.assertEqual(calculate_overall_score(scores), 69)

    def test_color_boundaries_map_to_eighty_and_sixty_quality(self):
        scores = phone_quality_scores(np.asarray([0.0, 0.15, 0.30, 1.0]))

        self.assertEqual(scores[0], 100)
        self.assertAlmostEqual(scores[1], 80, places=4)
        self.assertAlmostEqual(scores[2], 60, places=4)
        self.assertEqual(scores[3], 0)

    def test_weak_phone_pulls_down_word_accuracy(self):
        score = conservative_phone_aggregate([95, 94, 37])

        self.assertLess(score, 70)
        self.assertGreater(score, 55)

    def test_parses_phone_vectors_as_85_values(self):
        values = " ".join(str(index) for index in range(85))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.txt"
            path.write_text(f"practice.0 [ {values} ]\n", encoding="utf-8")
            matrix = _parse_kaldi_matrix(path)

        self.assertEqual(matrix.shape, (1, 85))
        self.assertEqual(matrix[0, 0], 0)
        self.assertEqual(matrix[0, -1], 84)

    def test_production_routing_combines_arabic_classifier_and_gopt(self):
        backend_dir = Path(__file__).resolve().parent
        scorer = KaldiGoptScorer(backend_dir)
        features = np.zeros((3, 84), dtype=np.float32)

        with patch.object(scorer, "_extract", return_value=features):
            result = scorer.score("unused.wav", "car")

        self.assertEqual(result["scoring_method"], "kaldi_gop_arabic_loso_severity_gopt_v2")
        self.assertEqual([item["arpabet"] for item in result["analysis"]], ["K", "AA1", "R"])
        self.assertEqual(set(result["scores"]), {"accuracy", "completeness", "fluency", "prosody", "overall_score", "gop_score"})
        self.assertEqual(result["scores"]["completeness"], 100)
        self.assertEqual(result["scores"]["gop_score"], calculate_word_overall_score(result["scores"]))
        self.assertEqual(result["scores"]["overall_score"], result["scores"]["gop_score"])
        for value in result["scores"].values():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)
        for item in result["analysis"]:
            self.assertIn("correct_probability", item)
            self.assertIn("error_probability", item)
            self.assertIn("error_severity", item)

    def test_recalibration_uses_green_warning_and_red_states(self):
        backend_dir = Path(__file__).resolve().parent
        scorer = KaldiGoptScorer(backend_dir)
        features = np.zeros((4, 84), dtype=np.float32)
        probabilities = np.asarray([
            [0.98, 0.02],
            [0.85, 0.15],
            [0.80, 0.20],
            [0.60, 0.40],
        ])
        severe_probabilities = np.asarray([
            [0.99, 0.01],
            [0.99, 0.01],
            [0.80, 0.20],
            [0.10, 0.90],
        ])
        severities = np.asarray([0.05, 0.15, 0.20, 0.50])

        with (
            patch.object(scorer, "_extract", return_value=features),
            patch.object(scorer.phone_classifier, "predict_proba", return_value=probabilities),
            patch.object(
                scorer.phone_severe_classifier,
                "predict_proba",
                return_value=severe_probabilities,
            ),
            patch.object(
                scorer.phone_severity_model, "predict", return_value=severities
            ),
            patch.object(scorer, "probability_slope", 1.0),
            patch.object(scorer, "probability_intercept", 0.0),
            patch.object(scorer, "severe_probability_slope", 1.0),
            patch.object(scorer, "severe_probability_intercept", 0.0),
            patch.object(scorer, "severity_slope", 1.0),
            patch.object(scorer, "severity_intercept", 0.0),
            patch.object(scorer, "quality_severity_regressor_weight", 1.0),
            patch.object(scorer, "global_red_severe_probability", 0.30),
            patch.object(scorer, "red_severe_probability_by_phone_id", {}),
        ):
            result = scorer.score("unused.wav", "test")

        self.assertEqual(
            [item["status"] for item in result["analysis"]],
            ["correct", "correct", "warning", "incorrect"],
        )
        self.assertEqual(
            [item["error_probability"] for item in result["analysis"]],
            [2.0, 15.0, 20.0, 40.0],
        )
        self.assertEqual(
            [item["error_severity"] for item in result["analysis"]],
            [5.0, 15.0, 20.0, 50.0],
        )
        self.assertEqual(result["word_scores"][0]["accuracy"], 78)
        self.assertEqual(len(result["flagged_phones"]), 1)
        self.assertEqual(len(result["uncertain_phones"]), 1)

    def test_production_routing_batches_a_long_sentence(self):
        backend_dir = Path(__file__).resolve().parent
        scorer = KaldiGoptScorer(backend_dir)
        target = "I would like to practice a complete sentence and then practice another sentence"
        pronunciation = scorer.canonicalizer.canonicalize(target)
        features = np.zeros((len(pronunciation.phones), 84), dtype=np.float32)

        with patch.object(scorer, "_extract", return_value=features):
            result = scorer.score("unused.wav", target)

        self.assertEqual(len(result["analysis"]), len(pronunciation.phones))
        self.assertEqual(len(result["word_scores"]), len(pronunciation.words))

    def test_non_finite_v2_model_output_fails_instead_of_scoring(self):
        backend_dir = Path(__file__).resolve().parent
        scorer = KaldiGoptScorer(backend_dir)
        features = np.zeros((3, 84), dtype=np.float32)

        with (
            patch.object(scorer, "_extract", return_value=features),
            patch.object(
                scorer.phone_severity_model,
                "predict",
                return_value=np.asarray([0.1, np.nan, 0.2]),
            ),
        ):
            with self.assertRaisesRegex(
                PronunciationScoringError, "malformed values"
            ):
                scorer.score("unused.wav", "car")

    def test_quality_blends_error_likelihood_with_regressor_severity(self):
        backend_dir = Path(__file__).resolve().parent
        scorer = KaldiGoptScorer(backend_dir)
        features = np.zeros((2, 84), dtype=np.float32)
        any_error = np.asarray([[0.95, 0.05], [0.55, 0.45]])
        severe_error = np.asarray([[0.99, 0.01], [0.99, 0.01]])

        with (
            patch.object(scorer, "_extract", return_value=features),
            patch.object(
                scorer.phone_classifier, "predict_proba", return_value=any_error
            ),
            patch.object(
                scorer.phone_severe_classifier,
                "predict_proba",
                return_value=severe_error,
            ),
            patch.object(
                scorer.phone_severity_model,
                "predict",
                return_value=np.asarray([0.10, 0.10]),
            ),
            patch.object(scorer, "probability_slope", 1.0),
            patch.object(scorer, "probability_intercept", 0.0),
            patch.object(scorer, "severe_probability_slope", 1.0),
            patch.object(scorer, "severe_probability_intercept", 0.0),
            patch.object(scorer, "severity_slope", 1.0),
            patch.object(scorer, "severity_intercept", 0.0),
            patch.object(scorer, "quality_severity_regressor_weight", 0.5),
        ):
            result = scorer.score("unused.wav", "we")

        self.assertEqual(
            [item["model_error_severity"] for item in result["analysis"]],
            [10.0, 10.0],
        )
        self.assertEqual(
            [item["error_severity"] for item in result["analysis"]],
            [7.5, 27.5],
        )
        self.assertGreater(
            result["analysis"][0]["score"], result["analysis"][1]["score"]
        )


if __name__ == "__main__":
    unittest.main()
