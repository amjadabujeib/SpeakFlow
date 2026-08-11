import asyncio
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from speakflow.features.learning_plan.engine.pronunciation_attempt_policy import (
    pronunciation_evidence_weight,
    should_record_pronunciation_evidence,
)
from speakflow.features.learning_plan.engine.service_progress import (
    _pronunciation_activity_mastery_score,
    _pronunciation_activity_progress,
)
from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    LocalG2pCanonicalizer,
)
from tests.runtime.runtime_test_support import (
    FAKE_SPEECH,
    FakeScorer,
    FakeUpload,
    main,
    model_runtime,
    pronunciation_endpoints,
)


class PronunciationContractConsistencyTests(unittest.TestCase):
    def test_first_conclusive_recording_can_create_evidence_after_uncertainty(self):
        inconclusive = SimpleNamespace(
            response={"pronunciation": {"target": "paper"}}
        )

        self.assertTrue(
            should_record_pronunciation_evidence(
                [inconclusive],
                target="paper",
                evidence_allowed=True,
                attempt_kind="initial",
            )
        )
        inconclusive.response["_mastery_evidence_recorded"] = True
        self.assertFalse(
            should_record_pronunciation_evidence(
                [inconclusive],
                target="paper",
                evidence_allowed=True,
                attempt_kind="initial",
            )
        )
        self.assertTrue(
            should_record_pronunciation_evidence(
                [inconclusive],
                target="bag",
                evidence_allowed=True,
                attempt_kind="initial",
            )
        )

    def test_multi_target_drill_shares_one_activity_evidence_weight(self):
        self.assertAlmostEqual(
            pronunciation_evidence_weight(
                base_weight=1.5,
                assigned_target_count=3,
            ),
            0.5,
        )

    def test_transcript_relation_distinguishes_homophone_from_near_spelling(self):
        scorer = SimpleNamespace(canonicalizer=LocalG2pCanonicalizer())
        with patch.object(model_runtime, "pronunciation_scorer", scorer):
            self.assertEqual(
                main._single_word_transcript_relation("two", "too"),
                "phonetic_compatible",
            )
            self.assertEqual(
                main._single_word_transcript_relation("paper", "baber"),
                "near_match",
            )

    def test_single_model_alternative_is_guidance_not_a_correction(self):
        with (
            patch.object(
                model_runtime,
                "pronunciation_scorer",
                FakeScorer(uncertain=True, first_phone_alternative=True),
            ),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(result["analysis"][0]["display_status"], "warning")
        self.assertEqual(result["feedback_kind"], "guidance")
        self.assertEqual(result["learner_attention_phones"][0]["char"], "k")
        self.assertEqual(
            result["phone_summaries"]["acoustic"]["uncertain_phone_count"], 1
        )
        self.assertEqual(
            result["phone_summaries"]["learner_facing"]["uncertain_phone_count"], 1
        )

    def test_progress_and_score_distinguish_verified_from_unverified_targets(self):
        activity = {
            "id": "sound_check",
            "type": "pronunciation_drill",
            "data": {"practice_items": ["paper", "bag"]},
        }
        lesson = SimpleNamespace(
            id=uuid.uuid4(),
            content={"content": {"activities": [activity]}},
        )
        attempts = [
            SimpleNamespace(
                activity_id="sound_check",
                correct=True,
                response={"pronunciation": {"target": "paper"}},
            ),
            SimpleNamespace(
                activity_id="sound_check",
                correct=None,
                response={
                    "pronunciation": {
                        "target": "bag",
                        "completion_accepted": True,
                    }
                },
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = attempts

        progress = _pronunciation_activity_progress(session, lesson)
        score = _pronunciation_activity_mastery_score(session, lesson, activity)

        self.assertEqual(
            progress["sound_check"],
            {
                "verified_target_keys": ["paper"],
                "unverified_target_keys": ["bag"],
            },
        )
        self.assertEqual(score, 50)
