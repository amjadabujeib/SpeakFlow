"""User-owned roleplay scenario catalog lifecycle."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from speakflow.features.learning_plan.engine.database import session_scope
from speakflow.features.learning_plan.engine.identity import (
    current_user_id as _user_id,
)
from speakflow.features.learning_plan.engine.schemas import (
    RoleplayScenarioCreate,
    RoleplayScenarioUpdate,
    RoleplayScenarioView,
)
from speakflow.features.learning_plan.engine.service_errors import PlpNotFoundError
from speakflow.features.learning_plan.engine.service_identity import (
    _database_error,
    _ensure_local_user,
)
from speakflow.features.roleplay.domain.engine import (
    builtin_scenarios,
    custom_scenario_definition,
)
from speakflow.features.roleplay.infrastructure.models import RoleplayScenario


class PlpRoleplayScenarioMixin:
    def list_roleplay_scenarios(self) -> list[RoleplayScenarioView]:
        try:
            with session_scope() as session:
                custom_rows = session.scalars(
                    select(RoleplayScenario)
                    .where(RoleplayScenario.user_id == _user_id())
                    .order_by(RoleplayScenario.created_at)
                ).all()
                values = [
                    {**item, "custom": False} for item in builtin_scenarios()
                ]
                values.extend(
                    {**copy.deepcopy(row.definition), "custom": True}
                    for row in custom_rows
                )
                return [RoleplayScenarioView.model_validate(item) for item in values]
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def create_roleplay_scenario(
        self, payload: RoleplayScenarioCreate
    ) -> RoleplayScenarioView:
        try:
            with session_scope() as session:
                _ensure_local_user(session)
                scenario_id = f"custom_{uuid.uuid4().hex[:20]}"
                definition = custom_scenario_definition(
                    scenario_id=scenario_id,
                    category=payload.category,
                    title=payload.title,
                    description=payload.description,
                    designed_cefr_level=payload.designed_cefr_level,
                )
                if payload.ai_role is not None:
                    definition.update(
                        {
                            "icon": payload.icon,
                            "ai_role": payload.ai_role,
                            "learner_role": payload.learner_role,
                            "opening": payload.opening,
                            "objectives": [
                                item.model_dump() for item in payload.objectives or []
                            ],
                            "target_language": list(payload.target_language or []),
                            "evaluation_rubric": [
                                item.model_dump()
                                for item in payload.evaluation_rubric or []
                            ],
                            "designed_cefr_level": payload.designed_cefr_level,
                        }
                    )
                validated = RoleplayScenarioView.model_validate(
                    {**definition, "custom": True}
                )
                definition = validated.model_dump(exclude={"custom"})
                row = RoleplayScenario(
                    id=scenario_id,
                    user_id=_user_id(),
                    category=definition["category"],
                    title=definition["title"],
                    description=definition["description"],
                    definition=definition,
                )
                session.add(row)
                session.flush()
                return RoleplayScenarioView.model_validate(
                    {**definition, "custom": True}
                )
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def update_roleplay_scenario(
        self,
        scenario_id: str,
        payload: RoleplayScenarioUpdate,
    ) -> RoleplayScenarioView:
        """Replace a custom scenario for future sessions only."""
        try:
            with session_scope() as session:
                row = self._owned_scenario_for_update(session, scenario_id)
                validated = RoleplayScenarioView.model_validate(
                    {
                        "id": scenario_id,
                        **payload.model_dump(mode="python"),
                        "custom": True,
                    }
                )
                definition = validated.model_dump(exclude={"custom"})
                row.category = definition["category"]
                row.title = definition["title"]
                row.description = definition["description"]
                row.definition = definition
                session.flush()
                return validated
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def delete_roleplay_scenario(self, scenario_id: str) -> None:
        """Delete a custom scenario while saved sessions retain snapshots."""
        try:
            with session_scope() as session:
                row = self._owned_scenario_for_update(session, scenario_id)
                session.delete(row)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    @staticmethod
    def _owned_scenario_for_update(session, scenario_id: str) -> RoleplayScenario:
        row = session.scalar(
            select(RoleplayScenario)
            .where(
                RoleplayScenario.id == scenario_id,
                RoleplayScenario.user_id == _user_id(),
            )
            .with_for_update()
        )
        if row is None:
            raise PlpNotFoundError("custom roleplay scenario was not found")
        return row
