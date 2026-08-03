from tests.plp_generator_test_support import PlpGeneratorTestBase
from tests.plp_test_support import *


class GeneratorTests(PlpGeneratorTestBase):
    def test_strict_schema_uses_unambiguous_typed_buckets(self):
        schema = _lesson_json_schema(
            ["concept", "listening_comprehension"],
            blueprint=ACTIVITY_BLUEPRINTS["listening"],
        )
        buckets = schema["properties"]["activities"]["properties"]
        self.assertEqual(
            list(buckets), ["concept", "listening_comprehension"]
        )
        self.assertEqual(buckets["concept"]["minItems"], 1)
        self.assertEqual(buckets["listening_comprehension"]["minItems"], 2)
        self.assertNotIn("oneOf", json.dumps(schema))

    def test_curated_catalog_and_checkpoints_validate_without_a_writer_model(self):
        generator = LessonGenerator(provider="curated")
        domains = (
            "vocabulary", "grammar", "reading", "listening",
            "speaking", "pronunciation", "discourse",
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
                self.assertGreaterEqual(
                    len(generated["content"]["activities"]), 2
                )
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

        with patch("plp.generator.time.sleep") as sleep:
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

        with patch("plp.generator.time.sleep"):
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
