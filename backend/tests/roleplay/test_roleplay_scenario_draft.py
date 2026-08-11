from tests.runtime.runtime_test_support import (
    RoleplayScenarioDraftInput,
    json,
    main,
    patch,
    roleplay_scenario,
    unittest,
)


class RoleplayScenarioDraftTests(unittest.TestCase):
    def test_custom_scenario_draft_is_cefr_aware_and_structured(self):
        provider = {
            "icon": "🛍️",
            "ai_role": "shop assistant",
            "learner_role": "customer returning a product",
            "opening": "Hello. How can I help you with this item?",
            "objectives": [
                {
                    "id": "problem",
                    "label": "Explain the problem with the product",
                    "weight": 2,
                },
                {
                    "id": "purchase",
                    "label": "Give a relevant purchase detail",
                    "weight": 1,
                },
                {
                    "id": "solution",
                    "label": "Request and confirm a solution",
                    "weight": 2,
                },
            ],
            "target_language": [
                "I bought this last week",
                "The problem is",
                "Could I exchange it",
            ],
            "evaluation_rubric": [
                {
                    "id": "problem_clarity",
                    "label": "Problem clarity",
                    "description": (
                        "Explains the product problem with enough concrete detail."
                    ),
                    "weight": 2,
                },
                {
                    "id": "resolution",
                    "label": "Resolution management",
                    "description": (
                        "Responds to options and confirms a practical resolution."
                    ),
                    "weight": 1,
                },
            ],
        }
        with patch.object(
            roleplay_scenario,
            "_groq_chat",
            return_value=json.dumps(provider),
        ) as groq:
            result = main._roleplay_scenario_draft(
                RoleplayScenarioDraftInput(
                    category="Shopping",
                    title="Return an item",
                    description="Return a defective item and ask for an exchange.",
                ),
                "A2",
            )

        prompt = groq.call_args.args[0][0]["content"]
        self.assertIn("CEFR A2", prompt)
        self.assertEqual(result.designed_cefr_level, "A2")
        self.assertEqual(result.draft_source, "groq")
        self.assertEqual(len(result.objectives), 3)
        self.assertEqual(result.evaluation_rubric[0].id, "problem_clarity")

    def test_custom_scenario_draft_has_reviewable_provider_fallback(self):
        with patch.object(
            roleplay_scenario,
            "_groq_chat",
            side_effect=RuntimeError("offline"),
        ):
            result = main._roleplay_scenario_draft(
                RoleplayScenarioDraftInput(
                    category="Community",
                    title="Join a club",
                    description="Ask to join a local photography club.",
                ),
                "B1",
            )

        self.assertEqual(result.draft_source, "reviewable_fallback")
        self.assertEqual(result.designed_cefr_level, "B1")
        self.assertGreaterEqual(len(result.evaluation_rubric), 2)


if __name__ == "__main__":
    unittest.main()
