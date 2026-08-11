from speakflow.features.learning_plan.engine.service_generation import (
    _existing_generation_disposition,
)
from speakflow.features.learning_plan.engine.service_progress import (
    _eligible_pending_lesson_ids,
    _progress_view,
    _visible_lesson_status,
)
from tests.learning_plan.support.plp_test_support import (
    ActivityAttemptInput,
    LearningPlanEngine,
    MagicMock,
    Mock,
    SimpleNamespace,
    audit_generation,
    patch,
    unittest,
    utc_now,
    uuid,
)


class PlpGenerationContractTests(unittest.TestCase):
    def test_idle_jit_job_is_reused_for_onboarding_but_replaced_explicitly(self):
        self.assertEqual(
            _existing_generation_disposition("idle", "onboarding"),
            "reuse",
        )
        self.assertEqual(
            _existing_generation_disposition("idle", "manual_regeneration"),
            "supersede",
        )
        self.assertEqual(
            _existing_generation_disposition(
                "generating_week_one",
                "manual_regeneration",
            ),
            "reuse",
        )
        self.assertEqual(
            _existing_generation_disposition(
                "idle",
                f"adaptation:{uuid.uuid4()}",
            ),
            "supersede",
        )
        self.assertEqual(
            _existing_generation_disposition(
                "generating_next",
                f"adaptation:{uuid.uuid4()}",
            ),
            "block",
        )

    def test_legacy_unverified_completion_is_presented_as_in_progress(self):
        completed_at = utc_now()
        progress = SimpleNamespace(
            status="completed",
            completed_activity_ids=["concept", "pronunciation"],
            best_score=100,
            attempts=2,
            completed_at=completed_at,
        )
        visible_ids = ["concept"]
        status = _visible_lesson_status(
            progress,
            ["concept", "pronunciation"],
            visible_ids,
        )
        view = _progress_view(
            progress,
            2,
            completed_activity_ids=visible_ids,
            best_score=50,
            status=status,
        )

        self.assertEqual(view.status, "in_progress")
        self.assertEqual(view.progress_fraction, 0.5)
        self.assertEqual(view.best_score, 50)
        self.assertIsNone(view.completed_at)

    def test_legacy_unverified_completion_does_not_unlock_next_lesson(self):
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
            scalar_rows([]),
        ]

        eligible = _eligible_pending_lesson_ids(session, uuid.uuid4())

        self.assertEqual(eligible, [])

    def test_idle_jit_generation_is_reused_instead_of_creating_a_revision(self):
        revision_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        job = Mock(id=uuid.uuid4(), revision_id=revision_id, status="idle")
        revision = Mock(id=revision_id, plan_id=plan_id)
        session = Mock()
        session.scalar.side_effect = [Mock(cefr_level="B1"), job]
        session.get.return_value = revision
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = LearningPlanEngine()

        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_generation.session_scope",
                return_value=context,
            ):
                result = service.create_generation()
        finally:
            service.retriever.close()
            service.generator.close()

        existing_query = session.scalar.call_args_list[1].args[0]
        status_values = [
            item
            for value in existing_query.compile().params.values()
            for item in (value if isinstance(value, list) else [])
        ]
        self.assertIn("idle", status_values)
        self.assertEqual(result.job_id, job.id)
        self.assertEqual(result.plan_id, plan_id)
        session.add.assert_not_called()

    def test_manual_generation_retry_locks_the_job_before_resetting_lessons(self):
        job = Mock(
            id=uuid.uuid4(),
            revision_id=uuid.uuid4(),
            status="failed",
            error=None,
        )
        failed_lesson = Mock(content_status="failed", generation_error="failed")
        session = Mock()
        session.scalar.return_value = job
        session.scalars.return_value.all.return_value = [failed_lesson]
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = LearningPlanEngine()
        service._generation_view = Mock(return_value="retried")

        try:
            with (
                patch(
                    "speakflow.features.learning_plan.engine.service_generation.session_scope",
                    return_value=context,
                ),
                patch(
                    "speakflow.features.learning_plan.engine.service_generation.reviewed_source_is_current",
                    return_value=True,
                ),
            ):
                result = service.retry_generation(job.id)
        finally:
            service.retriever.close()
            service.generator.close()

        retry_query = session.scalar.call_args.args[0]
        self.assertIsNotNone(retry_query._for_update_arg)
        self.assertEqual(result, "retried")
        self.assertEqual(job.status, "queued")
        self.assertEqual(failed_lesson.content_status, "pending")
        self.assertIsNone(failed_lesson.generation_error)

    def test_pending_adaptation_proposal_is_reused(self):
        plan = Mock(id=uuid.uuid4(), active_revision_id=uuid.uuid4())
        proposal = Mock(
            id=uuid.uuid4(),
            status="pending",
            summary="Reinforce speaking.",
            changes=[],
            evidence=[],
            created_at=utc_now(),
        )
        session = Mock()
        session.scalar.return_value = proposal
        context = MagicMock()
        context.__enter__.return_value = session
        context.__exit__.return_value = False
        service = LearningPlanEngine()
        service._active_plan = Mock(return_value=plan)

        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_adaptation.session_scope",
                return_value=context,
            ):
                result = service.create_adaptation_proposal()
        finally:
            service.retriever.close()
            service.generator.close()

        lock_query = session.execute.call_args.args[0]
        self.assertIsNotNone(lock_query._for_update_arg)
        self.assertEqual(result.id, proposal.id)
        session.add.assert_not_called()

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
                "title": "Audit lesson",
                "content": {"activities": []},
            },
            [],
        )

        with (
            patch(
                "speakflow.features.learning_plan.engine.audit_generation.session_scope",
                return_value=context,
            ),
            patch(
                "speakflow.features.learning_plan.engine.audit_generation.CurriculumRetriever",
                return_value=retriever,
            ),
            patch(
                "speakflow.features.learning_plan.engine.audit_generation.LessonGenerator",
                return_value=generator,
            ),
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
        service = LearningPlanEngine()
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
        service = LearningPlanEngine()
        service._find_active_lesson_by_activity = Mock(return_value=lesson)
        service._update_lesson_completion = Mock(return_value=False)
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_attempts.session_scope",
                return_value=context,
            ):
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
                service = LearningPlanEngine()
                service._find_active_lesson_by_activity = Mock(return_value=lesson)

                def complete_lesson(*_args, **_kwargs):
                    progress.status = "completed"
                    return True

                service._update_lesson_completion = Mock(side_effect=complete_lesson)
                service._queue_next_generation = Mock()
                try:
                    with patch(
                        "speakflow.features.learning_plan.engine.service_attempts.session_scope",
                        return_value=context,
                    ):
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
        service = LearningPlanEngine()
        try:
            with patch(
                "speakflow.features.learning_plan.engine.service_base.session_scope",
                return_value=context,
            ):
                result = service.reset_local_learner()
        finally:
            service.retriever.close()
            service.generator.close()

        self.assertEqual(result, {"status": "reset"})
        self.assertEqual(session.execute.call_count, 8)
        session.delete.assert_not_called()
