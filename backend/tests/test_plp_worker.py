from tests.plp_generator_test_support import PlpGeneratorTestBase
from tests.plp_test_support import *


class GeneratorWorkerTests(PlpGeneratorTestBase):
    def test_progress_queues_generation_when_a_pending_lesson_is_eligible(self):
        session = Mock()
        job = GenerationJob(revision_id=uuid.uuid4(), status="idle")
        session.scalar.return_value = job
        with patch(
            "plp.service_worker._eligible_pending_lesson_ids",
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
                "plp.service_worker.session_scope",
                side_effect=[first_context(), final_context()],
            ), patch(
                "plp.service_worker._eligible_pending_lesson_ids",
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
            with patch("plp.service_worker.session_scope", return_value=context()):
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
            with patch("plp.service_worker.session_scope", return_value=context()):
                claimed = service._claim_next_job()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(claimed, job.id)
        self.assertEqual(job.status, "generating_initial")
        self.assertEqual(job.attempts, 1)
        self.assertIsNone(job.error)

