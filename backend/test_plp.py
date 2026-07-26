import json
import unittest
import uuid
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import httpx
from openai import RateLimitError
from pydantic import ValidationError

from plp.audit_generation import audit_generation
from plp.database import get_engine, session_scope
from plp.curated_lessons import get_curated_template
from plp.generator import GenerationError, LessonGenerator, _lesson_json_schema
from plp.ingest import _validate_skill_graph
from plp.lesson_quality import (
    ACTIVITY_BLUEPRINTS,
    _validate_choice,
    _validate_fill_blank,
    _validate_pronunciation,
)
from plp.planner import PlanningSkill, build_outline
from plp.models import GenerationJob, PlanLesson, utc_now
from plp.retrieval import CurriculumRetriever, RetrievedChunk
from plp.schemas import Activity, LearnerProfileInput, PublicLessonContent
from plp.seed import seed_records
from plp.service import (
    PlpInvalidAttemptError,
    PlpService,
    _activity_skill_ids,
    _ensure_local_user,
    _grade_activity,
    _latest_lesson_score,
    _pronunciation_activity_complete,
    _sanitize_content,
    _verified_completed_activity_ids,
)
from plp.schemas import ActivityAttemptInput


def profile(level="B1"):
    return LearnerProfileInput(
        cefr_level=level,
        native_language="Arabic",
        learning_goals=["Speak confidently", "Communicate at work"],
        interests=["Technology", "Travel"],
    )


def planning_skills():
    _, skills, _ = seed_records()
    return [
        PlanningSkill(
            id=item["id"],
            domain=item["domain"],
            level=item["cefr_level"],
            title=item["title"],
            description=item["description"],
            outcomes=item["outcomes"],
        )
        for item in skills
    ]


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
        labels = {
            week["mission"]["interest"]["label"]
            for week in outline["weeks"]
        }

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
        self.assertNotIn(
            "correct_option_id", sanitized["activities"][0]["data"]
        )
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

        self.assertEqual(
            sanitized["activities"][0]["data"]["concept_id"], concept_id
        )
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
        self.assertTrue(content["activities"][0]["data"]["definition"].startswith("a computer"))
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

    def test_pronunciation_drill_requires_trusted_acoustic_result(self):
        activity = {
            "type": "pronunciation_drill",
            "data": {"practice_items": ["think", "Thursday"]},
        }
        with self.assertRaisesRegex(
            PlpInvalidAttemptError,
            "record and score",
        ):
            _grade_activity(activity, ActivityAttemptInput())

        passed, score, explanation, evidence = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "think",
                "accuracy": 88,
                "completeness": 100,
            },
        )
        self.assertTrue(passed)
        self.assertEqual(score, 90)
        self.assertIn("passed", explanation)
        self.assertTrue(evidence)

        passed, score, explanation, _ = _grade_activity(
            activity,
            ActivityAttemptInput(),
            trusted_pronunciation={
                "target": "think",
                "accuracy": 60,
                "completeness": 100,
            },
        )
        self.assertFalse(passed)
        self.assertEqual(score, 68)
        self.assertIn("Try again", explanation)

    def test_legacy_click_through_is_not_a_verified_pronunciation_pass(self):
        lesson = SimpleNamespace(
            id=uuid.uuid4(),
            content={
                "content": {
                    "activities": [
                        {
                            "id": "sound_check",
                            "type": "pronunciation_drill",
                            "required": True,
                        },
                        {
                            "id": "technique",
                            "type": "concept",
                            "required": True,
                        },
                    ]
                }
            },
        )
        progress = SimpleNamespace(
            completed_activity_ids=["sound_check", "technique"]
        )
        session = Mock()
        session.scalars.return_value.all.return_value = []

        visible = _verified_completed_activity_ids(session, lesson, progress)

        self.assertEqual(visible, ["technique"])

    def test_pronunciation_activity_requires_every_assigned_target(self):
        activity = {
            "id": "sound_check",
            "type": "pronunciation_drill",
            "data": {
                "practice_items": [
                    "project plan",
                    {"text": "payment problem"},
                    "Please print the proposal.",
                ]
            },
        }

        def passed(target):
            return SimpleNamespace(
                activity_id="sound_check",
                correct=True,
                response={
                    "pronunciation": {
                        "target": target,
                        "accuracy": 90,
                        "completeness": 100,
                    }
                },
            )

        attempts = [passed("project plan"), passed("payment problem")]
        self.assertFalse(_pronunciation_activity_complete(activity, attempts))

        attempts.append(passed("Please print the proposal."))
        self.assertTrue(_pronunciation_activity_complete(activity, attempts))

    def test_fill_grading_normalizes_unicode_apostrophe_and_terminal_punctuation(self):
        correct, score, _, _ = _grade_activity(
            {
                "type": "fill_blank",
                "data": {
                    "accepted_answers": ["don't"],
                    "explanation": "The expected contraction is don't.",
                },
            },
            ActivityAttemptInput(text_answer="DON’T!"),
        )
        self.assertTrue(correct)
        self.assertEqual(score, 100)

    def test_invalid_choice_id_is_rejected_instead_of_recorded_as_wrong(self):
        with self.assertRaises(PlpInvalidAttemptError):
            _grade_activity(
                {
                    "type": "multiple_choice",
                    "data": {
                        "options": [
                            {"id": "a", "text": "One"},
                            {"id": "b", "text": "Two"},
                            {"id": "c", "text": "Three"},
                        ],
                        "correct_option_id": "a",
                        "explanation": "One is correct.",
                    },
                },
                ActivityAttemptInput(selected_option_id="not_an_option"),
            )

    def test_lesson_score_keeps_unanswered_items_in_the_denominator(self):
        lesson = Mock(
            id=uuid.uuid4(),
            content={
                "content": {
                    "activities": [
                        {
                            "id": f"q{index}",
                            "type": "multiple_choice",
                            "required": True,
                        }
                        for index in range(1, 4)
                    ]
                }
            },
        )
        session = Mock()
        session.scalar.side_effect = [100, None, None]
        self.assertEqual(_latest_lesson_score(session, lesson), 33)

    def test_checkpoint_activity_evidence_targets_only_its_bound_skill(self):
        lesson = Mock(
            lesson_type="assessment",
            skill_ids=["grammar.b1.core", "listening.b1.core"],
        )
        activity = {"id": "q1", "skill_ids": ["listening.b1.core"]}
        self.assertEqual(
            _activity_skill_ids(activity, lesson),
            ["listening.b1.core"],
        )

    def test_first_submission_marked_correction_never_records_mastery_evidence(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            skill_ids=["listening.b1.core"],
            content={
                "content": {
                    "activities": [
                        {
                            "id": activity_id,
                            "type": "multiple_choice",
                            "required": True,
                            "skill_ids": ["listening.b1.core"],
                            "data": {
                                "options": [
                                    {"id": "a", "text": "Answer"},
                                    {"id": "b", "text": "Distractor"},
                                    {"id": "c", "text": "Distractor two"},
                                ],
                                "correct_option_id": "a",
                                "explanation": "That detail is stated directly.",
                            },
                        }
                    ]
                }
            },
        )
        session = Mock()
        session.get.return_value = None
        session.scalar.side_effect = [0, 100]
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = PlpService()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        service._update_lesson_completion = Mock(return_value=False)
        try:
            with (
                patch("plp.service.session_scope", return_value=context),
                patch("plp.service.SkillEvidence") as skill_evidence,
            ):
                result = service.record_attempt(
                    activity_id,
                    ActivityAttemptInput(
                        attempt_kind="correction",
                        selected_option_id="a",
                    ),
                )
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertTrue(result.first_attempt)
        self.assertFalse(result.mastery_evidence_recorded)
        skill_evidence.assert_not_called()

    def test_generation_audit_binds_the_reviewed_skill_to_its_specification(self):
        skill = Mock(
            title="Core listening",
            description="Follow the main idea.",
            outcomes=["Identify the main idea"],
        )
        session = Mock()
        session.scalar.return_value = skill
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        generator = MagicMock()
        generator.provider = "curated"
        generator.generate.return_value = (
            {
                "generator_version": "test",
                "title": "Audit lesson",
                "content": {"activities": []},
            },
            [],
        )

        with (
            patch("plp.audit_generation.session_scope", return_value=context),
            patch(
                "plp.audit_generation.CurriculumRetriever",
                return_value=retriever,
            ),
            patch("plp.audit_generation.LessonGenerator", return_value=generator),
        ):
            audit_generation(domain="listening", level="B1")

        specification = generator.generate.call_args.kwargs["specification"]
        self.assertEqual(specification["skill_ids"], ["listening.b1.core"])

    def test_checkpoint_cannot_pass_from_a_partial_new_attempt_session(self):
        lesson = Mock(
            id=uuid.uuid4(),
            lesson_type="assessment",
            specification={
                "completion_policy": {
                    "mode": "minimum_score",
                    "minimum_score": 75,
                }
            },
            content={
                "content": {
                    "activities": [
                        {
                            "id": "q1",
                            "type": "multiple_choice",
                            "required": True,
                        },
                        {
                            "id": "q2",
                            "type": "multiple_choice",
                            "required": True,
                        },
                    ]
                }
            },
        )
        progress = Mock(
            completed_activity_ids=["q1", "q2"],
            best_score=50,
            status="in_progress",
            completed_at=None,
        )
        session = Mock()
        session.scalars.return_value.all.return_value = ["q1"]
        service = PlpService()
        try:
            completed = service._update_lesson_completion(
                session,
                lesson,
                progress,
                attempt_session_id="session_12345678",
            )
        finally:
            service.retriever.close()
            service.generator.close()
        self.assertFalse(completed)
        self.assertEqual(progress.status, "in_progress")
        session.scalar.assert_not_called()

    def test_first_activity_attempt_initializes_progress_before_flush(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            skill_ids=[],
            content={
                "content": {
                    "activities": [
                        {
                            "id": activity_id,
                            "type": "multiple_choice",
                            "required": True,
                            "skill_ids": ["listening.b1.core"],
                            "data": {
                                "options": [
                                    {"id": "a", "text": "Answer"},
                                    {"id": "b", "text": "Distractor"},
                                    {"id": "c", "text": "Distractor two"},
                                ],
                                "correct_option_id": "a",
                                "explanation": "That detail is stated directly.",
                            },
                        }
                    ]
                }
            },
        )
        session = Mock()
        session.get.return_value = None
        session.scalar.side_effect = [0, 100]
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = PlpService()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        service._update_lesson_completion = Mock(return_value=False)
        try:
            with patch("plp.service.session_scope", return_value=context):
                result = service.record_attempt(
                    activity_id,
                    ActivityAttemptInput(selected_option_id="a"),
                )
        finally:
            service.retriever.close()
            service.generator.close()

        progress = next(
            call.args[0]
            for call in session.add.call_args_list
            if call.args[0].__class__.__name__ == "LessonProgress"
        )
        self.assertEqual(progress.status, "in_progress")
        self.assertEqual(progress.attempts, 1)
        self.assertEqual(progress.completed_activity_ids, [activity_id])
        self.assertTrue(result.correct)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.correct_response, {"selected_option_id": "a"})
        self.assertEqual(result.lesson_score, 100)
        self.assertFalse(result.lesson_completed)
        self.assertFalse(result.newly_completed)
        self.assertEqual(result.xp_awarded, 0)

    def test_attempt_awards_xp_only_on_the_completion_transition(self):
        activity_id = "w01_l01_listening_a01"
        lesson = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            lesson_type="listening",
            xp=20,
            skill_ids=["listening.b1.core"],
            content={
                "content": {
                    "activities": [
                        {
                            "id": activity_id,
                            "type": "multiple_choice",
                            "required": True,
                            "skill_ids": ["listening.b1.core"],
                            "data": {
                                "options": [
                                    {"id": "a", "text": "Answer"},
                                    {"id": "b", "text": "Distractor"},
                                    {"id": "c", "text": "Distractor two"},
                                ],
                                "correct_option_id": "a",
                                "explanation": "That detail is stated directly.",
                            },
                        }
                    ]
                }
            },
        )

        for initial_status, expected_new, expected_xp in (
            ("in_progress", True, 20),
            ("completed", False, 0),
        ):
            with self.subTest(initial_status=initial_status):
                progress = Mock(
                    status=initial_status,
                    completed_activity_ids=[activity_id],
                    best_score=100,
                    attempts=1,
                    completed_at=None,
                )
                session = Mock()
                session.get.return_value = progress
                session.scalar.side_effect = [1, 100]
                context = MagicMock()
                context.__enter__.return_value = session
                context.__exit__.return_value = False
                service = PlpService()
                service._find_active_lesson_by_activity = Mock(return_value=lesson)

                def complete_lesson(*_args, **_kwargs):
                    progress.status = "completed"
                    return True

                service._update_lesson_completion = Mock(
                    side_effect=complete_lesson
                )
                service._queue_next_generation = Mock()
                try:
                    with patch("plp.service.session_scope", return_value=context):
                        result = service.record_attempt(
                            activity_id,
                            ActivityAttemptInput(selected_option_id="a"),
                        )
                finally:
                    service.retriever.close()
                    service.generator.close()

                self.assertEqual(result.lesson_score, 100)
                self.assertTrue(result.lesson_completed)
                self.assertEqual(result.newly_completed, expected_new)
                self.assertEqual(result.xp_awarded, expected_xp)
                self.assertEqual(
                    service._queue_next_generation.call_count,
                    1 if expected_new else 0,
                )

    def test_reset_preserves_account_and_deletes_user_learning_state(self):
        session = Mock()
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = PlpService()
        try:
            with patch("plp.service.session_scope", return_value=context):
                result = service.reset_local_learner()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(result, {"status": "reset"})
        self.assertEqual(session.execute.call_count, 8)
        session.delete.assert_not_called()


class PlannerTests(unittest.TestCase):
    def test_seed_skill_graph_is_acyclic(self):
        _, skills, _ = seed_records()
        _validate_skill_graph(skills)

    def test_all_supported_levels_make_four_ordered_weeks(self):
        skills = planning_skills()
        for level in ("A1", "A2", "B1", "B2"):
            with self.subTest(level=level):
                outline = build_outline(profile(level=level), skills)
                self.assertEqual(len(outline["weeks"]), 4)
                flattened = [
                    lesson
                    for week in outline["weeks"]
                    for unit in week["units"]
                    for lesson in unit["lessons"]
                ]
                seen = set()
                for lesson in flattened:
                    self.assertTrue(set(lesson["required_lesson_keys"]).issubset(seen))
                    seen.add(lesson["lesson_key"])
                self.assertEqual(len(seen), len(flattened))

    def test_schedule_is_fixed_and_each_week_uses_the_mission_role_dag(self):
        skills = planning_skills()
        outline = build_outline(profile(), skills)
        self.assertEqual(outline["architecture"], "mission_v3")
        self.assertEqual(outline["schedule"]["days_per_week"], 5)
        self.assertEqual(outline["schedule"]["minutes_per_day"], 20)
        previous_checkpoint = None
        for week in outline["weeks"]:
            lessons = week["units"][0]["lessons"]
            self.assertEqual(len(lessons), 5)
            self.assertEqual(
                [item["specification"]["lesson_role"] for item in lessons],
                [
                    "input_noticing",
                    "language_tools",
                    "guided_interaction",
                    "independent_transfer",
                    "checkpoint",
                ],
            )
            expected_roots = [previous_checkpoint] if previous_checkpoint else []
            self.assertEqual(lessons[0]["required_lesson_keys"], expected_roots)
            self.assertEqual(lessons[1]["required_lesson_keys"], expected_roots)
            self.assertEqual(
                lessons[2]["required_lesson_keys"],
                [lessons[0]["lesson_key"], lessons[1]["lesson_key"]],
            )
            self.assertEqual(
                lessons[3]["required_lesson_keys"],
                [lessons[2]["lesson_key"]],
            )
            self.assertEqual(lessons[-1]["type"], "assessment")
            self.assertEqual(
                lessons[-1]["lesson_key"],
                f"w{week['sequence']:02d}_l05_assessment",
            )
            self.assertEqual(
                lessons[-1]["required_lesson_keys"],
                [item["lesson_key"] for item in lessons[:4]],
            )
            self.assertEqual(
                lessons[-1]["specification"]["completion_policy"]["minimum_score"],
                75,
            )
            previous_checkpoint = lessons[-1]["lesson_key"]

    def test_weekly_missions_rotate_profile_dimensions_and_do_not_repeat(self):
        first = build_outline(profile(), planning_skills())
        second = build_outline(profile(), planning_skills())
        first_missions = [week["mission"] for week in first["weeks"]]
        self.assertEqual(first_missions, [week["mission"] for week in second["weeks"]])
        self.assertEqual(
            [item["goal"]["id"] for item in first_missions],
            [
                "confident_conversation",
                "workplace_communication",
                "confident_conversation",
                "workplace_communication",
            ],
        )
        self.assertEqual(
            [item["interest"]["id"] for item in first_missions],
            ["technology", "travel", "technology", "travel"],
        )
        scenario_ids = [item["scenario"]["id"] for item in first_missions]
        self.assertEqual(len(scenario_ids), len(set(scenario_ids)))

        for week, mission in zip(first["weeks"], first_missions, strict=True):
            for lesson in week["units"][0]["lessons"]:
                specification = lesson["specification"]
                self.assertEqual(specification["architecture"], "mission_v3")
                self.assertEqual(specification["can_do"], mission["can_do"])
                self.assertEqual(specification["goal"], mission["goal"])
                self.assertEqual(specification["interest"], mission["interest"])
                self.assertEqual(specification["scenario"], mission["scenario"])
                self.assertEqual(specification["mission"], mission["mission"])
                self.assertEqual(specification["cefr_realization"]["level"], "B1")

    def test_cefr_changes_the_reviewed_mission_realization(self):
        skills = planning_skills()
        a1 = build_outline(profile(level="A1"), skills)["weeks"][0]["mission"]
        b2 = build_outline(profile(level="B2"), skills)["weeks"][0]["mission"]
        self.assertEqual(a1["scenario"]["id"], b2["scenario"]["id"])
        self.assertNotEqual(a1["can_do"], b2["can_do"])
        self.assertLess(
            a1["cefr_realization"]["maximum_sentence_words"],
            b2["cefr_realization"]["maximum_sentence_words"],
        )
        self.assertLess(
            a1["cefr_realization"]["input_word_range"][1],
            b2["cefr_realization"]["input_word_range"][1],
        )

    def test_same_domain_micro_skills_are_kept_as_distinct_records(self):
        same_domain_skills = [
            PlanningSkill(
                id=f"interaction.b1.skill_{index}",
                domain="speaking",
                level="B1",
                title=f"Interaction skill {index}",
                description=f"Use interaction move {index}.",
                outcomes=[f"Can use interaction move {index}."],
            )
            for index in range(1, 5)
        ]
        outline = build_outline(profile(), same_domain_skills)
        first_week = outline["weeks"][0]["units"][0]["lessons"]
        self.assertEqual(
            {lesson["skill_ids"][0] for lesson in first_week[:4]},
            {skill.id for skill in same_domain_skills},
        )
        self.assertEqual({lesson["type"] for lesson in first_week[:4]}, {"speaking"})

    def test_later_checkpoints_include_one_distinct_spaced_review_skill(self):
        outline = build_outline(profile(), planning_skills())
        for week in outline["weeks"][1:]:
            lessons = week["units"][0]["lessons"]
            current = {skill for lesson in lessons[:4] for skill in lesson["skill_ids"]}
            checkpoint = lessons[-1]
            review = checkpoint["specification"]["review_skill_ids"]
            self.assertEqual(len(review), 1)
            self.assertNotIn(review[0], current)
            self.assertEqual(len(checkpoint["skill_ids"]), 5)

    def test_adaptation_priority_reinforces_without_removing_core(self):
        skills = planning_skills()
        baseline = build_outline(profile(), skills)
        adapted = build_outline(
            profile(),
            skills,
            priority_skill_ids=["grammar.b1.core"],
        )

        def teaching_skill_ids(outline):
            return [
                lesson["skill_ids"][0]
                for week in outline["weeks"]
                for unit in week["units"]
                for lesson in unit["lessons"]
                if lesson["type"] != "assessment"
            ]

        baseline_ids = teaching_skill_ids(baseline)
        adapted_ids = teaching_skill_ids(adapted)
        self.assertGreater(
            adapted_ids.count("grammar.b1.core"),
            baseline_ids.count("grammar.b1.core"),
        )
        self.assertTrue(set(baseline_ids).issubset(set(adapted_ids)))


class GeneratorTests(unittest.TestCase):
    @staticmethod
    def _valid_listening_response():
        payload = {
            "title": "Listening for key details",
            "description": "Follow a clear conversation about technology.",
            "intro": "Listen for the main idea and its supporting detail.",
            "activities": {
                "concept": [
                    {
                        "explanation": "Contrast markers such as however signal that the speaker is changing direction.",
                        "key_points": [
                            "Listen for however before an important contrast",
                            "Write only the detail that answers the question",
                        ],
                        "examples": [
                            "The battery improved; however, the camera stayed the same."
                        ],
                        "native_hint": None,
                    }
                ],
                "listening_comprehension": [
                    {
                        "title": "A useful phone update",
                        "transcript": "The update improves battery life. However, the camera quality remains unchanged.",
                        "question": {
                            "prompt": "Which feature does the update improve?",
                            "options": [
                                {"id": "a", "text": "Battery life"},
                                {"id": "b", "text": "Screen size"},
                                {"id": "c", "text": "Call quality"},
                            ],
                            "correct_option_id": "a",
                            "explanation": "Battery life is the only feature described as improved.",
                        },
                        "voice": "american",
                    },
                    {
                        "title": "Choosing a smartwatch",
                        "transcript": "Maya compares three watches. She chooses the Nova because its battery lasts for five days.",
                        "question": {
                            "prompt": "Why does Maya choose the Nova watch?",
                            "options": [
                                {"id": "a", "text": "Its battery lasts longer"},
                                {"id": "b", "text": "It has a brighter screen"},
                                {"id": "c", "text": "It includes free headphones"},
                            ],
                            "correct_option_id": "a",
                            "explanation": "She chooses it because its battery lasts for five days.",
                        },
                        "voice": "american",
                    },
                ],
            },
        }
        response = Mock()
        response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
        return response

    @staticmethod
    def _generate_listening(generator):
        return generator.generate(
            specification={
                "domain": "listening",
                "title": "Listening for key details",
                "description": "Follow clear speech.",
                "cefr_level": "B1",
                "skill_ids": ["listening.b1.core"],
            },
            lesson_key="w01_l01_listening",
            chunks=[
                RetrievedChunk(
                    id="core_b1_listening_001",
                    source_id="project_core_curriculum_v1",
                    content="Teach signposts and distinguish main ideas from details.",
                    metadata={"skill_ids": ["listening.b1.core"]},
                    score=1.0,
                )
            ],
            support_language="Arabic",
        )

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

    def test_local_generator_uses_schema_and_unloads_model(self):
        groq_style = self._valid_listening_response()
        local_response = Mock(message=groq_style.choices[0].message)
        client = Mock()
        client.chat.return_value = local_response
        generator = LessonGenerator(
            ollama_client=client,
            provider="ollama",
        )

        generated, refs = self._generate_listening(generator)

        self.assertEqual(generated["title"], "Listening for key details")
        self.assertEqual(refs, ["project_core_curriculum_v1"])
        request = client.chat.call_args.kwargs
        self.assertEqual(request["model"], "llama3.1:latest")
        self.assertEqual(request["keep_alive"], 0)
        self.assertFalse(request["stream"])
        self.assertEqual(request["options"]["num_ctx"], 12288)
        self.assertEqual(
            request["format"]["properties"]["activities"]["type"],
            "object",
        )

    def test_progress_queues_generation_when_a_pending_lesson_is_eligible(self):
        session = Mock()
        job = GenerationJob(revision_id=uuid.uuid4(), status="idle")
        session.scalar.return_value = job
        with patch(
            "plp.service._eligible_pending_lesson_ids",
            return_value=[uuid.uuid4()],
        ):
            PlpService._queue_next_generation(session, job.revision_id)
        self.assertEqual(job.status, "queued")

    def test_curated_worker_prepares_all_currently_eligible_skill_days(self):
        job_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        job = Mock(id=job_id, revision_id=revision_id)
        lessons = [
            Mock(id=uuid.uuid4(), content_status="pending", required_lesson_keys=[]),
            Mock(id=uuid.uuid4(), content_status="pending", required_lesson_keys=[]),
        ]
        revision = Mock(id=revision_id, plan_id=plan_id)
        plan = Mock(id=plan_id)
        first_session = Mock()
        first_session.get.return_value = job
        first_session.scalars.return_value.all.return_value = lessons
        final_session = Mock()
        final_session.get.side_effect = [job, revision, plan]
        final_session.scalar.return_value = 2

        @contextmanager
        def first_context():
            yield first_session

        @contextmanager
        def final_context():
            yield final_session

        service = PlpService()
        service.generator.provider = "curated"
        service._generate_lesson = Mock()
        try:
            with patch(
                "plp.service.session_scope",
                side_effect=[first_context(), final_context()],
            ), patch(
                "plp.service._eligible_pending_lesson_ids",
                return_value=[item.id for item in lessons],
            ):
                service._process_job(job_id)
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(
            service._generate_lesson.call_args_list,
            [
                call(job_id, lessons[0].id),
                call(job_id, lessons[1].id),
            ],
        )
        self.assertEqual(job.status, "idle")

    def test_only_stale_generating_jobs_are_reclaimed(self):
        job = GenerationJob(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            status="generating_next",
            attempts=2,
            updated_at=utc_now() - timedelta(minutes=3),
        )
        session = Mock()
        no_waiting = MagicMock()
        no_waiting.all.return_value = []
        stale = MagicMock()
        stale.all.return_value = [job]
        session.scalars.side_effect = [stale, no_waiting]
        session.scalar.side_effect = [job, 1]

        @contextmanager
        def context():
            yield session

        service = PlpService()
        try:
            with patch("plp.service.session_scope", return_value=context()):
                claimed = service._claim_next_job()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(claimed, job.id)
        self.assertEqual(job.status, "generating_next")
        self.assertEqual(job.attempts, 3)

    def test_due_rate_limit_wait_is_claimed_automatically(self):
        job = GenerationJob(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            status="waiting_for_model",
            attempts=0,
            error=(
                "__plp_failure_v1__:"
                '{"message":"waiting","failure_kind":"rate_limited",'
                '"retry_after_seconds":30}'
            ),
            updated_at=utc_now() - timedelta(seconds=31),
        )
        session = Mock()
        no_stale = MagicMock()
        no_stale.all.return_value = []
        waiting = MagicMock()
        waiting.all.return_value = [job]
        session.scalars.side_effect = [no_stale, waiting]
        session.scalar.side_effect = [job, 0]

        @contextmanager
        def context():
            yield session

        service = PlpService()
        try:
            with patch("plp.service.session_scope", return_value=context()):
                claimed = service._claim_next_job()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(claimed, job.id)
        self.assertEqual(job.status, "generating_initial")
        self.assertEqual(job.attempts, 1)
        self.assertIsNone(job.error)


class RetrievalIntegrationTests(unittest.TestCase):
    def test_reviewed_b1_pronunciation_query(self):
        try:
            retriever = CurriculumRetriever()
            try:
                with session_scope() as session:
                    results = retriever.retrieve(
                        session,
                        query="Arabic learner B1 TH sounds and sentence stress",
                        cefr_level="B1",
                        skill_ids=["pronunciation.b1.core"],
                    )
            finally:
                retriever.close()
        except Exception as exc:
            self.skipTest(f"local PostgreSQL/EmbeddingGemma unavailable: {exc}")
        self.assertEqual(results[0].id, "core_b1_pronunciation_001")
        self.assertTrue(all(item.metadata["cefr"] == ["B1"] for item in results))

    @classmethod
    def tearDownClass(cls):
        get_engine().dispose()


if __name__ == "__main__":
    unittest.main()
