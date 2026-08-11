from tests.learning_plan.support.plp_test_support import (
    Activity,
    ActivityAttemptInput,
    LearnerProfileInput,
    Mock,
    PublicLessonContent,
    ValidationError,
    _ensure_local_user,
    _grade_activity,
    _sanitize_content,
    build_outline,
    get_curated_template,
    planning_skills,
    profile,
    unittest,
)


class PlpContractTests(unittest.TestCase):
    def test_new_local_user_is_flushed_before_dependent_profile(self):
        session = Mock()
        session.get.return_value = None
        _ensure_local_user(session)
        session.add.assert_called_once()
        session.flush.assert_called_once_with()

    def test_profile_rejects_unsupported_level_and_schedule(self):
        with self.assertRaises(ValidationError):
            profile(level="C1")
        with self.assertRaises(ValidationError):
            LearnerProfileInput(
                cefr_level="B1",
                native_language="Arabic",
                learning_goals=["Speak confidently"],
                interests=["Technology"],
                days_per_week=4,
            )

    def test_profile_derives_internal_defaults_without_extra_questions(self):
        value = LearnerProfileInput(
            cefr_level="A2",
            native_language="Arabic",
            learning_goals=["Travel independently"],
            interests=["Travel"],
        )
        self.assertEqual(value.support_language, "Arabic")
        self.assertEqual(value.days_per_week, 5)
        self.assertEqual(value.minutes_per_day, 20)
        self.assertEqual(value.accent_preference, "no_preference")
        self.assertEqual(value.preferred_contexts, [])
        self.assertEqual(value.pronunciation_priorities, [])
        with self.assertRaises(ValidationError):
            LearnerProfileInput(
                cefr_level="B1",
                native_language="Arabic",
                learning_goals=["Speak confidently"],
                interests=["Technology"],
                minutes_per_day=30,
            )

    def test_profile_accepts_music_and_history_as_distinct_interests(self):
        value = LearnerProfileInput(
            cefr_level="B1",
            native_language="Arabic",
            learning_goals=["Speak confidently"],
            interests=["Music", "History"],
        )

        outline = build_outline(value, planning_skills(), variation_seed="interests")
        labels = {week["mission"]["interest"]["label"] for week in outline["weeks"]}

        self.assertEqual(labels, {"Music", "History"})

    def test_profile_rejects_an_interest_the_planner_cannot_use(self):
        with self.assertRaisesRegex(ValidationError, "unsupported learner interest"):
            LearnerProfileInput(
                cefr_level="B1",
                native_language="Arabic",
                learning_goals=["Speak confidently"],
                interests=["Underwater basket weaving"],
            )

    def test_activity_rejects_unknown_answers(self):
        with self.assertRaises(ValidationError):
            Activity.model_validate(
                {
                    "id": "question_1",
                    "type": "multiple_choice",
                    "required": True,
                    "source_refs": ["source"],
                    "data": {
                        "prompt": "Choose.",
                        "options": [
                            {"id": "a", "text": "One"},
                            {"id": "b", "text": "Two"},
                        ],
                        "correct_option_id": "missing",
                        "explanation": "Because.",
                    },
                }
            )

    def test_mobile_payload_hides_answer_keys(self):
        content = {
            "intro": "Intro",
            "activities": [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "data": {
                        "options": [],
                        "correct_option_id": "a",
                        "explanation": "Explanation",
                    },
                },
                {
                    "id": "q2",
                    "type": "fill_blank",
                    "data": {
                        "accepted_answers": ["answer"],
                        "explanation": "Explanation",
                    },
                },
            ],
        }
        sanitized = _sanitize_content(content)
        self.assertNotIn("correct_option_id", sanitized["activities"][0]["data"])
        self.assertNotIn("accepted_answers", sanitized["activities"][1]["data"])
        self.assertNotEqual(
            sanitized["activities"][0]["data"]["explanation"], "Explanation"
        )
        self.assertIn("correct_option_id", content["activities"][0]["data"])
        PublicLessonContent.model_validate(sanitized)

    def test_mobile_payload_removes_legacy_listening_boilerplate(self):
        content = {
            "intro": "Listen for one practical detail.",
            "activities": [
                {
                    "id": "listen_1",
                    "type": "listening_comprehension",
                    "source_refs": ["project_core_a1_b2_v1"],
                    "data": {
                        "title": "Club update",
                        "transcript": (
                            "Where will the group meet?\n"
                            "The group will meet in the community hall.\n"
                            "Please answer.\n"
                            "The group compares this detail before choosing an option.\n"
                            "Each person checks the supplied information before agreeing."
                        ),
                        "question": {
                            "prompt": "Where will the group meet?",
                            "options": [
                                {"id": "a", "text": "In the community hall"},
                                {"id": "b", "text": "At the station"},
                            ],
                            "correct_option_id": "a",
                            "explanation": "The transcript states the meeting place.",
                        },
                        "voice": "american",
                    },
                },
                {
                    "id": "concept_2",
                    "type": "concept",
                    "source_refs": ["project_core_a1_b2_v1"],
                    "data": {
                        "explanation": "Listen for the confirmed meeting place.",
                        "key_points": [
                            "Separate the key detail from supporting context."
                        ],
                        "examples": ["The community hall is the confirmed place."],
                        "native_hint": None,
                    },
                },
            ],
        }

        sanitized = _sanitize_content(content)

        transcript = sanitized["activities"][0]["data"]["transcript"]
        self.assertEqual(
            transcript,
            "The group will meet in the community hall.",
        )
        self.assertIn("Please answer.", content["activities"][0]["data"]["transcript"])
        PublicLessonContent.model_validate(sanitized)

    def test_mobile_payload_moves_legacy_concept_ref_out_of_source_refs(self):
        concept_id = "cefr_j_profiles_2020:vocabulary:abc123"
        content = {
            "intro": "Learn a source-grounded word.",
            "activities": [
                {
                    "id": "vocab_1",
                    "type": "vocabulary_card",
                    "source_refs": [
                        f"concept:{concept_id}",
                        "cefr_j_profiles_2020",
                        "princeton_wordnet_3_0",
                        "cmudict_local",
                    ],
                    "data": {
                        "word": "network",
                        "part_of_speech": "noun",
                        "ipa": "netwurk",
                        "definition": "A connected group.",
                        "examples": ["The network links each office."],
                        "collocations": [],
                    },
                },
                {
                    "id": "concept_2",
                    "type": "concept",
                    "source_refs": ["cefr_j_profiles_2020"],
                    "data": {"explanation": "Use the word in context."},
                },
            ],
        }

        sanitized = _sanitize_content(content)

        self.assertEqual(sanitized["activities"][0]["data"]["concept_id"], concept_id)
        self.assertEqual(
            sanitized["activities"][0]["source_refs"],
            [
                "cefr_j_profiles_2020",
                "princeton_wordnet_3_0",
                "cmudict_local",
            ],
        )
        PublicLessonContent.model_validate(sanitized)

    def test_mobile_payload_repairs_dated_website_definition(self):
        content = {
            "intro": "Learn a useful technology word.",
            "activities": [
                {
                    "id": "vocab_website",
                    "type": "vocabulary_card",
                    "source_refs": [
                        "cefr_j_profiles_2020",
                        "princeton_wordnet_3_0",
                        "cmudict_local",
                    ],
                    "data": {
                        "word": "website",
                        "part_of_speech": "noun",
                        "ipa": "websait",
                        "definition": (
                            "a computer connected to the internet that maintains "
                            "a series of web pages"
                        ),
                        "examples": ["Open the website to read the details."],
                        "collocations": [],
                        "native_hint": None,
                    },
                },
                {
                    "id": "concept_website",
                    "type": "concept",
                    "source_refs": ["project_core_a1_b2_v1"],
                    "data": {
                        "explanation": "Use the word for an internet location.",
                        "key_points": ["A website contains connected pages."],
                        "examples": ["I visited the school website."],
                        "native_hint": None,
                    },
                },
            ],
        }

        sanitized = _sanitize_content(content)

        self.assertEqual(
            sanitized["activities"][0]["data"]["definition"],
            "a group of connected pages that you can visit on the internet",
        )
        self.assertEqual(
            sanitized["activities"][0]["data"]["source_definition"],
            content["activities"][0]["data"]["definition"],
        )
        self.assertEqual(
            sanitized["activities"][0]["data"]["definition_origin"],
            "reviewed_project_gloss",
        )
        # Sanitizing the public copy does not rewrite immutable stored content.
        self.assertTrue(
            content["activities"][0]["data"]["definition"].startswith("a computer")
        )
        PublicLessonContent.model_validate(sanitized)

    def test_mobile_payload_restores_reviewed_fill_prompt(self):
        content = {
            "intro": "Ask for clarification.",
            "activities": [
                {
                    "id": "fill_1",
                    "type": "fill_blank",
                    "source_refs": ["project_core_a1_b2_v1"],
                    "data": {
                        "prompt": "Could you repeat the ___, please?",
                        "accepted_answers": ["mean"],
                        "explanation": "The clarification frame uses mean.",
                    },
                },
                {
                    "id": "concept_2",
                    "type": "concept",
                    "source_refs": ["project_core_a1_b2_v1"],
                    "data": {"explanation": "Use a clarification question."},
                },
            ],
        }

        sanitized = _sanitize_content(
            content,
            reviewed_template=get_curated_template("A2", "speaking"),
        )

        self.assertEqual(
            sanitized["activities"][0]["data"]["prompt"],
            "Do you ___ Thursday at three?",
        )
        PublicLessonContent.model_validate(sanitized)

    def test_server_grades_normalized_fill_blank(self):
        correct, score, _, evidence = _grade_activity(
            {
                "type": "fill_blank",
                "data": {
                    "accepted_answers": ["has finished"],
                    "explanation": "Present perfect.",
                },
            },
            ActivityAttemptInput(text_answer="  HAS   FINISHED "),
        )
        self.assertTrue(correct)
        self.assertEqual(score, 100)
        self.assertTrue(evidence)
