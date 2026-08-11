from speakflow.features.learning_plan.engine.pronunciation_attempt_policy import (
    should_accept_inconclusive_progress,
)
from tests.learning_plan.support.plp_test_support import (
    ActivityAttemptInput,
    LearningPlanEngine,
    MagicMock,
    Mock,
    PlpConflictError,
    PlpInvalidAttemptError,
    SimpleNamespace,
    _grade_activity,
    _pronunciation_activity_complete,
    _verified_completed_activity_ids,
    patch,
    unittest,
    uuid,
)


class PlpAttemptContractTests(unittest.TestCase):
    def test_pronunciation_drill_requires_trusted_acoustic_result(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {
                "ipa": "/θ/",
                "practice_items": ["think", "Thursday"],
            },
        }
        with self.assertRaisesRegex(
            PlpInvalidAttemptError,
            "record and score",
        ):
            _grade_activity(activity, ActivityAttemptInput())

        passed, score, explanation, evidence = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "think",
                "accuracy": 88,
                "completeness": 100,
                "transcript_verified": True,
                "analysis": [
                    {
                        "char": "θ",
                        "arpabet": "TH",
                        "status": "correct",
                        "score": 88,
                        "likely_arpabet": "TH",
                        "likely_phone_probability": 99.0,
                    },
                ],
            },
        )
        self.assertTrue(passed)
        self.assertEqual(score, 100)
        self.assertEqual(
            90,
            round((88 * 0.8) + (100 * 0.2)),
        )
        self.assertIn("verified", explanation)
        self.assertTrue(evidence)

        passed, score, explanation, _ = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "think",
                "accuracy": 60,
                "completeness": 100,
                "transcript_verified": True,
                "analysis": [
                    {
                        "char": "θ",
                        "arpabet": "TH",
                        "status": "incorrect",
                        "score": 60,
                        "likely_arpabet": "T",
                        "likely_phone_probability": 99.0,
                    },
                ],
            },
        )
        self.assertFalse(passed)
        self.assertEqual(score, 0)
        self.assertIn("Try again", explanation)

    def test_uncertain_paper_model_output_does_not_block_a_p_lesson(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {"ipa": "/p/", "practice_items": ["paper"]},
        }

        passed, score, explanation, evidence = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "paper",
                "accuracy": 82,
                "completeness": 100,
                "transcript_verified": True,
                "analysis": [
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "warning",
                        "score": 76,
                        "likely_arpabet": "P",
                        "likely_phone_probability": 99.9,
                    },
                    {
                        "char": "ˈeɪ",
                        "arpabet": "EY1",
                        "status": "correct",
                        "score": 87,
                        "likely_arpabet": "EY",
                        "likely_phone_probability": 99.6,
                    },
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "correct",
                        "score": 89,
                        "likely_arpabet": "P",
                        "likely_phone_probability": 100.0,
                    },
                    {
                        "char": "ɚ",
                        "arpabet": "ER0",
                        "status": "warning",
                        "score": 76,
                        "likely_arpabet": "ER",
                        "likely_phone_probability": 99.7,
                    },
                ],
            },
        )

        self.assertTrue(passed)
        self.assertEqual(score, 100)
        self.assertIn("/p/ verified", explanation)
        self.assertIn("not a pass threshold", explanation)
        self.assertTrue(evidence)

    def test_unverified_transcript_is_inconclusive_not_wrong(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {"ipa": "/p/", "practice_items": ["paper"]},
        }

        passed, _, explanation, evidence = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "paper",
                "accuracy": 82,
                "completeness": 100,
                "transcript_verified": False,
                "analysis": [
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "warning",
                        "score": 76,
                        "likely_arpabet": "P",
                        "likely_phone_probability": 99.9,
                    },
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "correct",
                        "score": 89,
                        "likely_arpabet": "P",
                        "likely_phone_probability": 100.0,
                    },
                ],
            },
        )

        self.assertIsNone(passed)
        self.assertIn("not marked as a pronunciation mistake", explanation)
        self.assertFalse(evidence)

    def test_alternative_target_phone_is_inconclusive_without_red_evidence(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {"ipa": "/p/", "practice_items": ["paper"]},
        }

        passed, _, explanation, evidence = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "paper",
                "accuracy": 70,
                "completeness": 100,
                "transcript_verified": True,
                "analysis": [
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "warning",
                        "score": 65,
                        "likely_arpabet": "B",
                        "likely_phone_probability": 99.0,
                    },
                    {
                        "char": "p",
                        "arpabet": "P",
                        "status": "correct",
                        "score": 90,
                        "likely_arpabet": "P",
                        "likely_phone_probability": 99.0,
                    },
                ],
            },
        )

        self.assertIsNone(passed)
        self.assertIn("did not agree strongly enough", explanation)
        self.assertIn("not a confirmed mistake", explanation)
        self.assertFalse(evidence)

    def test_legacy_click_through_is_not_a_verified_pronunciation_pass(self):
        lesson = SimpleNamespace(
            id=uuid.uuid4(),
            content={
                "content": {
                    "activities": [
                        {
                            "id": "sound_check",
                            "type": "pronunciation_drill",
                            "required": True,
                        },
                        {
                            "id": "technique",
                            "type": "concept",
                            "required": True,
                        },
                    ]
                }
            },
        )
        progress = SimpleNamespace(completed_activity_ids=["sound_check", "technique"])
        session = Mock()
        session.scalars.return_value.all.return_value = []

        visible = _verified_completed_activity_ids(session, lesson, progress)

        self.assertEqual(visible, ["technique"])

    def test_pronunciation_activity_requires_every_assigned_target(self):
        activity = {
            "id": "sound_check",
            "type": "pronunciation_drill",
            "data": {
                "practice_items": [
                    "project plan",
                    {"text": "payment problem"},
                    "Please print the proposal.",
                ]
            },
        }

        def passed(target):
            return SimpleNamespace(
                activity_id="sound_check",
                correct=True,
                response={
                    "pronunciation": {
                        "target": target,
                        "accuracy": 90,
                        "completeness": 100,
                    }
                },
            )

        attempts = [passed("project plan"), passed("payment problem")]
        self.assertFalse(_pronunciation_activity_complete(activity, attempts))

        attempts.append(passed("Please print the proposal."))
        self.assertTrue(_pronunciation_activity_complete(activity, attempts))

    def test_inconclusive_retry_escape_completes_without_claiming_correctness(self):
        activity = {
            "id": "sound_check",
            "type": "pronunciation_drill",
            "data": {"practice_items": ["paper"]},
        }
        accepted = SimpleNamespace(
            activity_id="sound_check",
            correct=None,
            response={
                "pronunciation": {
                    "target": "paper",
                    "accuracy": 70,
                    "completeness": 100,
                    "completion_accepted": True,
                }
            },
        )

        self.assertTrue(_pronunciation_activity_complete(activity, [accepted]))
        self.assertIsNone(accepted.correct)

    def test_third_inconclusive_attempt_unlocks_progress_for_same_target(self):
        def attempt(target, correct=None):
            return SimpleNamespace(
                correct=correct,
                response={"pronunciation": {"target": target}},
            )

        self.assertFalse(
            should_accept_inconclusive_progress(
                [attempt("paper")],
                "paper",
            )
        )
        self.assertTrue(
            should_accept_inconclusive_progress(
                [attempt("paper"), attempt("PAPER!")],
                "paper",
            )
        )
        self.assertFalse(
            should_accept_inconclusive_progress(
                [attempt("paper"), attempt("pen"), attempt("paper", False)],
                "paper",
            )
        )

    def test_first_submission_marked_correction_never_records_mastery_evidence(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            skill_ids=["listening.b1.core"],
            content={
                "content": {
                    "activities": [
                        {
                            "id": activity_id,
                            "type": "multiple_choice",
                            "required": True,
                            "skill_ids": ["listening.b1.core"],
                            "data": {
                                "options": [
                                    {"id": "a", "text": "Answer"},
                                    {"id": "b", "text": "Distractor"},
                                    {"id": "c", "text": "Distractor two"},
                                ],
                                "correct_option_id": "a",
                                "explanation": "That detail is stated directly.",
                            },
                        }
                    ]
                }
            },
        )
        session = Mock()
        session.get.return_value = None
        session.scalar.side_effect = [0, 100]
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = LearningPlanEngine()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        service._update_lesson_completion = Mock(return_value=False)
        try:
            with (
                patch(
                    "speakflow.features.learning_plan.engine.service_attempts.session_scope",
                    return_value=context,
                ),
                patch(
                    "speakflow.features.learning_plan.engine.service_attempts.SkillEvidence"
                ) as skill_evidence,
            ):
                result = service.record_attempt(
                    activity_id,
                    ActivityAttemptInput(
                        attempt_kind="correction",
                        selected_option_id="a",
                    ),
                )
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertTrue(result.first_attempt)
        self.assertFalse(result.mastery_evidence_recorded)
        skill_evidence.assert_not_called()

    def test_submission_id_cannot_be_reused_for_another_activity(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            skill_ids=["listening.b1.core"],
            content={
                "content": {
                    "activities": [
                        {
                            "id": activity_id,
                            "type": "multiple_choice",
                            "required": True,
                            "skill_ids": ["listening.b1.core"],
                            "data": {
                                "options": [
                                    {"id": "a", "text": "Answer"},
                                    {"id": "b", "text": "Distractor"},
                                ],
                                "correct_option_id": "a",
                                "explanation": "The detail is stated directly.",
                            },
                        }
                    ]
                }
            },
        )
        session = Mock()
        session.scalar.return_value = Mock(
            lesson_id=uuid.uuid4(),
            activity_id="another_activity",
        )
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = LearningPlanEngine()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_attempts.session_scope",
                return_value=context,
            ):
                with self.assertRaises(PlpConflictError):
                    service.record_attempt(
                        activity_id,
                        ActivityAttemptInput(
                            submission_id="submission-key-123",
                            selected_option_id="a",
                        ),
                    )
        finally:
            service.retriever.close()
            service.generator.close()
