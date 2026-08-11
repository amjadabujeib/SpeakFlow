from tests.learning_plan.support.plp_test_support import (
    ActivityAttemptInput,
    LearningPlanEngine,
    MagicMock,
    Mock,
    PlpConflictError,
    patch,
    unittest,
    uuid,
)


class PlpAttemptIdempotencyTests(unittest.TestCase):
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
        service = LearningPlanEngine()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_attempts.session_scope",
                return_value=context,
            ):
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
