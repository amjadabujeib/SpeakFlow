from tests.runtime.runtime_test_support import (
    FAKE_SPEECH,
    FakeScorer,
    FakeUpload,
    HTTPException,
    PronunciationScoringError,
    asyncio,
    main,
    model_runtime,
    np,
    patch,
    pronunciation_endpoints,
    unittest,
)


class PronunciationAudioQualityTests(unittest.TestCase):
    def test_rejects_stationary_electronic_tone(self):
        tone = (
            np.sin(2 * np.pi * 440 * np.arange(16000, dtype=np.float32) / 16000) * 0.2
        ).astype(np.float32)

        activity = main._speech_activity(tone)

        self.assertFalse(activity["has_speech"])
        self.assertTrue(activity["stationary_tone"])

    def test_rejects_silence_instead_of_returning_fallback_scores(self):
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(
                main.sf,
                "read",
                return_value=(np.zeros(16000, dtype=np.float32), 16000),
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)

    def test_rejects_background_audio_when_vad_finds_no_speech(self):
        background = np.random.default_rng(7).normal(0, 0.01, 16000).astype(np.float32)
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(background, 16000)),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": False},
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("No speech", caught.exception.detail)

    def test_rejects_non_finite_audio(self):
        malformed = np.ones(16000, dtype=np.float32) * 0.05
        malformed[100] = np.nan
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(malformed, 16000)),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 400)

    def test_rejects_heavily_clipped_audio(self):
        clipped = np.ones(16000, dtype=np.float32)
        with (
            patch.object(model_runtime, "pronunciation_scorer", FakeScorer()),
            patch.object(main.sf, "read", return_value=(clipped, 16000)),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("car", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("clipped", caught.exception.detail)

    def test_surfaces_production_scorer_errors(self):
        scorer = FakeScorer(
            PronunciationScoringError(
                "The local English G2P model could not pronounce: xyz.",
                422,
            )
        )
        with (
            patch.object(model_runtime, "pronunciation_scorer", scorer),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("xyz", 75.0, None),
            ),
            patch.object(main.sf, "read", return_value=(FAKE_SPEECH, 16000)),
            patch.object(main.sf, "write"),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
        ):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.check_pronunciation("xyz", FakeUpload()))

        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("G2P model", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
