from tests.plp_test_support import *


class PlpAttemptContractTests(unittest.TestCase):
    def test_pronunciation_drill_requires_trusted_acoustic_result(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {"practice_items": ["think", "Thursday"]},
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
            },
        )
        self.assertTrue(passed)
        self.assertEqual(score, 90)
        self.assertIn("passed", explanation)
        self.assertTrue(evidence)

        passed, score, explanation, _ = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "think",
                "accuracy": 60,
                "completeness": 100,
            },
        )
        self.assertFalse(passed)
        self.assertEqual(score, 68)
        self.assertIn("Try again", explanation)

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
        progress = SimpleNamespace(
            completed_activity_ids=["sound_check", "technique"]
        )
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

    def test_fill_grading_normalizes_unicode_apostrophe_and_terminal_punctuation(self):
        correct, score, _, _ = _grade_activity(
            {
                "type": "fill_blank",
                "data": {
                    "accepted_answers": ["don't"],
                    "explanation": "The expected contraction is don't.",
                },
            },
            ActivityAttemptInput(text_answer="DON’T!"),
        )
        self.assertTrue(correct)
        self.assertEqual(score, 100)

    def test_invalid_choice_id_is_rejected_instead_of_recorded_as_wrong(self):
        with self.assertRaises(PlpInvalidAttemptError):
            _grade_activity(
                {
                    "type": "multiple_choice",
                    "data": {
                        "options": [
                            {"id": "a", "text": "One"},
                            {"id": "b", "text": "Two"},
                            {"id": "c", "text": "Three"},
                        ],
                        "correct_option_id": "a",
                        "explanation": "One is correct.",
                    },
                },
                ActivityAttemptInput(selected_option_id="not_an_option"),
            )

    def test_lesson_score_keeps_unanswered_items_in_the_denominator(self):
        lesson = Mock(
            id=uuid.uuid4(),
            content={
                "content": {
                    "activities": [
                        {
                            "id": f"q{index}",
                            "type": "multiple_choice",
                            "required": True,
                        }
                        for index in range(1, 4)
                    ]
                }
            },
        )
        session = Mock()
        session.scalar.side_effect = [100, None, None]
        self.assertEqual(_latest_lesson_score(session, lesson), 33)

    def test_checkpoint_activity_evidence_targets_only_its_bound_skill(self):
        lesson = Mock(
            lesson_type="assessment",
            skill_ids=["grammar.b1.core", "listening.b1.core"],
        )
        activity = {"id": "q1", "skill_ids": ["listening.b1.core"]}
        self.assertEqual(
            _activity_skill_ids(activity, lesson),
            ["listening.b1.core"],
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
        service = PlpService()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        service._update_lesson_completion = Mock(return_value=False)
        try:
            with (
                patch("plp.service_attempts.session_scope", return_value=context),
                patch("plp.service_attempts.SkillEvidence") as skill_evidence,
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
        service = PlpService()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        try:
            with patch("plp.service_attempts.session_scope", return_value=context):
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

    def test_submission_id_cannot_cache_a_different_answer(self):
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
        submission_id = "submission-key-123"
        existing = Mock(
            lesson_id=lesson.id,
            activity_id=activity_id,
            response={
                "attempt_kind": "correction",
                "submission_id": submission_id,
                "selected_option_id": "b",
                "timezone_offset_minutes": 0,
            },
        )
        session = Mock()
        session.scalar.return_value = existing
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = PlpService()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        try:
            with patch("plp.service_attempts.session_scope", return_value=context):
                with self.assertRaisesRegex(
                    PlpConflictError,
                    "different response",
                ):
                    service.record_attempt(
                        activity_id,
                        ActivityAttemptInput(
                            attempt_kind="correction",
                            submission_id=submission_id,
                            selected_option_id="a",
                        ),
                    )
        finally:
            service.retriever.close()
            service.generator.close()
