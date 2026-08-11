import asyncio
import unittest
from datetime import timedelta

from sqlalchemy import func, select

from speakflow.features.learning_plan.engine.database import session_scope
from speakflow.features.learning_plan.engine.schemas import (
    RoleplayFinalizeInput,
    RoleplayScenarioCreate,
    RoleplayScenarioUpdate,
    RoleplaySessionStart,
    RoleplayTurnInput,
)
from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    learning_plan_engine,
)
from speakflow.features.roleplay.domain.engine import aggregate_session
from speakflow.features.roleplay.infrastructure.models import (
    RoleplayScenario,
    RoleplaySession,
    RoleplayTurn,
)
from speakflow.features.roleplay.presentation.finalize import finalize_roleplay_session
from speakflow.shared.orm import utc_now


class RoleplayPersistenceTests(unittest.TestCase):
    client_session_id = "integrity-roleplay-20260726"

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        with session_scope() as session:
            row = session.scalar(
                select(RoleplaySession).where(
                    RoleplaySession.client_session_id == self.client_session_id
                )
            )
            if row is not None:
                session.delete(row)
            for scenario in session.scalars(
                select(RoleplayScenario).where(
                    RoleplayScenario.title.in_(
                        (
                            "Integrity custom scenario",
                            "Edited integrity custom scenario",
                        )
                    )
                )
            ).all():
                session.delete(scenario)

    def test_session_turn_and_evaluation_are_saved_atomically(self):
        started = learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="airport_check_in",
            )
        )
        self.assertEqual(started.status, "active")
        turn = RoleplayTurnInput(
            turn_id="turn-integrity-0001",
            input_mode="audio",
            user_text="I flying to Paris today.",
            assistant_text="May I see your passport?",
            grammar_corrected_text="I am flying to Paris today.",
            grammar_feedback=(
                'Add “am” after “I” to form the present continuous. '
                "Corrected: I am flying to Paris today."
            ),
            grammar_error_units=1,
            word_count=5,
            word_feedback=[
                {"word": "I", "score": 0.96, "start": 0.0, "end": 0.1},
                {"word": "flying", "score": 0.48, "start": 0.2, "end": 0.6},
                {"word": "to", "score": 0.91, "start": 0.7, "end": 0.8},
                {"word": "Paris", "score": 0.86, "start": 0.9, "end": 1.2},
                {"word": "today", "score": 0.73, "start": 1.3, "end": 1.6},
            ],
            objective_evidence=[
                {
                    "objective_id": "destination",
                    "turn_id": "turn-integrity-0001",
                    "evidence": "Paris",
                }
            ],
        )

        first = learning_plan_engine.record_roleplay_turn(
            self.client_session_id,
            turn,
            objective_updates=turn.objective_evidence,
        )
        duplicate = learning_plan_engine.record_roleplay_turn(
            self.client_session_id,
            turn,
            objective_updates=turn.objective_evidence,
        )

        self.assertEqual(first["turn"]["turn_id"], duplicate["turn"]["turn_id"])
        self.assertEqual(first["turn"]["sequence"], duplicate["turn"]["sequence"])
        context = learning_plan_engine.roleplay_context(self.client_session_id)
        self.assertEqual(len(context["turns"]), 1)
        self.assertEqual(context["turns"][0]["sequence"], 1)
        evaluation = aggregate_session(
            scenario=context["scenario"],
            objective_state=context["objective_state"],
            turns=context["turns"],
        )
        completed = learning_plan_engine.complete_roleplay_session(
            self.client_session_id,
            ended_reason="learner_ended",
            evaluation=evaluation,
            corrections=[],
        )

        self.assertEqual(completed.status, "complete")
        self.assertEqual(completed.message_count, 1)
        self.assertEqual(
            completed.objective_state["destination"]["evidence"], "Paris"
        )
        self.assertIn("scores", completed.evaluation)
        transcript = learning_plan_engine.get_roleplay_transcript(
            self.client_session_id
        )
        self.assertTrue(transcript.read_only)
        self.assertEqual(transcript.scenario.opening, started.scenario.opening)
        self.assertEqual(len(transcript.turns), 1)
        self.assertEqual(transcript.turns[0].sequence, 1)
        self.assertEqual(
            transcript.turns[0].user_text,
            "I flying to Paris today.",
        )
        self.assertEqual(
            transcript.turns[0].assistant_text,
            "May I see your passport?",
        )
        self.assertEqual(
            transcript.turns[0].grammar_corrected_text,
            "I am flying to Paris today.",
        )
        self.assertIn("present continuous", transcript.turns[0].grammar_feedback)
        self.assertEqual(len(transcript.turns[0].word_confidence), 5)
        self.assertEqual(
            transcript.turns[0].word_confidence[1]["score"],
            0.48,
        )
        with session_scope() as session:
            row = session.scalar(
                select(RoleplaySession).where(
                    RoleplaySession.client_session_id
                    == self.client_session_id
                )
            )
            self.assertIsNotNone(row)
            count = session.scalar(
                select(func.count(RoleplayTurn.id)).where(
                    RoleplayTurn.session_id == row.id
                )
            )
            self.assertEqual(count, 1)

    def test_zero_turn_session_is_abandoned_not_completed(self):
        started = learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="cafe_small_talk",
            )
        )
        evaluation = aggregate_session(
            scenario=started.scenario.model_dump(),
            objective_state=started.objective_state,
            turns=[],
        )

        abandoned = learning_plan_engine.complete_roleplay_session(
            self.client_session_id,
            ended_reason="back_navigation",
            evaluation=evaluation,
            corrections=[],
        )
        repeated = learning_plan_engine.complete_roleplay_session(
            self.client_session_id,
            ended_reason="learner_ended",
            evaluation=evaluation,
            corrections=[],
        )

        self.assertEqual(abandoned.status, "abandoned")
        self.assertEqual(repeated.status, "abandoned")
        self.assertEqual(repeated.ended_reason, "back_navigation")

    def test_client_cannot_claim_objective_completion_without_evidence(self):
        started = learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="cafe_small_talk",
            )
        )
        evaluation = aggregate_session(
            scenario=started.scenario.model_dump(),
            objective_state=started.objective_state,
            turns=[],
        )

        result = learning_plan_engine.complete_roleplay_session(
            self.client_session_id,
            ended_reason="objective_completed",
            evaluation=evaluation,
            corrections=[],
        )

        self.assertEqual(result.ended_reason, "learner_ended")

    def test_session_idempotency_key_cannot_change_scenario(self):
        learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="airport_check_in",
            )
        )

        with self.assertRaisesRegex(
            PlpConflictError,
            "another scenario",
        ):
            learning_plan_engine.start_roleplay_session(
                RoleplaySessionStart(
                    client_session_id=self.client_session_id,
                    scenario_id="hotel_check_in",
                )
            )

    def test_finalization_reclaims_a_stale_finalizing_session(self):
        learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="cafe_small_talk",
            )
        )
        self.assertTrue(
            learning_plan_engine.begin_roleplay_finalization(self.client_session_id)
        )

        result = asyncio.run(
            finalize_roleplay_session(
                self.client_session_id,
                RoleplayFinalizeInput(ended_reason="disconnected"),
            )
        )

        self.assertEqual(result.session.status, "abandoned")
        self.assertEqual(result.session.ended_reason, "disconnected")

    def test_startup_maintenance_expires_orphaned_active_sessions(self):
        learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="cafe_small_talk",
            )
        )
        with session_scope() as session:
            row = session.scalar(
                select(RoleplaySession).where(
                    RoleplaySession.client_session_id == self.client_session_id
                )
            )
            row.created_at = utc_now() - timedelta(hours=7)

        learning_plan_engine._expire_stale_roleplay_sessions()

        with session_scope() as session:
            row = session.scalar(
                select(RoleplaySession).where(
                    RoleplaySession.client_session_id == self.client_session_id
                )
            )
            self.assertEqual(row.status, "abandoned")
            self.assertEqual(row.ended_reason, "timeout")
            self.assertIsNotNone(row.ended_at)

    def test_turn_idempotency_key_cannot_change_content_or_evidence(self):
        learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="airport_check_in",
            )
        )
        turn = RoleplayTurnInput(
            turn_id="turn-integrity-0002",
            input_mode="text",
            user_text="I am flying to Paris.",
            assistant_text="May I see your passport?",
            grammar_evaluated=True,
            word_count=5,
            objective_evidence=[
                {
                    "objective_id": "destination",
                    "turn_id": "turn-integrity-0002",
                    "evidence": "flying to Paris",
                }
            ],
        )
        updates = [item.model_dump(mode="json") for item in turn.objective_evidence]
        learning_plan_engine.record_roleplay_turn(
            self.client_session_id,
            turn,
            objective_updates=updates,
        )

        changed = turn.model_copy(update={"user_text": "I am flying to Rome."})
        with self.assertRaisesRegex(PlpConflictError, "different roleplay content"):
            learning_plan_engine.record_roleplay_turn(
                self.client_session_id,
                changed,
                objective_updates=updates,
            )
        with self.assertRaisesRegex(
            PlpInvalidAttemptError,
            "evidence does not match",
        ):
            learning_plan_engine.record_roleplay_turn(
                self.client_session_id,
                turn,
                objective_updates=[],
            )

    def test_custom_scenario_can_be_edited_and_deleted_without_changing_session_snapshot(self):
        created = learning_plan_engine.create_roleplay_scenario(
            RoleplayScenarioCreate(
                category="Community",
                icon="📷",
                title="Integrity custom scenario",
                description="Ask to join a local photography club and confirm the next meeting.",
                ai_role="photography club coordinator",
                learner_role="prospective club member",
                opening="Welcome. What would you like to know about our club?",
                objectives=[
                    {
                        "id": "interest",
                        "label": "Explain your interest in joining",
                        "weight": 2,
                        "required": True,
                    },
                    {
                        "id": "experience",
                        "label": "Share one relevant experience",
                        "weight": 1,
                        "required": True,
                    },
                    {
                        "id": "meeting",
                        "label": "Confirm the next meeting details",
                        "weight": 2,
                        "required": True,
                    },
                ],
                target_language=[
                    "I am interested in joining",
                    "I have experience with",
                    "When is the next meeting",
                ],
                evaluation_rubric=[
                    {
                        "id": "motivation_clarity",
                        "label": "Motivation clarity",
                        "description": "Explains the reason for joining with relevant detail.",
                        "weight": 2,
                    },
                    {
                        "id": "next_step",
                        "label": "Next-step management",
                        "description": "Asks for and confirms practical meeting information.",
                        "weight": 1,
                    },
                ],
                designed_cefr_level="B1",
            )
        )

        self.assertTrue(created.custom)
        self.assertEqual(created.designed_cefr_level, "B1")
        self.assertEqual(created.evaluation_rubric[0].id, "motivation_clarity")
        started = learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id=created.id,
            )
        )
        self.assertEqual(
            started.scenario.evaluation_rubric[1].id, "next_step"
        )
        updated_payload = created.model_dump(
            exclude={"id", "custom"},
            mode="python",
        )
        updated_payload.update(
            {
                "title": "Edited integrity custom scenario",
                "opening": "Welcome. Tell me what you want from the photography club.",
            }
        )
        updated = learning_plan_engine.update_roleplay_scenario(
            created.id,
            RoleplayScenarioUpdate.model_validate(updated_payload),
        )

        self.assertEqual(updated.title, "Edited integrity custom scenario")
        self.assertEqual(updated.evaluation_rubric[0].weight, 2)
        listed = {item.id: item for item in learning_plan_engine.list_roleplay_scenarios()}
        self.assertEqual(listed[created.id].title, updated.title)
        context = learning_plan_engine.roleplay_context(self.client_session_id)
        self.assertEqual(context["scenario"]["title"], created.title)

        learning_plan_engine.delete_roleplay_scenario(created.id)
        self.assertNotIn(
            created.id,
            {item.id for item in learning_plan_engine.list_roleplay_scenarios()},
        )
        context_after_delete = learning_plan_engine.roleplay_context(self.client_session_id)
        self.assertEqual(context_after_delete["scenario"]["title"], created.title)
        with self.assertRaises(PlpNotFoundError):
            learning_plan_engine.delete_roleplay_scenario(created.id)

    def test_builtin_scenarios_cannot_be_deleted(self):
        with self.assertRaises(PlpNotFoundError):
            learning_plan_engine.delete_roleplay_scenario("airport_check_in")


if __name__ == "__main__":
    unittest.main()
