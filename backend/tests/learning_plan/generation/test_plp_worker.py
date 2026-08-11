from speakflow.features.learning_plan.engine.service_progress import (
    _eligible_pending_lesson_ids,
)
from tests.learning_plan.support.plp_generator_test_support import PlpGeneratorTestBase
from tests.learning_plan.support.plp_test_support import (
    GenerationJob,
    LearningPlanEngine,
    MagicMock,
    Mock,
    SimpleNamespace,
    call,
    contextmanager,
    patch,
    timedelta,
    utc_now,
    uuid,
)


class GeneratorWorkerTests(PlpGeneratorTestBase):
    def test_progress_queues_generation_when_a_pending_lesson_is_eligible(self):
        session = Mock()
        job = GenerationJob(revision_id=uuid.uuid4(), status="idle")
        session.scalar.return_value = job
        with patch(
            "speakflow.features.learning_plan.engine.service_worker._eligible_pending_lesson_ids",
            return_value=[uuid.uuid4()],
        ):
            LearningPlanEngine._queue_next_generation(session, job.revision_id)
        self.assertEqual(job.status, "queued")

    def test_worker_eligibility_verifies_pronunciation_for_plan_owner(self):
        owner_id = uuid.uuid4()
        completed_lesson = SimpleNamespace(
            id=uuid.uuid4(),
            lesson_key="w01_l01",
            content_status="ready",
            required_lesson_keys=[],
            content={
                "content": {
                    "activities": [
                        {
                            "id": "sound_check",
                            "type": "pronunciation_drill",
                            "required": True,
                            "data": {"practice_items": ["paper"]},
                        }
                    ]
                }
            },
        )
        pending_lesson = SimpleNamespace(
            id=uuid.uuid4(),
            lesson_key="w01_l02",
            content_status="pending",
            required_lesson_keys=["w01_l01"],
            content=None,
        )
        progress = SimpleNamespace(
            lesson_id=completed_lesson.id,
            status="completed",
            completed_activity_ids=["sound_check"],
        )

        def scalar_rows(values):
            result = Mock()
            result.all.return_value = values
            return result

        session = Mock()
        session.scalar.return_value = owner_id
        session.scalars.side_effect = [
            scalar_rows([completed_lesson, pending_lesson]),
            scalar_rows([progress]),
            scalar_rows(
                [
                    SimpleNamespace(
                        activity_id="sound_check",
                        correct=True,
                        response={"pronunciation": {"target": "paper"}},
                    )
                ]
            ),
        ]

        eligible = _eligible_pending_lesson_ids(session, uuid.uuid4())

        self.assertEqual(eligible, [pending_lesson.id])
        attempt_query = session.scalars.call_args_list[2].args[0]
        self.assertIn(owner_id, attempt_query.compile().params.values())

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

        service = LearningPlanEngine()
        service.generator.provider = "curated"
        service._generate_lesson = Mock()
        try:
            with (
                patch(
                    "speakflow.features.learning_plan.engine.service_worker.session_scope",
                    side_effect=[first_context(), final_context()],
                ),
                patch(
                    "speakflow.features.learning_plan.engine.service_worker._eligible_pending_lesson_ids",
                    return_value=[item.id for item in lessons],
                ),
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

        service = LearningPlanEngine()
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_worker.session_scope",
                return_value=context(),
            ):
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

        service = LearningPlanEngine()
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_worker.session_scope",
                return_value=context(),
            ):
                claimed = service._claim_next_job()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(claimed, job.id)
        self.assertEqual(job.status, "generating_initial")
        self.assertEqual(job.attempts, 1)
        self.assertIsNone(job.error)

    def test_eligible_idle_job_is_recovered_automatically(self):
        job = GenerationJob(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            status="idle",
            attempts=1,
            updated_at=utc_now(),
        )
        session = Mock()
        no_stale = MagicMock()
        no_stale.all.return_value = []
        no_waiting = MagicMock()
        no_waiting.all.return_value = []
        idle = MagicMock()
        idle.all.return_value = [job]
        session.scalars.side_effect = [no_stale, no_waiting, idle]
        session.scalar.side_effect = [None, 5]

        @contextmanager
        def context():
            yield session

        service = LearningPlanEngine()
        try:
            with (
                patch(
                    "speakflow.features.learning_plan.engine.service_worker.session_scope",
                    return_value=context(),
                ),
                patch(
                    "speakflow.features.learning_plan.engine.service_worker._eligible_pending_lesson_ids",
                    return_value=[uuid.uuid4()],
                ),
            ):
                claimed = service._claim_next_job()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(claimed, job.id)
        self.assertEqual(job.status, "generating_next")
        self.assertEqual(job.attempts, 2)
        self.assertIsNone(job.error)
