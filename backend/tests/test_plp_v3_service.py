import threading
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from plp.models import (
    GenerationJob,
    LearningPlan,
    PlanLesson,
    PlanRevision,
)
from plp.generator import GenerationError
from plp.retrieval import CurriculumRetriever, RetrievalError
from plp.schemas import GenerationView
from plp.service import (
    PlpConflictError,
    PlpService,
    _decode_job_failure,
    _encode_job_failure,
)


def _context_for(session):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    return context


def _scalar_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


class ExactRetrievalTests(unittest.TestCase):
    def test_exact_retrieval_skips_embeddings_and_returns_stable_hashes(self):
        rows = [
            SimpleNamespace(
                id="chunk-z",
                source_id="source-z",
                content="Later lexical ID",
                metadata_json={"cefr": ["B1"], "skill_ids": ["skill.two"]},
                content_hash="z" * 64,
            ),
            SimpleNamespace(
                id="chunk-a",
                source_id="source-a",
                content="Earlier lexical ID",
                metadata_json={"cefr": ["B1"], "skill_ids": ["skill.one"]},
                content_hash="a" * 64,
            ),
        ]
        session = Mock()
        session.execute.return_value = _scalar_result(rows)
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(side_effect=AssertionError("embed must not run"))

        chunks = retriever.retrieve_exact(
            session,
            cefr_level="B1",
            skill_ids=["skill.two", "skill.one"],
        )

        retriever.embed.assert_not_called()
        self.assertEqual([item.id for item in chunks], ["chunk-a", "chunk-z"])
        self.assertEqual(
            [item.content_hash for item in chunks],
            ["a" * 64, "z" * 64],
        )

    def test_exact_retrieval_reports_each_missing_skill(self):
        row = SimpleNamespace(
            id="chunk-a",
            source_id="source-a",
            content="Only one skill is present",
            metadata_json={"cefr": ["B1"], "skill_ids": ["skill.one"]},
            content_hash="a" * 64,
        )
        session = Mock()
        session.execute.return_value = _scalar_result([row])
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(side_effect=AssertionError("embed must not run"))

        with self.assertRaisesRegex(RetrievalError, "skill.missing"):
            retriever.retrieve_exact(
                session,
                cefr_level="B1",
                skill_ids=["skill.one", "skill.missing"],
            )

        retriever.embed.assert_not_called()


class WeeklyWorkerTests(unittest.TestCase):
    def test_rate_limit_keeps_week_pending_for_automatic_resume(self):
        job_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        lesson_ids = [uuid.uuid4() for _ in range(5)]
        job = SimpleNamespace(
            id=job_id,
            revision_id=revision_id,
            status="generating_week_one",
            error=None,
            updated_at=None,
        )
        cohort = [
            SimpleNamespace(
                id=lesson_id,
                revision_id=revision_id,
                week_sequence=1,
                specification={"architecture": "mission_v3"},
                content_status="pending",
                generation_error=None,
                generation_attempts=2,
            )
            for lesson_id in lesson_ids
        ]
        session = Mock()

        def get(model, identifier):
            if model is GenerationJob:
                return job
            if model is PlanLesson and identifier == lesson_ids[0]:
                return cohort[0]
            return None

        session.get.side_effect = get
        cohort_result = MagicMock()
        cohort_result.all.return_value = cohort
        session.scalars.return_value = cohort_result
        failure = GenerationError(
            "Groq is temporarily rate-limited.",
            failure_kind="rate_limited",
            retry_after_seconds=42,
        )

        with patch(
            "plp.service.session_scope",
            return_value=_context_for(session),
        ):
            PlpService._defer_job_for_rate_limit(
                job_id,
                lesson_ids[0],
                failure,
            )

        self.assertEqual(job.status, "waiting_for_model")
        decoded = _decode_job_failure(job.error)
        self.assertEqual(decoded["failure_kind"], "rate_limited")
        self.assertEqual(decoded["retry_after_seconds"], 42)
        self.assertTrue(all(item.content_status == "pending" for item in cohort))
        self.assertTrue(all(item.generation_attempts == 1 for item in cohort))
        self.assertTrue(all(item.generation_error is None for item in cohort))

    def test_rate_limited_job_cannot_retry_before_provider_window(self):
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="failed",
            error=_encode_job_failure(
                "Groq is temporarily rate-limited.",
                failure_kind="rate_limited",
                retry_after_seconds=60,
            ),
            updated_at=datetime.now(timezone.utc),
        )
        session = Mock()
        session.scalar.return_value = job
        service = object.__new__(PlpService)

        with patch("plp.service.session_scope", return_value=_context_for(session)):
            with self.assertRaisesRegex(PlpConflictError, r"Retry in .* seconds"):
                service.retry_generation(job_id)

        session.scalars.assert_not_called()

    def test_explicit_retry_preserves_attempt_count_for_a_fresh_writer_variant(self):
        job_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            revision_id=revision_id,
            status="failed",
            error="invalid weekly surface",
        )
        failed = [
            SimpleNamespace(
                content_status="failed",
                generation_attempts=1,
                generation_error="invalid weekly surface",
            )
            for _ in range(5)
        ]
        session = Mock()
        session.scalar.return_value = job
        result = MagicMock()
        result.all.return_value = failed
        session.scalars.return_value = result
        expected = GenerationView(
            job_id=job_id,
            status="queued",
            ready_weeks=0,
            completed_lessons=0,
            total_lessons=20,
            failed_lesson_ids=[],
        )
        service = object.__new__(PlpService)
        service._generation_view = Mock(return_value=expected)

        with patch("plp.service.session_scope", return_value=_context_for(session)):
            actual = service.retry_generation(job_id)

        self.assertEqual(actual, expected)
        self.assertEqual(job.status, "queued")
        self.assertTrue(all(item.content_status == "pending" for item in failed))
        self.assertTrue(all(item.generation_attempts == 1 for item in failed))

    def test_v3_job_dispatches_one_week_generation_not_per_lesson(self):
        job_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        eligible_ids = [uuid.uuid4(), uuid.uuid4()]
        job = SimpleNamespace(
            id=job_id,
            revision_id=revision_id,
            status="queued",
            updated_at=None,
        )
        first_lesson = SimpleNamespace(
            id=eligible_ids[0],
            week_sequence=1,
            specification={"architecture": "mission_v3"},
        )
        revision = SimpleNamespace(id=revision_id, plan_id=plan_id, status="draft")
        plan = SimpleNamespace(id=plan_id, active_revision_id=None)
        session = Mock()

        def get(model, identifier):
            if model is GenerationJob:
                return job
            if model is PlanLesson:
                return first_lesson
            if model is PlanRevision:
                return revision
            if model is LearningPlan:
                return plan
            return None

        session.get.side_effect = get
        session.scalar.return_value = 15
        service = object.__new__(PlpService)
        service.generator = SimpleNamespace(provider="groq")
        service._stop_event = threading.Event()
        service._generate_week = Mock()
        service._generate_lesson = Mock()

        with (
            patch("plp.service.session_scope", return_value=_context_for(session)),
            patch(
                "plp.service._eligible_pending_lesson_ids",
                return_value=eligible_ids,
            ),
        ):
            service._process_job(job_id)

        service._generate_week.assert_called_once_with(job_id, 1)
        service._generate_lesson.assert_not_called()
        self.assertEqual(job.status, "idle")
        self.assertEqual(revision.status, "active_jit")
        self.assertEqual(plan.active_revision_id, revision_id)

    def test_v3_failure_marks_the_entire_pending_week_failed(self):
        job_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        lesson_ids = [uuid.uuid4() for _ in range(5)]
        job = SimpleNamespace(
            id=job_id,
            revision_id=revision_id,
            status="generating_week_one",
            error=None,
            updated_at=None,
        )
        cohort = [
            SimpleNamespace(
                id=lesson_id,
                revision_id=revision_id,
                week_sequence=1,
                specification={"architecture": "mission_v3"},
                content_status="pending",
                generation_error=None,
            )
            for lesson_id in lesson_ids
        ]
        session = Mock()

        def get(model, identifier):
            if model is GenerationJob:
                return job
            if model is PlanLesson and identifier == lesson_ids[0]:
                return cohort[0]
            return None

        session.get.side_effect = get
        cohort_result = MagicMock()
        cohort_result.all.return_value = cohort
        session.scalars.return_value = cohort_result

        with patch(
            "plp.service.session_scope",
            return_value=_context_for(session),
        ):
            PlpService._mark_job_failed(job_id, lesson_ids[0], "writer failed")

        self.assertTrue(all(item.content_status == "failed" for item in cohort))
        self.assertTrue(
            all(item.generation_error == "writer failed" for item in cohort)
        )
        self.assertEqual(job.status, "failed")
        self.assertEqual(_decode_job_failure(job.error)["message"], "writer failed")
        self.assertEqual(_decode_job_failure(job.error)["failure_kind"], "internal")


class DocumentGroundingTests(unittest.TestCase):
    def test_document_prefers_explicit_provenance_and_exposes_v3_metadata(self):
        plan_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        lesson_rows = []
        weeks = []
        for week_number in range(1, 5):
            lesson_key = f"w{week_number:02d}_l01_input_noticing"
            specification = {
                "title": f"Week {week_number} input",
                "description": "Notice useful language in context.",
                "cefr_level": "B1",
                "completion_policy": {"mode": "required_activities"},
                "objectives": ["Notice the key language"],
                "personalization_reason": "Matches the selected mission.",
                "lesson_role": "input_noticing",
                "can_do": "Can identify the key information in a short exchange.",
            }
            ready = week_number == 1
            generated = None
            source_refs = []
            if ready:
                source_refs = ["source-reviewed"]
                generated = {
                    # Explicit provenance must win over misleading legacy text.
                    "generator_version": "old-curated-looking-prefix",
                    "provenance": {
                        "origin": "retrieval_generated",
                        "review_status": "generated_validated",
                    },
                    "title": "Personalized input",
                    "description": "A grounded scenario realization.",
                    "content_instance_id": "instance-week-1-input",
                    "content": {
                        "intro": "Read the grounded scenario.",
                        "activities": [
                            {
                                "id": "week1_activity_1",
                                "type": "concept",
                                "required": True,
                                "source_refs": source_refs,
                                "skill_ids": ["reading.b1.core"],
                                "data": {},
                            },
                            {
                                "id": "week1_activity_2",
                                "type": "concept",
                                "required": True,
                                "source_refs": source_refs,
                                "skill_ids": ["reading.b1.core"],
                                "data": {},
                            },
                        ],
                    },
                }
            lesson_rows.append(
                SimpleNamespace(
                    id=uuid.uuid4(),
                    lesson_key=lesson_key,
                    lesson_sequence=1,
                    week_sequence=week_number,
                    lesson_type="reading",
                    estimated_minutes=20,
                    xp=20,
                    skill_ids=["reading.b1.core"],
                    required_lesson_keys=[],
                    specification=specification,
                    content_status="ready" if ready else "pending",
                    content=generated,
                    source_refs=source_refs,
                )
            )
            weeks.append(
                {
                    "id": f"week-{week_number}",
                    "sequence": week_number,
                    "title": f"Week {week_number}",
                    "description": "Mission week.",
                    "objectives": ["Complete the mission"],
                    "mission": {"id": f"mission-{week_number}"},
                    "units": [
                        {
                            "id": f"unit-{week_number}",
                            "sequence": 1,
                            "title": "Mission",
                            "description": "Prepare and apply.",
                            "objectives": ["Apply the weekly language"],
                            "lessons": [
                                {
                                    "lesson_key": lesson_key,
                                    "specification": specification,
                                }
                            ],
                        }
                    ],
                }
            )

        outline = {
            "architecture": "mission_v3",
            "title": "Personal learning path",
            "description": "Four grounded weekly missions.",
            "level": {"current": "B1", "target": "B2"},
            "schedule": {
                "duration_weeks": 4,
                "days_per_week": 5,
                "minutes_per_day": 20,
            },
            "focus_areas": ["reading"],
            "weeks": weeks,
        }
        snapshot = {
            "native_language": "Arabic",
            "support_language": "Arabic",
            "learning_goals": ["Speak confidently"],
            "interests": ["Technology"],
            "preferred_contexts": [],
            "accent_preference": "no_preference",
            "pronunciation_priorities": [],
        }
        plan = SimpleNamespace(id=plan_id)
        revision = SimpleNamespace(
            id=revision_id,
            revision=1,
            outline=outline,
            learner_snapshot=snapshot,
        )
        job = SimpleNamespace(id=uuid.uuid4())
        source = SimpleNamespace(
            id="source-reviewed",
            title="Reviewed curriculum",
            locator="project://curriculum",
            license="project-authored",
            version="1",
        )
        session = Mock()
        session.scalars.side_effect = [
            _scalar_result(lesson_rows).scalars.return_value,
            _scalar_result([]).scalars.return_value,
            _scalar_result([]).scalars.return_value,
            _scalar_result([source]).scalars.return_value,
            _scalar_result([]).scalars.return_value,
        ]
        service = object.__new__(PlpService)
        service._generation_view = Mock(
            return_value=GenerationView(
                job_id=job.id,
                status="idle",
                ready_weeks=0,
                completed_lessons=1,
                total_lessons=4,
                failed_lesson_ids=[],
            )
        )

        document = service._build_document(session, plan, revision, job)
        lesson = document.plan.weeks[0].units[0].lessons[0]

        self.assertEqual(lesson.grounding.origin, "retrieval_generated")
        self.assertEqual(lesson.grounding.review_status, "generated_validated")
        self.assertEqual(lesson.grounding.source_refs, ["source-reviewed"])
        self.assertEqual(lesson.lesson_role, "input_noticing")
        self.assertEqual(
            lesson.can_do_statement,
            "Can identify the key information in a short exchange.",
        )
        self.assertEqual(lesson.content_instance_id, "instance-week-1-input")


if __name__ == "__main__":
    unittest.main()
