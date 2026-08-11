import unittest

from speakflow.features.pronunciation.domain import (
    annotate_phone_verification,
    assess_pronunciation_evidence,
    learner_attention_evidence,
    parse_focus_ipa,
)


class PronunciationAssessmentTests(unittest.TestCase):
    @staticmethod
    def phone(char, status, *, expected="P", likely="P", confidence=99.0):
        return {
            "char": char,
            "status": status,
            "arpabet": expected,
            "likely_arpabet": likely,
            "likely_phone_probability": confidence,
        }

    def test_parses_decorated_and_multiple_ipa_targets(self):
        self.assertEqual(parse_focus_ipa("/ˈp/ and /b/"), ("p", "b"))

    def test_orange_evidence_is_advisory(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "warning")],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["outcome"], "passed")
        self.assertEqual(result["acoustic_uncertain_phone_count"], 1)

    def test_unsupported_explicit_focus_never_falls_back_to_all_phones(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "correct")],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/ˈ/",
        )

        self.assertIsNone(result["passed"])
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertEqual(result["evaluated_phone_count"], 0)

    def test_verified_orange_phone_displays_as_correct_without_losing_raw_status(self):
        result = annotate_phone_verification(
            [self.phone("p", "warning")],
            transcript_verified=True,
            transcript_contradicted=False,
        )[0]

        self.assertEqual(result["display_status"], "correct")
        self.assertEqual(result["acoustic_status"], "warning")
        self.assertEqual(
            result["verification_reason"],
            "transcript_and_phone_identity_agree",
        )

    def test_two_model_alternative_displays_as_correction(self):
        result = annotate_phone_verification(
            [self.phone("p", "warning", likely="B")],
            transcript_verified=False,
            transcript_contradicted=True,
        )[0]

        self.assertEqual(result["display_status"], "incorrect")
        self.assertEqual(result["acoustic_status"], "warning")
        self.assertEqual(
            result["verification_reason"],
            "transcript_and_phone_identity_contradict",
        )

    def test_one_model_disagreement_remains_uncertain(self):
        result = annotate_phone_verification(
            [self.phone("p", "warning", likely="B")],
            transcript_verified=True,
            transcript_contradicted=False,
        )[0]

        self.assertEqual(result["display_status"], "warning")

    def test_coaching_excludes_raw_orange_promoted_to_display_green(self):
        analysis = annotate_phone_verification(
            [
                self.phone("p", "warning"),
                self.phone("ə", "warning", expected="AH", likely="ER"),
            ],
            transcript_verified=True,
            transcript_contradicted=False,
        )

        attention = learner_attention_evidence(analysis)

        self.assertEqual([item["char"] for item in attention], ["ə"])
        self.assertEqual(attention[0]["status"], "warning")
        self.assertEqual(attention[0]["phoneme"], "ə")

    def test_only_the_assigned_sound_blocks_a_targeted_drill(self):
        result = assess_pronunciation_evidence(
            analysis=[
                self.phone("p", "correct"),
                self.phone(
                    "ɚ",
                    "incorrect",
                    expected="ER",
                    likely="AH",
                ),
            ],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["evaluated_phone_count"], 1)

    def test_confirmed_target_error_still_requires_work(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "incorrect", likely="B")],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["outcome"], "needs_work")

    def test_unverified_word_is_inconclusive(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "warning")],
            completeness=100,
            transcript_verified=False,
            focus_ipa="/p/",
        )

        self.assertIsNone(result["passed"])
        self.assertEqual(result["outcome"], "inconclusive")

    def test_incomplete_target_cannot_pass(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "correct")],
            completeness=89,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["outcome"], "incomplete")

    def test_orange_alternative_phone_is_inconclusive(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "warning", likely="B")],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertIsNone(result["passed"])
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertEqual(result["unsupported_phone_count"], 1)

    def test_weak_phone_identity_confidence_is_inconclusive(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "warning", confidence=49.9)],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertIsNone(result["passed"])
        self.assertEqual(result["supported_phone_count"], 0)

    def test_omitted_target_phone_cannot_pass(self):
        result = assess_pronunciation_evidence(
            analysis=[self.phone("p", "omitted")],
            completeness=100,
            transcript_verified=True,
            focus_ipa="/p/",
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["outcome"], "incomplete")
        self.assertEqual(result["acoustic_omitted_phone_count"], 1)


if __name__ == "__main__":
    unittest.main()
