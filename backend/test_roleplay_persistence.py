import unittest

from sqlalchemy import func, select

from plp.database import session_scope
from plp.models import RoleplayScenario, RoleplaySession, RoleplayTurn
from plp.schemas import (
    RoleplayScenarioCreate,
    RoleplaySessionStart,
    RoleplayTurnInput,
)
from plp.service import plp_service
from roleplay_engine import aggregate_session


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
                    RoleplayScenario.title == "Integrity custom scenario"
                )
            ).all():
                session.delete(scenario)

    def test_session_turn_and_evaluation_are_saved_atomically(self):
        started = plp_service.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id="airport_check_in",
            )
        )
        self.assertEqual(started.status, "active")
        turn = RoleplayTurnInput(
            turn_id="turn-integrity-0001",
            input_mode="text",
            user_text="I am flying to Paris today.",
            assistant_text="May I see your passport?",
            grammar_error_units=0,
            word_count=6,
            objective_evidence=[
                {
                    "objective_id": "destination",
                    "turn_id": "turn-integrity-0001",
                    "evidence": "Paris",
                }
            ],
        )

        first = plp_service.record_roleplay_turn(
            self.client_session_id,
            turn,
            objective_updates=turn.objective_evidence,
        )
        duplicate = plp_service.record_roleplay_turn(
            self.client_session_id,
            turn,
            objective_updates=turn.objective_evidence,
        )

        self.assertEqual(first["turn"]["turn_id"], duplicate["turn"]["turn_id"])
        self.assertEqual(first["turn"]["sequence"], duplicate["turn"]["sequence"])
        context = plp_service.roleplay_context(self.client_session_id)
        self.assertEqual(len(context["turns"]), 1)
        self.assertEqual(context["turns"][0]["sequence"], 1)
        evaluation = aggregate_session(
            scenario=context["scenario"],
            objective_state=context["objective_state"],
            turns=context["turns"],
        )
        completed = plp_service.complete_roleplay_session(
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
        self.assertEqual(
            completed.evaluation["evaluation_version"],
            "roleplay-rubric-v3-2026-07-26",
        )
        transcript = plp_service.get_roleplay_transcript(
            self.client_session_id
        )
        self.assertTrue(transcript.read_only)
        self.assertEqual(transcript.scenario.opening, started.scenario.opening)
        self.assertEqual(len(transcript.turns), 1)
        self.assertEqual(transcript.turns[0].sequence, 1)
        self.assertEqual(
            transcript.turns[0].user_text,
            "I am flying to Paris today.",
        )
        self.assertEqual(
            transcript.turns[0].assistant_text,
            "May I see your passport?",
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
        started = plp_service.start_roleplay_session(
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

        abandoned = plp_service.complete_roleplay_session(
            self.client_session_id,
            ended_reason="back_navigation",
            evaluation=evaluation,
            corrections=[],
        )
        repeated = plp_service.complete_roleplay_session(
            self.client_session_id,
            ended_reason="learner_ended",
            evaluation=evaluation,
            corrections=[],
        )

        self.assertEqual(abandoned.status, "abandoned")
        self.assertEqual(repeated.status, "abandoned")
        self.assertEqual(repeated.ended_reason, "back_navigation")

    def test_custom_scenario_keeps_edited_cefr_rubric(self):
        created = plp_service.create_roleplay_scenario(
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
        started = plp_service.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id=created.id,
            )
        )
        self.assertEqual(
            started.scenario.evaluation_rubric[1].id, "next_step"
        )


if __name__ == "__main__":
    unittest.main()
