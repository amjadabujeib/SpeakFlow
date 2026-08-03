from tests.plp_test_support import *


class PlpGenerationContractTests(unittest.TestCase):
    def test_generation_audit_binds_the_reviewed_skill_to_its_specification(self):
        skill = Mock(
            title="Core listening",
            description="Follow the main idea.",
            outcomes=["Identify the main idea"],
        )
        session = Mock()
        session.scalar.return_value = skill
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        generator = MagicMock()
        generator.provider = "curated"
        generator.generate.return_value = (
            {
                "title": "Audit lesson",
                "content": {"activities": []},
            },
            [],
        )

        with (
            patch("plp.audit_generation.session_scope", return_value=context),
            patch(
                "plp.audit_generation.CurriculumRetriever",
                return_value=retriever,
            ),
            patch("plp.audit_generation.LessonGenerator", return_value=generator),
        ):
            audit_generation(domain="listening", level="B1")

        specification = generator.generate.call_args.kwargs["specification"]
        self.assertEqual(specification["skill_ids"], ["listening.b1.core"])

    def test_checkpoint_cannot_pass_from_a_partial_new_attempt_session(self):
        lesson = Mock(
            id=uuid.uuid4(),
            lesson_type="assessment",
            specification={
                "completion_policy": {
                    "mode": "minimum_score",
                    "minimum_score": 75,
                }
            },
            content={
                "content": {
                    "activities": [
                        {
                            "id": "q1",
                            "type": "multiple_choice",
                            "required": True,
                        },
                        {
                            "id": "q2",
                            "type": "multiple_choice",
                            "required": True,
                        },
                    ]
                }
            },
        )
        progress = Mock(
            completed_activity_ids=["q1", "q2"],
            best_score=50,
            status="in_progress",
            completed_at=None,
        )
        session = Mock()
        session.scalars.return_value.all.return_value = ["q1"]
        service = PlpService()
        try:
            completed = service._update_lesson_completion(
                session,
                lesson,
                progress,
                attempt_session_id="session_12345678",
            )
        finally:
            service.retriever.close()
            service.generator.close()
        self.assertFalse(completed)
        self.assertEqual(progress.status, "in_progress")
        session.scalar.assert_not_called()

    def test_first_activity_attempt_initializes_progress_before_flush(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            skill_ids=[],
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
            with patch("plp.service_attempts.session_scope", return_value=context):
                result = service.record_attempt(
                    activity_id,
                    ActivityAttemptInput(selected_option_id="a"),
                )
        finally:
            service.retriever.close()
            service.generator.close()

        progress = next(
            call.args[0]
            for call in session.add.call_args_list
            if call.args[0].__class__.__name__ == "LessonProgress"
        )
        self.assertEqual(progress.status, "in_progress")
        self.assertEqual(progress.attempts, 1)
        self.assertEqual(progress.completed_activity_ids, [activity_id])
        self.assertTrue(result.correct)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.correct_response, {"selected_option_id": "a"})
        self.assertEqual(result.lesson_score, 100)
        self.assertFalse(result.lesson_completed)
        self.assertFalse(result.newly_completed)
        self.assertEqual(result.xp_awarded, 0)

    def test_attempt_awards_xp_only_on_the_completion_transition(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            xp=20,
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

        for initial_status, expected_new, expected_xp in (
            ("in_progress", True, 20),
            ("completed", False, 0),
        ):
            with self.subTest(initial_status=initial_status):
                progress = Mock(
                    status=initial_status,
                    completed_activity_ids=[activity_id],
                    best_score=100,
                    attempts=1,
                    completed_at=None,
                )
                session = Mock()
                session.get.return_value = progress
                session.scalar.side_effect = [1, 100]
                context = MagicMock()
                context.__enter__.return_value = session
                context.__exit__.return_value = False
                service = PlpService()
                service._find_active_lesson_by_activity = Mock(return_value=lesson)

                def complete_lesson(*_args, **_kwargs):
                    progress.status = "completed"
                    return True

                service._update_lesson_completion = Mock(
                    side_effect=complete_lesson
                )
                service._queue_next_generation = Mock()
                try:
                    with patch(
                        "plp.service_attempts.session_scope",
                        return_value=context,
                    ):
                        result = service.record_attempt(
                            activity_id,
                            ActivityAttemptInput(selected_option_id="a"),
                        )
                finally:
                    service.retriever.close()
                    service.generator.close()

                self.assertEqual(result.lesson_score, 100)
                self.assertTrue(result.lesson_completed)
                self.assertEqual(result.newly_completed, expected_new)
                self.assertEqual(result.xp_awarded, expected_xp)
                self.assertEqual(
                    service._queue_next_generation.call_count,
                    1 if expected_new else 0,
                )

    def test_reset_preserves_account_and_deletes_user_learning_state(self):
        session = Mock()
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = PlpService()
        try:
            with patch("plp.service_base.session_scope", return_value=context):
                result = service.reset_local_learner()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(result, {"status": "reset"})
        self.assertEqual(session.execute.call_count, 8)
        session.delete.assert_not_called()
