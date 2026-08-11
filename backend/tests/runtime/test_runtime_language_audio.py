from pathlib import Path

from speakflow.features.language_tools.infrastructure import tts as tts_runtime
from speakflow.runtime import models as model_runtime
from tests.runtime.runtime_test_support import (
    FAKE_SPEECH,
    FakeUpload,
    HTTPException,
    asyncio,
    language_runtime,
    main,
    np,
    patch,
    pronunciation_endpoints,
    unittest,
)


class PronunciationEndpointTests(unittest.TestCase):
    def test_identical_concurrent_tts_requests_share_one_synthesis(self):
        calls = []

        def synthesize(text, output_path):
            calls.append(text)
            Path(output_path).write_bytes(b"RIFF-test-wave")
            return True

        async def request_twice():
            return await asyncio.gather(
                tts_runtime._tts_response("same phrase"),
                tts_runtime._tts_response("same   phrase"),
            )

        with tts_runtime._tts_cache_lock:
            tts_runtime._tts_cache.clear()
            tts_runtime._tts_cache_order.clear()
            tts_runtime._tts_key_locks.clear()
            tts_runtime._tts_cache_bytes = 0
        with (
            patch.object(model_runtime, "KOKORO_AVAILABLE", True),
            patch.object(tts_runtime, "generate_tts_audio", side_effect=synthesize),
        ):
            responses = asyncio.run(request_twice())

        self.assertEqual(calls, ["same phrase"])
        self.assertEqual([response.body for response in responses], [b"RIFF-test-wave"] * 2)

    def test_audio_upload_limit_is_enforced_while_streaming(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main._read_upload_limited(FakeUpload(b"123456"), 5))

        self.assertEqual(raised.exception.status_code, 413)

    def test_guided_speaking_returns_a_verified_transcript(self):
        with (
            patch.object(
                pronunciation_endpoints,
                "_decode_wav_16k",
                return_value=(FAKE_SPEECH, 16000),
            ),
            patch.object(
                pronunciation_endpoints,
                "_speech_activity",
                return_value={"has_speech": True},
            ),
            patch.object(model_runtime, "whisper_model", object()),
            patch.object(
                pronunciation_endpoints,
                "_transcribe_practice_audio",
                return_value=("I practice every day.", 92.0, None),
            ),
        ):
            result = asyncio.run(
                main.transcribe_guided_speaking(FakeUpload())
            )

        self.assertEqual(result["transcript"], "I practice every day.")
        self.assertEqual(result["duration_seconds"], 1.0)

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
            language_runtime,
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
            language_runtime, "_groq_chat", return_value="What kind of books do you enjoy?"
        ) as groq:
            result = main._get_groq_chat_response("I enjoy reading books")

        self.assertEqual(result["grammar_feedback"], "Correct")
        groq.assert_called_once()
