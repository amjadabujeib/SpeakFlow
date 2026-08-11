# ruff: noqa: F405

import os

from speakflow.shared.groq_keys import configured_groq_api_keys
from tests.learning_plan.support.plp_generator_test_support import PlpGeneratorTestBase
from tests.learning_plan.support.plp_test_support import (
    ACTIVITY_BLUEPRINTS,
    GenerationError,
    LessonGenerator,
    Mock,
    RateLimitError,
    RetrievedChunk,
    _lesson_json_schema,
    _validate_choice,
    _validate_fill_blank,
    _validate_pronunciation,
    get_curated_template,
    httpx,
    json,
    patch,
)


class GeneratorTests(PlpGeneratorTestBase):
    def test_plural_groq_keys_are_ordered_deduplicated_and_explicit(self):
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEYS": " first-key, second-key,first-key ",
            },
        ):
            self.assertEqual(
                configured_groq_api_keys(),
                ("first-key", "second-key"),
            )

    def test_groq_key_list_accepts_one_or_many_credentials(self):
        with patch.dict(os.environ, {"GROQ_API_KEYS": "only-key"}, clear=True):
            self.assertEqual(configured_groq_api_keys(), ("only-key",))

        keys = tuple(f"key-{index}" for index in range(25))
        with patch.dict(
            os.environ,
            {"GROQ_API_KEYS": ",".join(keys)},
            clear=True,
        ):
            self.assertEqual(configured_groq_api_keys(), keys)

    def test_plp_rotates_to_next_key_immediately_after_rate_limit(self):
        response = httpx.Response(
            429,
            headers={"retry-after": "60"},
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat"),
        )
        rate_limit = RateLimitError(
            "Rate limit reached",
            response=response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        first = Mock()
        second = Mock()
        first.chat.completions.create.side_effect = rate_limit
        second.chat.completions.create.return_value = self._valid_listening_response()
        generator = LessonGenerator(clients=[first, second], provider="groq")

        raw = generator.request_structured(
            messages=[],
            schema={"type": "object"},
            schema_name="rotation_test",
            max_tokens=20,
        )

        self.assertTrue(raw)
        first.chat.completions.create.assert_called_once()
        second.chat.completions.create.assert_called_once()

    def test_plp_round_robins_successful_requests_across_keys(self):
        first = Mock()
        second = Mock()
        first.chat.completions.create.return_value = self._valid_listening_response()
        second.chat.completions.create.return_value = self._valid_listening_response()
        generator = LessonGenerator(clients=[first, second], provider="groq")
        arguments = {
            "messages": [],
            "schema": {"type": "object"},
            "schema_name": "round_robin_test",
            "max_tokens": 20,
        }

        generator.request_structured(**arguments)
        generator.request_structured(**arguments)

        first.chat.completions.create.assert_called_once()
        second.chat.completions.create.assert_called_once()

    def test_exhausted_pool_reports_the_shortest_key_cooldown(self):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat")
        short_response = httpx.Response(
            429,
            headers={"retry-after": "2"},
            request=request,
        )
        long_response = httpx.Response(
            429,
            headers={"retry-after": "60"},
            request=request,
        )
        short_limit = RateLimitError(
            "first key",
            response=short_response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        long_limit = RateLimitError(
            "second key",
            response=long_response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        first = Mock()
        second = Mock()
        first.chat.completions.create.side_effect = short_limit
        second.chat.completions.create.side_effect = long_limit
        generator = LessonGenerator(clients=[first, second], provider="groq")

        with self.assertRaises(RateLimitError) as raised:
            generator.request_structured(
                messages=[],
                schema={"type": "object"},
                schema_name="all_limited_test",
                max_tokens=20,
            )

        self.assertIs(raised.exception, short_limit)

    def test_strict_schema_uses_unambiguous_typed_buckets(self):
        schema = _lesson_json_schema(
            ["concept", "listening_comprehension"],
            blueprint=ACTIVITY_BLUEPRINTS["listening"],
        )
        buckets = schema["properties"]["activities"]["properties"]
        self.assertEqual(list(buckets), ["concept", "listening_comprehension"])
        self.assertEqual(buckets["concept"]["minItems"], 1)
        self.assertEqual(buckets["listening_comprehension"]["minItems"], 2)
        self.assertNotIn("oneOf", json.dumps(schema))

    def test_curated_catalog_and_checkpoints_validate_without_a_writer_model(self):
        generator = LessonGenerator(provider="curated")
        domains = (
            "vocabulary",
            "grammar",
            "reading",
            "listening",
            "speaking",
            "pronunciation",
            "discourse",
        )
        validated = 0
        for level in ("A1", "A2", "B1", "B2"):
            chunks = []
            for domain in domains:
                chunk = RetrievedChunk(
                    id=f"core_{level.casefold()}_{domain}_001",
                    source_id="project_core_curriculum_v1",
                    content="reviewed",
                    metadata={
                        "lesson_template": get_curated_template(level, domain),
                        "skill_ids": [f"{domain}.{level.casefold()}.core"],
                    },
                    score=1.0,
                )
                chunks.append(chunk)
                generator.generate(
                    specification={
                        "domain": domain,
                        "title": domain,
                        "description": domain,
                        "cefr_level": level,
                        "skill_ids": [f"{domain}.{level.casefold()}.core"],
                    },
                    lesson_key=f"audit_{level}_{domain}",
                    chunks=[chunk],
                    support_language="Arabic",
                )
                validated += 1
            for count in (1, 4):
                generated, _ = generator.generate(
                    specification={
                        "domain": "assessment",
                        "title": "Checkpoint",
                        "description": "Review the week's targets.",
                        "cefr_level": level,
                        "skill_ids": [
                            f"{domain}.{level.casefold()}.core"
                            for domain in domains[:count]
                        ],
                    },
                    lesson_key=f"audit_{level}_checkpoint_{count}",
                    chunks=chunks[:count],
                    support_language="Arabic",
                )
                self.assertGreaterEqual(len(generated["content"]["activities"]), 2)
                validated += 1
        self.assertEqual(validated, 36)

    def test_quality_rejects_multi_answer_listening_question(self):
        with self.assertRaisesRegex(ValueError, "opinions, examples, or multiple"):
            _validate_choice(
                {
                    "prompt": "What are some key features of the new smartwatch?",
                    "options": [
                        {"id": "a", "text": "Fitness tracking"},
                        {"id": "b", "text": "GPS navigation"},
                        {"id": "c", "text": "Notification alerts"},
                    ],
                    "correct_option_id": "a",
                    "explanation": "Fitness tracking is one listed feature.",
                },
                domain="listening",
                context=(
                    "It has fitness tracking, GPS navigation, and notification alerts."
                ),
            )

    def test_quality_rejects_subjective_speaking_answer(self):
        with self.assertRaisesRegex(ValueError, "opinions, examples, or multiple"):
            _validate_choice(
                {
                    "prompt": "What do you think about social media?",
                    "options": [
                        {"id": "a", "text": "It has a positive effect"},
                        {"id": "b", "text": "It has a negative effect"},
                        {"id": "c", "text": "It has no effect"},
                    ],
                    "correct_option_id": "b",
                    "explanation": "It has a negative effect is the selected opinion.",
                },
                domain="speaking",
            )

    def test_quality_rejects_contradictory_fill_answers(self):
        with self.assertRaisesRegex(ValueError, "variants of one answer"):
            _validate_fill_blank(
                {
                    "prompt": "The main difference is ______.",
                    "accepted_answers": [
                        "the ability to perform complex tasks",
                        "the need for an internet connection",
                        "the user interface",
                    ],
                    "explanation": "The answer is the ability to perform complex tasks.",
                }
            )

    def test_quality_rejects_pronunciation_item_without_target(self):
        with self.assertRaisesRegex(ValueError, "does not contain target"):
            _validate_pronunciation(
                {
                    "ipa": "/p/",
                    "practice_items": [
                        "Please put the paper here.",
                        "I sent the file on Monday.",
                    ],
                },
                set(),
            )

    def test_quality_rejects_non_segmental_pronunciation_target(self):
        with self.assertRaisesRegex(ValueError, "assessable segmental"):
            _validate_pronunciation(
                {
                    "ipa": "/ˈ/",
                    "instructions": "Lengthen the stressed syllable.",
                    "tips": ["Use pitch and length."],
                    "practice_items": ["Tuesday", "Thursday"],
                },
                set(),
            )

    def test_quality_uses_canonical_phones_not_only_visible_spelling(self):
        with self.assertRaisesRegex(ValueError, "no canonical occurrence"):
            _validate_pronunciation(
                {
                    "ipa": "/ə/",
                    "instructions": "Relax the jaw for the central vowel.",
                    "tips": ["Shorten the syllable."],
                    "practice_items": ["We could have asked them earlier.", "about"],
                },
                set(),
            )

    def test_generator_validates_and_flattens_strict_groq_payload(self):
        client = Mock()
        client.chat.completions.create.return_value = self._valid_listening_response()
        generator = LessonGenerator(client=client, provider="groq")
        generated, refs = self._generate_listening(generator)
        self.assertEqual(refs, ["project_core_curriculum_v1"])
        self.assertEqual(
            [item["type"] for item in generated["content"]["activities"]],
            ["concept", "listening_comprehension", "listening_comprehension"],
        )
        request = client.chat.completions.create.call_args.kwargs
        self.assertTrue(request["response_format"]["json_schema"]["strict"])

    def test_rate_limit_waits_once_inside_the_two_call_budget(self):
        response = httpx.Response(
            429,
            headers={"retry-after": "0.1"},
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat"),
        )
        rate_limit = RateLimitError(
            "Rate limit reached",
            response=response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        client = Mock()
        client.chat.completions.create.side_effect = [
            rate_limit,
            self._valid_listening_response(),
        ]
        generator = LessonGenerator(client=client, provider="groq")

        with patch(
            "speakflow.features.learning_plan.engine.generator.time.sleep"
        ) as sleep:
            generated, _ = self._generate_listening(generator)

        self.assertEqual(generated["title"], "Listening for key details")
        self.assertEqual(client.chat.completions.create.call_count, 2)
        sleep.assert_called_once_with(0.35)

    def test_second_rate_limit_becomes_a_safe_actionable_failure(self):
        response = httpx.Response(
            429,
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat"),
        )
        rate_limit = RateLimitError(
            "raw provider detail",
            response=response,
            body={"error": {"code": "rate_limit_exceeded"}},
        )
        client = Mock()
        client.chat.completions.create.side_effect = [rate_limit, rate_limit]
        generator = LessonGenerator(client=client, provider="groq")

        with patch("speakflow.features.learning_plan.engine.generator.time.sleep"):
            with self.assertRaisesRegex(
                GenerationError,
                "temporarily rate-limited after one bounded retry",
            ) as raised:
                self._generate_listening(generator)

        self.assertNotIn("raw provider detail", str(raised.exception))
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_pydantic_value_error_is_serialized_for_semantic_repair(self):
        invalid = self._valid_listening_response()
        payload = json.loads(invalid.choices[0].message.content)
        payload["activities"]["listening_comprehension"][0]["question"][
            "correct_option_id"
        ] = "missing"
        invalid.choices[0].message.content = json.dumps(payload)
        client = Mock()
        client.chat.completions.create.side_effect = [
            invalid,
            self._valid_listening_response(),
        ]
        generator = LessonGenerator(client=client, provider="groq")

        generated, _ = self._generate_listening(generator)

        self.assertEqual(generated["title"], "Listening for key details")
        self.assertEqual(client.chat.completions.create.call_count, 2)
        repair_request = client.chat.completions.create.call_args.kwargs
        self.assertIn(
            "correct_option_id",
            repair_request["messages"][1]["content"],
        )
