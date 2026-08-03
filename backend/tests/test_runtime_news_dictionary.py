from tests.pronunciation_test_support import *


class RuntimeNewsDictionaryTests(unittest.TestCase):
    def test_news_rewrite_uses_groq(self):
        with patch.object(
            news_runtime,
            "_groq_chat",
            return_value="A simple summary.",
        ) as groq:
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
            patch.object(
                news_runtime,
                "rewrite_news",
                return_value="A simple sports summary.",
            ),
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
            patch.object(language_runtime, "_groq_client", return_value=Mock()),
            patch.object(main.plp_service, "get_profile", return_value=profile),
            patch.object(
                language_runtime,
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
            patch.object(pronunciation_text, "_groq_client", return_value=client),
        ):
            coaching, error, source = main.get_pronunciation_coaching("car", evidence)

        self.assertIsNone(error)
        self.assertIn("tongue", coaching)
        self.assertEqual(source, "groq")
        arguments = client.chat.completions.create.call_args.kwargs
        self.assertEqual(arguments["model"], "openai/gpt-oss-120b")
