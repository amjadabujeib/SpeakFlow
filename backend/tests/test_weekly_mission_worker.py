from tests.plp_service_test_support import *


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
                specification={"architecture": "weekly_mission"},
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
            "plp.service_worker.session_scope",
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

        with patch(
            "plp.service_generation.session_scope",
            return_value=_context_for(session),
        ):
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

        with patch(
            "plp.service_generation.session_scope",
            return_value=_context_for(session),
        ):
            actual = service.retry_generation(job_id)

        self.assertEqual(actual, expected)
        self.assertEqual(job.status, "queued")
        self.assertTrue(all(item.content_status == "pending" for item in failed))
        self.assertTrue(all(item.generation_attempts == 1 for item in failed))

    def test_weekly_job_dispatches_one_week_generation_not_per_lesson(self):
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
            specification={"architecture": "weekly_mission"},
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
            patch(
                "plp.service_worker.session_scope",
                return_value=_context_for(session),
            ),
            patch(
                "plp.service_worker._eligible_pending_lesson_ids",
                return_value=eligible_ids,
            ),
        ):
            service._process_job(job_id)

        service._generate_week.assert_called_once_with(job_id, 1)
        service._generate_lesson.assert_not_called()
        self.assertEqual(job.status, "idle")
        self.assertEqual(revision.status, "active_jit")
        self.assertEqual(plan.active_revision_id, revision_id)

    def test_weekly_failure_marks_the_entire_pending_week_failed(self):
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
                specification={"architecture": "weekly_mission"},
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
            "plp.service_worker.session_scope",
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
