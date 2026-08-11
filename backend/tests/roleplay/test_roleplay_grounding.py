import json
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from speakflow.features.learning_plan.engine.service import PlpConflictError
from speakflow.features.roleplay.application import roleplay_scenario, roleplay_turn
from speakflow.features.roleplay.domain.engine import (
    get_builtin_scenario,
    initial_objective_state,
)


class RoleplayTurnGroundingTests(unittest.TestCase):
    def _context(self, *, turns=None):
        scenario = get_builtin_scenario("airport_check_in")
        assert scenario is not None
        return {
            "cefr_level": "B1",
            "scenario": scenario,
            "objective_state": initial_objective_state(scenario),
            "turns": turns or [],
        }

    def test_obvious_gibberish_is_rejected_before_provider(self):
        provider = {
            "turn_status": "meaningful",
            "understood_meaning": "The learner asked for help.",
            "reply": "Sure, I can help you with that.",
            "objective_updates": [],
            "scenario_complete": False,
        }

        for index, learner_text in enumerate(
            ("as", "zxqv", "blorpt qqq", "asdfghjkl", "the and of"),
            start=1,
        ):
            with self.subTest(learner_text=learner_text):
                context = self._context()
                state = context["objective_state"]
                with patch.object(
                    roleplay_scenario,
                    "_groq_chat",
                    return_value=json.dumps(provider),
                ) as groq:
                    result = roleplay_scenario._roleplay_turn_reply(
                        context,
                        learner_text,
                        f"turn-gibberish-{index:04d}",
                    )

                groq.assert_not_called()
                self.assertEqual(result["turn_status"], "unclear")
                self.assertIn("didn't understand", result["reply"])
                self.assertEqual(result["objective_updates"], [])
                self.assertEqual(result["objective_state"], state)
                self.assertFalse(result["scenario_complete"])

    def test_provider_unclear_status_cannot_hallucinate_intent_or_progress(self):
        context = self._context()
        state = context["objective_state"]
        provider = {
            "turn_status": "unclear",
            "understood_meaning": "",
            "reply": "Sure, I can help you with that.",
            "objective_updates": [
                {"objective_id": "destination", "evidence": "zxqv"}
            ],
            "scenario_complete": True,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = roleplay_scenario._roleplay_turn_reply(
                context,
                "zxqv",
                "turn-unclear-0001",
            )

        self.assertEqual(result["turn_status"], "unclear")
        self.assertNotEqual(result["reply"], provider["reply"])
        self.assertEqual(result["objective_updates"], [])
        self.assertEqual(result["objective_state"], state)
        self.assertFalse(result["scenario_complete"])

    def test_provider_off_topic_status_gets_controlled_redirect(self):
        context = self._context()
        provider = {
            "turn_status": "off_topic",
            "understood_meaning": "",
            "reply": "The football match starts tonight.",
            "objective_updates": [],
            "scenario_complete": False,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = roleplay_scenario._roleplay_turn_reply(
                context,
                "Who won the football match?",
                "turn-offtopic-0001",
            )

        self.assertEqual(result["turn_status"], "off_topic")
        self.assertIn("our situation", result["reply"])
        self.assertEqual(result["objective_updates"], [])

    def test_contextually_meaningful_one_word_answer_remains_valid(self):
        context = self._context(
            turns=[
                {
                    "turn_id": "turn-history-0006",
                    "user_text": "Hello.",
                    "assistant_text": "Where are you flying today?",
                }
            ]
        )
        provider = {
            "turn_status": "meaningful",
            "understood_meaning": "The learner's destination is Paris.",
            "reply": "Thank you. May I see your passport?",
            "objective_updates": [
                {"objective_id": "destination", "evidence": "Paris"}
            ],
            "scenario_complete": False,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ) as groq:
            result = roleplay_scenario._roleplay_turn_reply(
                context,
                "Paris",
                "turn-short-answer-0001",
            )

        self.assertEqual(result["turn_status"], "meaningful")
        self.assertTrue(result["objective_state"]["destination"]["completed"])
        system_prompt = groq.call_args.args[0][0]["content"]
        self.assertIn("Never invent or assume", system_prompt)
        self.assertIn("keys turn_status, understood_meaning", system_prompt)

    def test_meaningful_status_without_grounded_interpretation_fails_closed(self):
        context = self._context()
        provider = {
            "turn_status": "meaningful",
            "understood_meaning": "",
            "reply": "Sure, I can help you with that.",
            "objective_updates": [
                {"objective_id": "destination", "evidence": "zxqv"}
            ],
            "scenario_complete": True,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = roleplay_scenario._roleplay_turn_reply(
                context,
                "zxqv",
                "turn-ungrounded-0001",
            )

        self.assertEqual(result["turn_status"], "unclear")
        self.assertEqual(result["objective_updates"], [])
        self.assertFalse(result["scenario_complete"])

    def test_names_places_and_abbreviations_have_no_word_specific_blocklist(self):
        provider = {
            "turn_status": "meaningful",
            "understood_meaning": "The learner supplied the requested detail.",
            "reply": "Thank you.",
            "objective_updates": [],
            "scenario_complete": False,
        }

        for index, learner_text in enumerate(("José", "Paris", "JFK", "card")):
            with self.subTest(learner_text=learner_text):
                with patch.object(
                    roleplay_scenario,
                    "_groq_chat",
                    return_value=json.dumps(provider),
                ) as groq:
                    result = roleplay_scenario._roleplay_turn_reply(
                        self._context(),
                        learner_text,
                        f"turn-valid-short-{index:04d}",
                    )

                groq.assert_called_once()
                self.assertEqual(result["turn_status"], "meaningful")
                self.assertEqual(result["reply"], "Thank you.")

    def test_missing_provider_status_fails_closed_without_progress(self):
        context = self._context()
        provider = {
            "understood_meaning": "The learner's destination is Paris.",
            "reply": "Sure, I can help.",
            "objective_updates": [
                {"objective_id": "destination", "evidence": "Paris"}
            ],
            "scenario_complete": True,
        }

        with patch.object(
            roleplay_scenario, "_groq_chat", return_value=json.dumps(provider)
        ):
            result = roleplay_scenario._roleplay_turn_reply(
                context,
                "Paris",
                "turn-missing-status-0001",
            )

        self.assertEqual(result["turn_status"], "unclear")
        self.assertEqual(result["objective_updates"], [])

    def test_unclear_status_strips_all_evaluation_evidence_before_persistence(self):
        context = self._context()
        unclear_result = {
            "turn_status": "unclear",
            "reply": "I'm sorry, I didn't understand that. Could you say it another way?",
            "objective_updates": [],
        }

        def record_turn(_session_id, payload, *, objective_updates):
            self.assertEqual(objective_updates, [])
            return {
                "turn": {**payload.model_dump(mode="json"), "sequence": 1},
                "objective_state": context["objective_state"],
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
            patch.object(
                roleplay_turn,
                "_roleplay_turn_reply",
                return_value=unclear_result,
            ),
            patch.object(
                roleplay_turn.roleplay_service,
                "record_turn",
                side_effect=record_turn,
            ),
        ):
            result = roleplay_turn.process_roleplay_turn(
                client_session_id="roleplay-grounding-0001",
                turn_id="turn-grounding-0001",
                input_mode="audio",
                user_text="zxqv",
                corrected_text="A fabricated correction.",
                word_feedback=[{"word": "zxqv", "score": 0.95}],
                delivery_metrics={"fluency": 99, "voiced_seconds": 1.0},
                grammar_evaluated=True,
            )

        stored = result["turn"]
        self.assertEqual(stored["turn_status"], "unclear")
        self.assertFalse(stored["grammar_evaluated"])
        self.assertIsNone(stored["grammar_corrected_text"])
        self.assertEqual(stored["grammar_error_units"], 0)
        self.assertEqual(stored["word_count"], 0)
        self.assertEqual(stored["word_feedback"], [])
        self.assertTrue(
            all(value is None for value in stored["delivery_metrics"].values())
        )

    def test_exact_unclear_turn_replay_uses_its_canonical_stored_form(self):
        context = self._context()
        context["status"] = "active"
        context["turns"] = [
            {
                "turn_id": "turn-unclear-replay-0001",
                "sequence": 1,
                "input_mode": "text",
                "user_text": "zxqv",
                "assistant_text": "Could you say it another way?",
                "turn_status": "unclear",
                "grammar_corrected_text": None,
                "grammar_feedback": None,
                "grammar_evaluated": False,
                "grammar_error_units": 0.0,
                "word_count": 0,
                "word_feedback": [],
                "delivery_metrics": {},
                "objective_evidence": [],
            }
        ]

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
            patch.object(roleplay_turn, "_roleplay_turn_reply") as provider,
        ):
            result = roleplay_turn.process_roleplay_turn(
                client_session_id="roleplay-grounding-0002",
                turn_id="turn-unclear-replay-0001",
                input_mode="text",
                user_text="zxqv",
                corrected_text="A newly computed correction.",
                word_feedback=[],
                delivery_metrics={},
                grammar_evaluated=True,
            )

        provider.assert_not_called()
        self.assertEqual(result["turn_status"], "unclear")
        self.assertEqual(result["turn"]["sequence"], 1)

    def test_inactive_session_is_rejected_before_provider_generation(self):
        context = self._context()
        context["status"] = "complete"

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
            patch.object(roleplay_turn, "_roleplay_turn_reply") as provider,
        ):
            with self.assertRaisesRegex(
                PlpConflictError,
                "roleplay session is no longer active",
            ):
                roleplay_turn.process_roleplay_turn(
                    client_session_id="roleplay-grounding-0003",
                    turn_id="turn-inactive-0001",
                    input_mode="text",
                    user_text="I need help.",
                    corrected_text=None,
                    word_feedback=[],
                    delivery_metrics={},
                    grammar_evaluated=False,
                )

        provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
