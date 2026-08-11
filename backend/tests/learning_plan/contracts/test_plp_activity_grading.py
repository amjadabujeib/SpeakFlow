from tests.learning_plan.support.plp_test_support import (
    ActivityAttemptInput,
    Mock,
    PlpInvalidAttemptError,
    _activity_skill_ids,
    _grade_activity,
    _latest_lesson_score,
    unittest,
    uuid,
)


class PlpActivityGradingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
