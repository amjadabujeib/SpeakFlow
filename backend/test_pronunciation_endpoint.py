import asyncio
import json
import os
import unittest
from unittest.mock import Mock, patch

import numpy as np
from fastapi import HTTPException

import main
from ctc_pronunciation_service import SCORING_METHOD
from pronunciation_core import PronunciationScoringError
from plp.schemas import ArabicTranslationInput, RoleplayScenarioDraftInput
from roleplay_engine import (
    apply_objective_updates,
    get_builtin_scenario,
    initial_objective_state,
)

FAKE_SPEECH = (
    np.sin(2 * np.pi * 220 * np.arange(16000, dtype=np.float32) / 16000) * 0.05
).astype(np.float32)


class FakeUpload:
    async def read(self):
        return b"wav-bytes"


class FakeScorer:
    def __init__(self, error=None, flagged=False, acoustically_contradicted=False):
        self.error = error
        self.flagged = flagged
        self.acoustically_contradicted = acoustically_contradicted
        self.call_count = 0

    def score(self, audio_path, target):
        self.call_count += 1
        if self.error:
            raise self.error
        expected_phones = ("K", "AA", "R")
        likely_phones = (
            ("B", "IY", "P")
            if self.acoustically_contradicted
            else expected_phones
        )
        result = {
            "target": target,
            "spoken": None,
            "target_ipa": ["k", "ˈɑ", "ɹ"],
            "analysis": [
                {
                    "char": "k",
                    "arpabet": "K",
                    "status": "correct",
                    "score": 91,
                    "error_probability": 3.0,
                    "likely_arpabet": likely_phones[0],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
                {
                    "char": "ˈɑ",
                    "arpabet": "AA1",
                    "status": "correct",
                    "score": 84,
                    "error_probability": 6.0,
                    "likely_arpabet": likely_phones[1],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
                {
                    "char": "ɹ",
                    "arpabet": "R",
                    "status": "incorrect" if self.flagged else "correct",
                    "score": 48 if self.flagged else 88,
                    "error_probability": 32.0 if self.flagged else 4.0,
                    "likely_arpabet": likely_phones[2],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
            ],
            "word_scores": [{"word": "car", "accuracy": 88}],
            "feedback": "Strong pronunciation across the aligned sounds.",
            "scores": {
                "accuracy": 88,
                "fluency": 80,
                "prosody": 76,
                "completeness": 100,
                "overall_score": 87,
                "gop_score": 87,
            },
            "scoring_method": SCORING_METHOD,
            "flagged_phones": ([{
                "phoneme": "ɹ",
                "arpabet": "R",
                "status": "incorrect",
                "score": 48,
                "error_probability": 32.0,
            }] if self.flagged else []),
            "warnings": [],
            "calibration": {"substitution_confidence_threshold": 20.0},
        }
        return result


class RoleplayApiAuthorityTests(unittest.TestCase):
    def test_client_authored_session_summary_endpoint_is_not_exposed(self):
        methods = {
            method
            for route in main.app.routes
            if getattr(route, "path", None) == "/api/roleplay/sessions"
            for method in (getattr(route, "methods", None) or set())
        }

        self.assertNotIn("POST", methods)


class PronunciationEndpointTests(unittest.TestCase):
    def test_local_coaching_corrects_warning_and_labels_closest_guess(self):
        feedback = main.local_pronunciation_coaching(
            [
                {
                    "phoneme": "ʌ",
                    "arpabet": "AH1",
                    "status": "warning",
                    "closest_ipa": "eɪ",
                    "replacement_verified": False,
                }
            ]
        )

        self.assertIn("/ʌ/ needs attention", feedback)
        self.assertIn("closest acoustic guess was /eɪ/", feedback)
        self.assertNotIn("not yet verified", feedback)
        self.assertIn("tongue and lips relaxed", feedback)

    def test_pronunciation_guide_uses_the_scorers_canonical_phones(self):
        guide = main.pronunciation_guide("through")

        self.assertEqual(guide["target"], "through")
        self.assertEqual(guide["phonemes"], ["θ", "ɹ", "ˈu"])
        self.assertEqual(guide["ipa"], "θɹˈu")
        self.assertEqual(guide["words"][0]["word"], "through")

    def test_chat_word_feedback_never_defaults_missing_score_to_perfect(self):
        missing = main._chat_word_feedback({"word": "hello"})
        self.assertIsNone(missing["score"])
        self.assertIsNone(missing["start"])
        self.assertIsNone(missing["end"])
        self.assertIsNone(
            main._chat_word_feedback({"word": "hello", "score": float("nan")})[
                "score"
            ]
        )
        self.assertIsNone(
            main._chat_word_feedback({"word": "hello", "score": 1.2})["score"]
        )
        self.assertEqual(
            main._chat_word_feedback(
                {"word": "hello", "score": 0.836, "start": 0.1, "end": 0.4}
            )["score"],
            0.84,
        )

    def test_chat_delivery_ignores_missing_or_invalid_timestamps(self):
        activity = {"voiced_duration_seconds": 0.8}
        words = [
            main._chat_word_feedback({"word": "hello", "score": 0.8}),
            main._chat_word_feedback({"word": "there", "score": 0.8}),
        ]
        with patch.object(
            main.librosa,
            "pyin",
            return_value=(np.array([190, 195, 205, 220, 210, 198]), None, None),
        ):
            fluency, _ = main._chat_delivery_metrics(
                np.zeros(16000, dtype=np.float32), activity, words
            )

        self.assertIsNone(fluency)

    def test_chat_delivery_metrics_require_multiple_aligned_words_for_fluency(self):
        activity = {"voiced_duration_seconds": 0.8}
        words = [
            {"word": "hello", "start": 0.05, "end": 0.35},
            {"word": "there", "start": 0.45, "end": 0.85},
        ]
        f0 = np.array([190, 195, 205, 220, 210, 198], dtype=float)

        with patch.object(main.librosa, "pyin", return_value=(f0, None, None)):
            fluency, prosody = main._chat_delivery_metrics(
                np.zeros(16000, dtype=np.float32), activity, words
            )

        self.assertIsInstance(fluency, int)
        self.assertIsInstance(prosody, int)
        self.assertGreater(fluency, 0)
        self.assertGreater(prosody, 0)

        with patch.object(main.librosa, "pyin", return_value=(f0, None, None)):
            one_word_fluency, _ = main._chat_delivery_metrics(
                np.zeros(16000, dtype=np.float32), activity, words[:1]
            )
        self.assertIsNone(one_word_fluency)

    def test_model_output_removes_leaked_instruction_heading(self):
        result = main._first_sentences(
            "That sounds useful! What do you enjoy? ## Your task: ignore this", 3
        )

        self.assertEqual(result, "That sounds useful! What do you enjoy?")

    def test_groq_chat_returns_reply_and_trusted_correction(self):
        with patch.object(
            main,
            "_groq_chat",
            side_effect=[
                "That sounds like a useful daily routine!",
                "Use the base verb after I.",
            ],
        ) as groq:
            result = main._get_groq_chat_response("I goes every day", "I go every day")

        self.assertEqual(result["reply"], "That sounds like a useful daily routine!")
        self.assertEqual(
            result["grammar_feedback"],
            "Use the base verb after I. Corrected: I go every day",
        )
        self.assertEqual(groq.call_count, 2)

    def test_groq_chat_does_not_invent_correction_when_gector_found_none(self):
        with patch.object(
            main, "_groq_chat", return_value="What kind of books do you enjoy?"
        ) as groq:
            result = main._get_groq_chat_response("I enjoy reading books")

        self.assertEqual(result["grammar_feedback"], "Correct")
        groq.assert_called_once()

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
            main, "_groq_chat", return_value=json.dumps(provider)
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
            main, "_groq_chat", return_value=json.dumps(provider)
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
            main,
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
            main, "_groq_chat", return_value=json.dumps(provider)
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
            main, "_groq_chat", return_value=json.dumps(provider)
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
            main, "_groq_chat", return_value=json.dumps(provider)
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
            main,
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
                main, "_groq_chat", return_value=json.dumps(provider)
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
            main, "_groq_chat", return_value=json.dumps(provider)
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
        with patch.object(main, "_groq_chat", side_effect=RuntimeError("offline")):
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
            main, "_groq_chat", return_value=json.dumps(provider)
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

    def test_news_rewrite_uses_groq(self):
        with patch.object(main, "_groq_chat", return_value="A simple summary.") as groq:
            result = main.rewrite_news("A complicated article.", "A2")

        self.assertEqual(result, "A simple summary.")
        groq.assert_called_once()

    def test_news_uses_the_user_selected_category_and_page(self):
        provider_response = Mock()
        provider_response.json.return_value = {
            "status": "ok",
            "totalResults": 12,
            "articles": [
                {
                    "title": "A sports headline",
                    "description": "A detailed sports summary.",
                    "url": "https://example.com/sports",
                    "urlToImage": None,
                    "source": {"name": "Example"},
                    "publishedAt": "2026-07-25T12:00:00Z",
                }
            ],
        }
        with (
            patch.dict(os.environ, {"NEWSAPI_KEY": "test-key"}),
            patch.object(main.requests, "get", return_value=provider_response) as get,
            patch.object(main, "rewrite_news", return_value="A simple sports summary."),
        ):
            result = main.get_personalized_news(
                level="A2",
                category="sports",
                page=2,
            )

        request = get.call_args
        self.assertEqual(request.kwargs["params"]["category"], "sports")
        self.assertEqual(request.kwargs["params"]["page"], 2)
        self.assertEqual(result["category"], "sports")
        self.assertEqual(result["articles"][0]["category"], "sports")
        self.assertEqual(
            result["articles"][0]["simplified_summary"],
            "A simple sports summary.",
        )

    def test_news_reports_missing_provider_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                main.get_personalized_news(
                    level="B1",
                    category="general",
                    page=1,
                )

        self.assertEqual(raised.exception.status_code, 503)

    def test_dictionary_pins_result_to_the_requested_word(self):
        provider_result = {
            "word": "thoroughly",
            "definition": "A definition for the selected word.",
            "translation": "technologie",
            "examples": [
                "Technology changes quickly.",
                "The school uses new technology.",
            ],
        }
        profile = Mock(native_language="French")
        with (
            patch.object(main, "_groq_client", return_value=Mock()),
            patch.object(main.plp_service, "get_profile", return_value=profile),
            patch.object(
                main,
                "_groq_chat",
                return_value=json.dumps(provider_result),
            ) as chat,
        ):
            result = asyncio.run(
                main.lookup_word(main.VocabularyLookupRequest(word="technology"))
            )

        self.assertEqual(result["word"], "technology")
        self.assertEqual(result["translation_language"], "French")
        self.assertEqual(result["translation"], "technologie")
        self.assertEqual(
            json.loads(chat.call_args.args[0][1]["content"]),
            {"word": "technology", "target_language": "French"},
        )
        self.assertEqual(
            result["definition"],
            "A definition for the selected word.",
        )

    def test_pronunciation_coaching_uses_groq(self):
        client = Mock()
        completion = Mock()
        completion.choices = [Mock()]
        completion.choices[0].message.content = (
            "Repeat car, red car, and clear car."
        )
        client.chat.completions.create.return_value = completion
        evidence = [{
            "phoneme": "ɹ",
            "arpabet": "R",
            "status": "incorrect",
            "score": 48,
            "error_probability": 32.0,
        }]

        with (
            patch.dict(os.environ, {
                "PRONUNCIATION_COACH_PROVIDER": "groq",
                "GROQ_PRONUNCIATION_MODEL": "openai/gpt-oss-120b",
            }),
            patch.object(main, "_groq_client", return_value=client),
        ):
            coaching, error, source = main.get_pronunciation_coaching("car", evidence)

        self.assertIsNone(error)
        self.assertIn("tongue", coaching)
        self.assertEqual(source, "groq")
        arguments = client.chat.completions.create.call_args.kwargs
        self.assertEqual(arguments["model"], "openai/gpt-oss-120b")

    def test_sentence_completeness_penalizes_omitted_words(self):
        score = main._sentence_completeness(
            "I would like to practice this complete sentence",
            "I would like to practice",
        )

        self.assertLess(score, 75)
        self.assertGreater(score, 40)

    def test_sentence_completeness_normalizes_written_numbers(self):
        self.assertEqual(main._sentence_completeness("The year is 2026", "the year is twenty twenty six"), 100)

    def test_sentence_completeness_does_not_reward_unrelated_equal_word_count(self):
        score = main._sentence_completeness(
            "we practice English every day",
            "cats sleep under wooden tables",
        )

        self.assertLess(score, 30)

    def test_single_word_gate_rejects_a_sentence_containing_the_target(self):
        self.assertFalse(
            main._single_word_transcript_matches(
                "will", "will we ever forget it"
            )
        )

    def test_omitted_sentence_word_is_unscored_in_phone_feedback(self):
        result = {
            "scores": {"accuracy": 90, "completeness": 100},
            "analysis": [
                {"status": "correct", "score": 90, "error_probability": 2.0},
                {"status": "correct", "score": 88, "error_probability": 3.0},
                {"status": "warning", "score": 75, "error_probability": 20.0},
                {"status": "correct", "score": 92, "error_probability": 2.0},
                {"status": "correct", "score": 94, "error_probability": 1.0},
            ],
            "word_scores": [
                {"word": "we", "accuracy": 90, "phone_start": 0, "phone_end": 1},
                {"word": "practice", "accuracy": 78, "phone_start": 1, "phone_end": 3},
                {"word": "today", "accuracy": 93, "phone_start": 3, "phone_end": 5},
            ],
            "flagged_phones": [{"phone_index": 2, "status": "warning"}],
        }

        main._apply_sentence_word_alignment(result, "we practice today", "we today")

        self.assertEqual(result["scores"]["completeness"], 67)
        self.assertTrue(result["word_scores"][1]["omitted"])
        self.assertEqual(result["analysis"][1]["status"], "omitted")
        self.assertIsNone(result["analysis"][2]["score"])
        self.assertEqual(result["flagged_phones"], [])
        self.assertEqual(result["scores"]["accuracy"], 92)

    def test_sentence_recomputes_overall_after_omissions(self):
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("I would", 80.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            result = asyncio.run(main.check_pronunciation("I would practice English", FakeUpload()))

        self.assertLess(result["scores"]["completeness"], 100)
        self.assertEqual(result["scores"]["gop_score"], main.calculate_overall_score(result["scores"]))
        self.assertEqual(result["scores"]["overall_score"], result["scores"]["gop_score"])
        self.assertIn("missing", result["feedback"].lower())

    def test_uses_only_the_production_scorer(self):
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("car", 91.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(result["scoring_method"], SCORING_METHOD)
        self.assertEqual(result["target_ipa"], ["k", "ˈɑ", "ɹ"])
        self.assertEqual(result["scores"]["accuracy"], 88)
        self.assertEqual(result["spoken"], "car")
        self.assertEqual(result["whisper_confidence"], 91.0)

    def test_lesson_pronunciation_is_validated_and_recorded_server_side(self):
        lesson_attempt = Mock()
        lesson_attempt.model_dump.return_value = {
            "correct": True,
            "score": 90,
            "explanation": "Sound check passed.",
        }
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main, "whisper_model", object()),
            patch.object(
                main,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                main,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
            patch.object(
                main.plp_service,
                "validate_pronunciation_target",
                return_value="car",
            ) as validate,
            patch.object(
                main.plp_service,
                "record_attempt",
                return_value=lesson_attempt,
            ) as record,
        ):
            result = asyncio.run(
                main.check_pronunciation(
                    "car",
                    FakeUpload(),
                    activity_id="lesson_activity",
                    attempt_session_id="lesson_session_123",
                )
            )

        validate.assert_called_once_with("lesson_activity", "car")
        self.assertEqual(result["lesson_attempt"]["correct"], True)
        self.assertEqual(
            record.call_args.kwargs["trusted_pronunciation"],
            {"target": "car", "accuracy": 88, "completeness": 100},
        )

    def test_non_16khz_recording_uses_bandlimited_resampling(self):
        scorer = FakeScorer()
        source = FAKE_SPEECH[::2]
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("car", 91.0, None)),
            patch.object(main.sf, "read", return_value=(source, 8000)),
            patch.object(main.sf, "write"),
            patch.object(main.librosa, "resample", return_value=FAKE_SPEECH) as resample,
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            asyncio.run(main.check_pronunciation("car", FakeUpload()))

        resample.assert_called_once()
        self.assertEqual(resample.call_args.kwargs["orig_sr"], 8000)
        self.assertEqual(resample.call_args.kwargs["target_sr"], 16000)
        self.assertEqual(resample.call_args.kwargs["res_type"], "soxr_hq")

    def test_flagged_phone_uses_groq_coaching_without_changing_scores(self):
        scorer = FakeScorer(flagged=True)
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("car", 91.0, None)),
            patch.object(main, "get_pronunciation_coaching", return_value=("Curl your tongue tip slightly back for /ɹ/.", None, "groq")) as coaching,
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        coaching.assert_called_once()
        self.assertEqual(result["feedback_source"], "groq")
        self.assertIn("tongue", result["feedback"])
        self.assertEqual(result["scores"]["accuracy"], 88)

    def test_rejects_harmonic_phone_noise_when_whisper_finds_no_speech(self):
        scorer = FakeScorer()
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("", 0.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("No intelligible speech", caught.exception.detail)
        self.assertEqual(scorer.call_count, 0)

    def test_allows_isolated_asr_mismatch_when_acoustics_support_target(self):
        scorer = FakeScorer()
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("duh", 80.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            result = asyncio.run(main.check_pronunciation("tough", FakeUpload()))

        self.assertEqual(scorer.call_count, 1)
        self.assertFalse(result["asr_target_match"])
        self.assertIn("acoustic phoneme evidence", result["warnings"][0])

    def test_rejects_unrelated_single_word_after_acoustic_contradiction(self):
        scorer = FakeScorer(acoustically_contradicted=True)
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("beep", 80.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("could not be verified", caught.exception.detail)
        self.assertEqual(scorer.call_count, 1)

    def test_rejects_longer_sentence_containing_single_word_target(self):
        scorer = FakeScorer()
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(
                main,
                "_transcribe_practice_audio",
                return_value=("will we ever forget it", 90.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("will", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(scorer.call_count, 0)

    def test_rejects_stationary_electronic_tone(self):
        tone = (
            np.sin(2 * np.pi * 440 * np.arange(16000, dtype=np.float32) / 16000)
            * 0.2
        ).astype(np.float32)

        activity = main._speech_activity(tone)

        self.assertFalse(activity["has_speech"])
        self.assertTrue(activity["stationary_tone"])

    def test_rejects_silence_instead_of_returning_fallback_scores(self):
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(np.zeros(16000, dtype=np.float32), 16000)),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)

    def test_rejects_background_audio_when_vad_finds_no_speech(self):
        background = np.random.default_rng(7).normal(0, 0.01, 16000).astype(np.float32)
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(background, 16000)),
            patch.object(main, "_speech_activity", return_value={"has_speech": False}),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("No speech", caught.exception.detail)

    def test_rejects_non_finite_audio(self):
        malformed = np.ones(16000, dtype=np.float32) * 0.05
        malformed[100] = np.nan
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(malformed, 16000)),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 400)

    def test_rejects_heavily_clipped_audio(self):
        clipped = np.ones(16000, dtype=np.float32)
        with (
            patch.object(main, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(clipped, 16000)),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("clipped", caught.exception.detail)

    def test_surfaces_production_scorer_errors(self):
        scorer = FakeScorer(PronunciationScoringError("The local English G2P model could not pronounce: xyz.", 422))
        with (
            patch.object(main, "pronunciation_scorer", scorer),
            patch.object(main, "whisper_model", object()),
            patch.object(main, "_transcribe_practice_audio", return_value=("xyz", 75.0, None)),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(main, "_speech_activity", return_value={"has_speech": True}),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("xyz", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("G2P model", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
