from tests.runtime.runtime_test_support import (
    FAKE_SPEECH,
    SCORING_METHOD,
    FakeScorer,
    FakeUpload,
    HTTPException,
    Mock,
    asyncio,
    main,
    model_runtime,
    patch,
    pronunciation_endpoints,
    unittest,
)


class RuntimePronunciationScoringTests(unittest.TestCase):
    def test_sentence_completeness_penalizes_omitted_words(self):
        score = main._sentence_completeness(
            "I would like to practice this complete sentence",
            "I would like to practice",
        )

        self.assertLess(score, 75)
        self.assertGreater(score, 40)

    def test_sentence_completeness_normalizes_written_numbers(self):
        self.assertEqual(
            main._sentence_completeness(
                "The year is 2026", "the year is twenty twenty six"
            ),
            100,
        )

    def test_sentence_completeness_does_not_reward_unrelated_equal_word_count(self):
        score = main._sentence_completeness(
            "we practice English every day",
            "cats sleep under wooden tables",
        )

        self.assertLess(score, 30)

    def test_single_word_gate_rejects_a_sentence_containing_the_target(self):
        self.assertFalse(
            main._single_word_transcript_matches("will", "will we ever forget it")
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
            "acoustic_flagged_phones": [{"phone_index": 2, "status": "warning"}],
        }

        main._apply_sentence_word_alignment(result, "we practice today", "we today")

        self.assertEqual(result["scores"]["completeness"], 67)
        self.assertTrue(result["word_scores"][1]["omitted"])
        self.assertEqual(result["analysis"][1]["status"], "omitted")
        self.assertIsNone(result["analysis"][2]["score"])
        self.assertEqual(result["acoustic_flagged_phones"], [])
        self.assertEqual(result["scores"]["accuracy"], 92)

    def test_sentence_recomputes_overall_after_omissions(self):
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("I would", 80.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(
                main.check_pronunciation("I would practice English", FakeUpload())
            )

        self.assertLess(result["scores"]["completeness"], 100)
        self.assertEqual(
            result["scores"]["overall_score"],
            main.calculate_overall_score(result["scores"]),
        )
        self.assertNotIn("gop_score", result["scores"])
        self.assertIn("missing", result["feedback"].lower())

    def test_uses_only_the_production_scorer(self):
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(result["scoring_method"], SCORING_METHOD)
        self.assertEqual(result["target_ipa"], ["k", "ˈɑ", "ɹ"])
        self.assertEqual(result["scores"]["accuracy"], 88)
        self.assertEqual(result["spoken"], "car")
        self.assertEqual(result["whisper_confidence"], 91.0)
        self.assertTrue(result["transcript_exact_match"])
        self.assertTrue(result["assessment"]["passed"])

    def test_cross_model_agreement_promotes_raw_orange_to_display_green(self):
        with (
            patch.object(
                model_runtime,
                "pronunciation_scorer",
                FakeScorer(uncertain=True),
            ),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        first = result["analysis"][0]
        self.assertEqual(first["acoustic_status"], "warning")
        self.assertEqual(first["display_status"], "correct")
        self.assertEqual(
            first["verification_reason"],
            "transcript_and_phone_identity_agree",
        )
        self.assertTrue(result["assessment"]["passed"])
        self.assertIn("Target verified", result["feedback"])
        self.assertEqual(result["feedback_kind"], "verified")

    def test_word_and_phone_disagreement_display_a_correction(self):
        with (
            patch.object(
                model_runtime,
                "pronunciation_scorer",
                FakeScorer(uncertain=True, first_phone_alternative=True),
            ),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("bar", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        first = result["analysis"][0]
        self.assertEqual(first["acoustic_status"], "warning")
        self.assertEqual(first["display_status"], "incorrect")
        self.assertEqual(
            first["verification_reason"],
            "transcript_and_phone_identity_contradict",
        )
        self.assertFalse(result["transcript_exact_match"])
        self.assertIsNone(result["assessment"]["passed"])
        self.assertEqual(result["feedback_source"], "local_cross_model_correction")
        self.assertEqual(result["feedback_kind"], "correction")
        self.assertIn("agree on this correction", result["feedback"])

    def test_lesson_pronunciation_is_validated_and_recorded_server_side(self):
        lesson_attempt = Mock()
        lesson_attempt.model_dump.return_value = {
            "correct": True,
            "score": 90,
            "explanation": "Sound check passed.",
        }
        lesson_attempt.pronunciation_mastery_verified = True
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
            patch.object(
                main.learning_plan_engine,
                "validate_pronunciation_target",
                return_value="car",
            ) as validate,
            patch.object(
                main.learning_plan_engine,
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
                    submission_id="lesson_session_123:pronunciation:1",
                )
            )

        validate.assert_called_once_with("lesson_activity", "car")
        self.assertEqual(result["lesson_attempt"]["correct"], True)
        self.assertEqual(result["feedback_kind"], "verified")
        trusted = record.call_args.kwargs["trusted_pronunciation"]
        self.assertEqual(trusted["target"], "car")
        self.assertEqual(trusted["accuracy"], 88)
        self.assertEqual(trusted["completeness"], 100)
        self.assertTrue(trusted["transcript_verified"])
        self.assertEqual(len(trusted["analysis"]), 3)
        self.assertEqual(
            record.call_args.args[1].submission_id,
            "lesson_session_123:pronunciation:1",
        )

    def test_non_16khz_recording_uses_bandlimited_resampling(self):
        scorer = FakeScorer()
        source = FAKE_SPEECH[::2]
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(main.sf, "read", return_value=(source, 8000)),
            patch.object(main.sf, "write"),
            patch.object(
                main.librosa, "resample", return_value=FAKE_SPEECH
            ) as resample,
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            asyncio.run(main.check_pronunciation("car", FakeUpload()))

        resample.assert_called_once()
        self.assertEqual(resample.call_args.kwargs["orig_sr"], 8000)
        self.assertEqual(resample.call_args.kwargs["target_sr"], 16000)
        self.assertEqual(resample.call_args.kwargs["res_type"], "soxr_hq")

    def test_flagged_phone_uses_groq_coaching_without_changing_scores(self):
        scorer = FakeScorer(flagged=True)
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("car", 91.0, None),
            ),
            patch.object(
                pronunciation_endpoints,
                "get_pronunciation_coaching",
                return_value=(
                    "Curl your tongue tip slightly back for /ɹ/.",
                    None,
                    "groq",
                ),
            ) as coaching,
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("car", FakeUpload()))

        coaching.assert_called_once()
        self.assertEqual(result["feedback_source"], "groq")
        self.assertIn("tongue", result["feedback"])
        self.assertEqual(result["scores"]["accuracy"], 88)

    def test_rejects_harmonic_phone_noise_when_whisper_finds_no_speech(self):
        scorer = FakeScorer()
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("", 0.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("No intelligible speech", caught.exception.detail)
        self.assertEqual(scorer.call_count, 0)

    def test_allows_isolated_asr_mismatch_when_acoustics_support_target(self):
        scorer = FakeScorer()
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("duh", 80.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            result = asyncio.run(main.check_pronunciation("tough", FakeUpload()))

        self.assertEqual(scorer.call_count, 1)
        self.assertFalse(result["asr_gate_match"])
        self.assertFalse(result["transcript_verified"])
        self.assertIn("cannot count as mastery", result["warnings"][0])

    def test_rejects_unrelated_single_word_after_acoustic_contradiction(self):
        scorer = FakeScorer(acoustically_contradicted=True)
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("beep", 80.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("could not be verified", caught.exception.detail)
        self.assertEqual(scorer.call_count, 1)

    def test_rejects_longer_sentence_containing_single_word_target(self):
        scorer = FakeScorer()
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("will we ever forget it", 90.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("will", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(scorer.call_count, 0)


if __name__ == "__main__":
    unittest.main()
