from tests.pronunciation_test_support import *


class RuntimeRoleplayTests(unittest.TestCase):
    def test_roleplay_reply_receives_history_and_only_accepts_exact_evidence(self):
        scenario = get_builtin_scenario("airport_check_in")
        context = {
            "cefr_level": "B1",
            "scenario": scenario,
            "objective_state": initial_objective_state(scenario),
            "turns": [
                {
                    "turn_id": "turn-history-0001",
                    "user_text": "Good morning.",
                    "assistant_text": "Where are you flying?",
                }
            ],
        }
        provider = {
            "reply": "Great. May I see your passport?",
            "objective_updates": [
                {
                    "objective_id": "destination",
                    "evidence": "flying to Paris",
                },
                {
                    "objective_id": "baggage",
                    "evidence": "one bag",
                },
            ],
            "scenario_complete": True,
        }
        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ) as groq:
            result = main._roleplay_turn_reply(
                context,
                "I am flying to Paris.",
                "turn-current-0002",
            )

        request_payload = json.loads(groq.call_args.args[0][1]["content"])
        self.assertEqual(
            request_payload["recent_history"][0]["turn_id"],
            "turn-history-0001",
        )
        self.assertEqual(
            result["objective_updates"],
            [
                {
                    "objective_id": "destination",
                    "turn_id": "turn-current-0002",
                    "evidence": "flying to Paris",
                }
            ],
        )
        self.assertFalse(result["scenario_complete"])

    def test_roleplay_reply_recovers_explicit_airport_fact_model_missed(self):
        scenario = get_builtin_scenario("airport_check_in")
        context = {
            "cefr_level": "B1",
            "scenario": scenario,
            "objective_state": initial_objective_state(scenario),
            "turns": [],
        }
        provider = {
            "reply": "Thank you. May I see your passport?",
            "objective_updates": [],
            "scenario_complete": False,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = main._roleplay_turn_reply(
                context,
                "I am flying to Germany.",
                "turn-current-0003",
            )

        self.assertTrue(result["objective_state"]["destination"]["completed"])
        self.assertEqual(
            result["objective_state"]["destination"]["evidence"],
            "I am flying to Germany.",
        )

    def test_roleplay_repeated_question_is_repaired(self):
        scenario = get_builtin_scenario("airport_check_in")
        context = {
            "cefr_level": "B1",
            "scenario": scenario,
            "objective_state": initial_objective_state(scenario),
            "turns": [
                {
                    "turn_id": "turn-history-0002",
                    "user_text": "I have one bag.",
                    "assistant_text": "Would you like to check that bag?",
                }
            ],
        }
        repeated = {
            "reply": "Do you have checked luggage?",
            "objective_updates": [],
            "scenario_complete": False,
        }
        with patch.object(
            roleplay_scenario,
            "_groq_chat",
            side_effect=[
                json.dumps(repeated),
                "May I see your passport, please?",
            ],
        ) as groq:
            result = main._roleplay_turn_reply(
                context,
                "Yes.",
                "turn-current-0004",
            )

        self.assertEqual(groq.call_count, 2)
        self.assertEqual(result["reply"], "May I see your passport, please?")

    def test_completed_goals_allow_the_roleplay_to_continue(self):
        scenario = get_builtin_scenario("airport_check_in")
        state = apply_objective_updates(
            initial_objective_state(scenario),
            [
                {
                    "objective_id": objective_id,
                    "turn_id": f"turn-{objective_id}",
                    "evidence": objective_id,
                }
                for objective_id in ("destination", "identification", "baggage")
            ],
        )
        context = {
            "cefr_level": "B1",
            "scenario": scenario,
            "objective_state": state,
            "turns": [],
        }
        provider = {
            "reply": "A middle seat is available. Would you like help with anything else?",
            "objective_updates": [
                {"objective_id": "seat", "evidence": "middle seat"}
            ],
            "scenario_complete": True,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ) as groq:
            result = main._roleplay_turn_reply(
                context,
                "A middle seat, please.",
                "turn-current-0005",
            )

        groq.assert_called_once()
        self.assertTrue(result["scenario_complete"])
        self.assertEqual(result["reply"], provider["reply"])

    def test_escape_options_are_pure_translation_with_three_registers(self):
        provider = {
            "literal_meaning": "I have one bag.",
            "options": [
                {
                    "style": "natural",
                    "label": "ignored",
                    "text": "I've got one bag.",
                },
                {
                    "style": "polite",
                    "label": "ignored",
                    "text": "I have one bag.",
                },
                {
                    "style": "formal",
                    "label": "ignored",
                    "text": "I possess one item of luggage.",
                },
            ]
        }

        with patch.object(
            roleplay_evaluation, "_groq_chat", return_value=json.dumps(provider)
        ) as groq:
            result = main._arabic_translation_options("لدي حقيبة واحدة")

        request = json.loads(groq.call_args.args[0][1]["content"])
        system_prompt = groq.call_args.args[0][0]["content"]
        self.assertEqual(
            request,
            {
                "source_language": "Arabic",
                "source_text": "لدي حقيبة واحدة",
            },
        )
        self.assertIn("This is translation only", system_prompt)
        self.assertIn("must not infer an answer", system_prompt)
        self.assertEqual(
            [item.style for item in result.options],
            ["natural", "polite", "formal"],
        )

    def test_escape_options_tolerate_old_style_names_and_missing_metadata(self):
        provider = {
            "options": [
                {"style": "natural", "text": "Hi."},
                {"style": "polite", "text": "Hello."},
                {"style": "precise", "text": "Greetings."},
            ]
        }

        with patch.object(
            roleplay_evaluation, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = main._arabic_translation_options("مرحبا")

        self.assertEqual(
            [(item.style, item.text) for item in result.options],
            [
                ("natural", "Hi."),
                ("polite", "Hello."),
                ("formal", "Greetings."),
            ],
        )

    def test_escape_options_can_fall_back_to_literal_translation(self):
        with patch.object(
            roleplay_evaluation,
            "_groq_chat",
            return_value=json.dumps({"literal_meaning": "Hello."}),
        ):
            result = main._arabic_translation_options("مرحبا")

        self.assertEqual(len(result.options), 3)
        self.assertTrue(all(item.text == "Hello." for item in result.options))

    def test_translation_endpoint_does_not_require_a_roleplay_session(self):
        payload = ArabicTranslationInput(text="مرحبا")
        provider = {
            "options": [
                {"style": "natural", "text": "Hi."},
                {"style": "polite", "text": "Hello."},
                {"style": "formal", "text": "Greetings."},
            ]
        }
        with (
            patch.object(
                roleplay_evaluation, "_groq_chat", return_value=json.dumps(provider)
            ),
            patch.object(
                main.plp_service,
                "roleplay_context",
                side_effect=AssertionError("translation touched roleplay state"),
            ) as roleplay_context,
        ):
            result = asyncio.run(main.translate_arabic(payload))

        roleplay_context.assert_not_called()
        self.assertEqual(result.source_text, "مرحبا")

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
                    "description": "Explains the product problem with enough concrete detail.",
                    "weight": 2,
                },
                {
                    "id": "resolution",
                    "label": "Resolution management",
                    "description": "Responds to options and confirms a practical resolution.",
                    "weight": 1,
                },
            ],
        }
        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
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

    def test_roleplay_evaluator_filters_evidence_to_real_turn_ids(self):
        scenario = get_builtin_scenario("cafe_small_talk")
        context = {
            "cefr_level": "B1",
            "scenario": scenario,
            "turns": [
                {
                    "turn_id": "turn-real-0001",
                    "user_text": "Of course. Please sit here.",
                    "assistant_text": "Thank you.",
                },
                {
                    "turn_id": "turn-real-0002",
                    "user_text": "Do you come here often?",
                    "assistant_text": "Sometimes.",
                },
            ],
        }
        provider = {
            "interaction_score": 80,
            "vocabulary_score": 74,
            "interaction_evidence": [
                {"turn_id": "turn-real-0002", "reason": "Asked a follow-up."},
                {"turn_id": "invented", "reason": "Not real."},
            ],
            "vocabulary_evidence": [],
            "scenario_scores": [
                {
                    "rubric_id": "reciprocity",
                    "score": 82,
                    "evidence": [
                        {
                            "turn_id": "turn-real-0002",
                            "reason": "Asked a relevant reciprocal question.",
                        }
                    ],
                },
                {
                    "rubric_id": "invented",
                    "score": 100,
                    "evidence": [],
                },
            ],
        }
        with patch.object(
            roleplay_evaluation, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = main._roleplay_external_evaluation(context)

        self.assertEqual(result["interaction_score"], 80)
        self.assertEqual(
            result["interaction_evidence"],
            [
                {
                    "turn_id": "turn-real-0002",
                    "reason": "Asked a follow-up.",
                }
            ],
        )
        self.assertEqual(
            result["scenario_evidence"][0]["rubric_id"], "reciprocity"
        )
