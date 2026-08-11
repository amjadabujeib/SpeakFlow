from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from sqlalchemy import select

from speakflow.features.learning_plan.engine.database import session_scope
from speakflow.features.learning_plan.engine.schemas import (
    RoleplayScenarioCreate,
    RoleplayScenarioUpdate,
    RoleplaySessionStart,
)
from speakflow.features.learning_plan.engine.service import learning_plan_engine
from speakflow.features.roleplay.application import roleplay_scenario
from speakflow.features.roleplay.application.roleplay_turn import (
    process_roleplay_turn,
)
from speakflow.features.roleplay.domain.engine import aggregate_session
from speakflow.features.roleplay.infrastructure.models import (
    RoleplayScenario,
    RoleplaySession,
)


class CustomRoleplayLifecycleTests(unittest.TestCase):
    client_session_id = "custom-roleplay-lifecycle-20260811"
    titles = ("Join a makerspace", "Join a local makerspace")

    def setUp(self) -> None:
        self._cleanup()

    def tearDown(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
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
                    RoleplayScenario.title.in_(self.titles)
                )
            ).all():
                session.delete(scenario)

    @staticmethod
    def _scenario_payload() -> RoleplayScenarioCreate:
        return RoleplayScenarioCreate(
            category="Community",
            icon="🛠️",
            title="Join a makerspace",
            description=(
                "Ask to join a local makerspace and confirm an introductory visit."
            ),
            ai_role="makerspace coordinator",
            learner_role="prospective makerspace member",
            opening="Welcome. What would you like to make here?",
            objectives=[
                {
                    "id": "purpose",
                    "label": "Explain why you want to join",
                    "weight": 2,
                    "required": True,
                },
                {
                    "id": "experience",
                    "label": "Describe relevant making experience",
                    "weight": 1,
                    "required": True,
                },
                {
                    "id": "visit",
                    "label": "Confirm an introductory visit",
                    "weight": 2,
                    "required": True,
                },
            ],
            target_language=[
                "I would like to join",
                "I have experience with",
                "When can I visit",
            ],
            evaluation_rubric=[
                {
                    "id": "purpose_clarity",
                    "label": "Purpose clarity",
                    "description": "Explains a specific reason for joining the makerspace.",
                    "weight": 2,
                },
                {
                    "id": "next_step",
                    "label": "Next-step management",
                    "description": "Asks for and confirms a practical introductory visit.",
                    "weight": 1,
                },
            ],
            designed_cefr_level="B1",
        )

    def test_custom_scenario_runs_and_keeps_its_snapshot_through_edit_and_delete(
        self,
    ) -> None:
        created = learning_plan_engine.create_roleplay_scenario(
            self._scenario_payload()
        )
        started = learning_plan_engine.start_roleplay_session(
            RoleplaySessionStart(
                client_session_id=self.client_session_id,
                scenario_id=created.id,
            )
        )
        provider_result = {
            "turn_status": "meaningful",
            "understood_meaning": "The learner wants to join the makerspace.",
            "reply": "Great. What kind of making experience do you have?",
            "objective_updates": [
                {"objective_id": "purpose", "evidence": "join the makerspace"}
            ],
            "scenario_complete": False,
        }
        with patch.object(
            roleplay_scenario,
            "_groq_chat",
            return_value=json.dumps(provider_result),
        ):
            turn = process_roleplay_turn(
                client_session_id=self.client_session_id,
                turn_id="turn-custom-lifecycle-0001",
                input_mode="text",
                user_text="I would like to join the makerspace.",
                corrected_text=None,
                word_feedback=[],
                delivery_metrics={},
                grammar_evaluated=False,
            )

        self.assertTrue(started.scenario.custom)
        self.assertEqual(turn["turn_status"], "meaningful")
        self.assertTrue(turn["objective_state"]["purpose"]["completed"])
        context = learning_plan_engine.roleplay_context(self.client_session_id)
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

        update = created.model_dump(exclude={"id", "custom"}, mode="python")
        update["title"] = "Join a local makerspace"
        learning_plan_engine.update_roleplay_scenario(
            created.id,
            RoleplayScenarioUpdate.model_validate(update),
        )
        before_delete = learning_plan_engine.get_roleplay_transcript(
            self.client_session_id
        )
        self.assertEqual(before_delete.scenario.title, "Join a makerspace")

        learning_plan_engine.delete_roleplay_scenario(created.id)
        after_delete = learning_plan_engine.get_roleplay_transcript(
            self.client_session_id
        )
        self.assertEqual(after_delete.scenario.title, "Join a makerspace")
        self.assertEqual(after_delete.turns[0].assistant_text, provider_result["reply"])


if __name__ == "__main__":
    unittest.main()
