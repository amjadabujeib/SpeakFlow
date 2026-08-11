from contextlib import nullcontext

from speakflow.features.roleplay.application import roleplay_turn
from tests.runtime.runtime_test_support import (
    ArabicTranslationInput,
    apply_objective_updates,
    asyncio,
    get_builtin_scenario,
    initial_objective_state,
    json,
    main,
    patch,
    roleplay_evaluation,
    roleplay_scenario,
    unittest,
)


class RuntimeRoleplayTests(unittest.TestCase):
    def test_non_english_typed_turn_never_reaches_the_provider(self):
        with patch.object(roleplay_turn, "_roleplay_turn_reply") as reply:
            with self.assertRaisesRegex(ValueError, "write your roleplay turn"):
                roleplay_turn.process_roleplay_turn(
                    client_session_id="roleplay-language-0001",
                    turn_id="turn-language-0001",
                    input_mode="text",
                    user_text="ابتثجحخ",
                    corrected_text=None,
                    word_feedback=[],
                    delivery_metrics={},
                    grammar_evaluated=False,
                )

        reply.assert_not_called()

    def test_replayed_turn_returns_stored_response_without_provider_call(self):
        scenario = get_builtin_scenario("cafe_small_talk")
        state = initial_objective_state(scenario)
        existing = {
            "turn_id": "turn-replay-0001",
            "sequence": 1,
            "input_mode": "text",
            "user_text": "Hello there.",
            "assistant_text": "Hello. How are you?",
            "grammar_corrected_text": None,
            "grammar_feedback": "Correct",
            "grammar_evaluated": True,
            "grammar_error_units": 0.0,
            "word_count": 2,
            "word_feedback": [],
            "delivery_metrics": {},
            "objective_evidence": [],
        }
        context = {
            "scenario": scenario,
            "objective_state": state,
            "turns": [existing],
        }
        with (
            patch.object(
                roleplay_turn.roleplay_service,
                "turn_lease",
                return_value=nullcontext(),
            ),
            patch.object(
                roleplay_turn.roleplay_service,
                "context",
                return_value=context,
            ),
            patch.object(roleplay_turn, "_roleplay_turn_reply") as reply,
        ):
            result = roleplay_turn.process_roleplay_turn(
                client_session_id="roleplay-replay-0001",
                turn_id="turn-replay-0001",
                input_mode="text",
                user_text="Hello there.",
                corrected_text=None,
                word_feedback=[],
                delivery_metrics={},
                grammar_evaluated=False,
            )

        reply.assert_not_called()
        self.assertEqual(result["turn"]["assistant_text"], "Hello. How are you?")

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
            "turn_status": "meaningful",
            "understood_meaning": "The learner is flying to Paris.",
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
            "turn_status": "meaningful",
            "understood_meaning": "The learner is flying to Germany.",
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
            "turn_status": "meaningful",
            "understood_meaning": "The learner agrees to check the bag.",
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
            "turn_status": "meaningful",
            "understood_meaning": "The learner requests a middle seat.",
            "reply": "A middle seat is available. Would you like help with anything else?",
            "objective_updates": [{"objective_id": "seat", "evidence": "middle seat"}],
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
            ],
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
                main.learning_plan_engine,
                "roleplay_context",
                side_effect=AssertionError("translation touched roleplay state"),
            ) as roleplay_context,
        ):
            result = asyncio.run(main.translate_arabic(payload))

        roleplay_context.assert_not_called()
        self.assertEqual(result.source_text, "مرحبا")

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
                    "word_count": 6,
                },
                {
                    "turn_id": "turn-real-0002",
                    "user_text": "Do you come here often?",
                    "assistant_text": "Sometimes.",
                    "word_count": 6,
                },
                {
                    "turn_id": "turn-real-0003",
                    "user_text": "I enjoy meeting people here after work.",
                    "assistant_text": "That sounds pleasant.",
                    "word_count": 8,
                },
                {
                    "turn_id": "turn-real-0004",
                    "user_text": "The coffee is good and the room feels welcoming.",
                    "assistant_text": "I agree.",
                    "word_count": 10,
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
        self.assertEqual(result["scenario_evidence"][0]["rubric_id"], "reciprocity")
