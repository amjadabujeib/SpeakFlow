"""Explicit roleplay application service over shared transactional storage."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from speakflow.features.learning_plan.application.services import learning_plan_engine


class RoleplayService:
    def list_scenarios(self) -> Any:
        return learning_plan_engine.list_roleplay_scenarios()

    def create_scenario(self, payload: Any) -> Any:
        return learning_plan_engine.create_roleplay_scenario(payload)

    def update_scenario(self, scenario_id: str, payload: Any) -> Any:
        return learning_plan_engine.update_roleplay_scenario(scenario_id, payload)

    def delete_scenario(self, scenario_id: str) -> None:
        learning_plan_engine.delete_roleplay_scenario(scenario_id)

    def start_session(self, payload: Any) -> Any:
        return learning_plan_engine.start_roleplay_session(payload)

    def list_sessions(self, limit: int = 50) -> Any:
        return learning_plan_engine.list_roleplay_sessions(limit)

    def transcript(self, client_session_id: str) -> Any:
        return learning_plan_engine.get_roleplay_transcript(client_session_id)

    def session(self, client_session_id: str) -> Any:
        return learning_plan_engine.get_roleplay_session(client_session_id)

    def context(self, client_session_id: str) -> dict:
        return learning_plan_engine.roleplay_context(client_session_id)

    def turn_lease(self, client_session_id: str) -> AbstractContextManager:
        return learning_plan_engine.roleplay_turn_lease(client_session_id)

    def record_turn(
        self,
        client_session_id: str,
        payload: Any,
        *,
        objective_updates: list[dict],
    ) -> Any:
        return learning_plan_engine.record_roleplay_turn(
            client_session_id,
            payload,
            objective_updates=objective_updates,
        )

    def begin_finalization(self, client_session_id: str) -> bool:
        return learning_plan_engine.begin_roleplay_finalization(client_session_id)

    def release_finalization(self, client_session_id: str) -> None:
        learning_plan_engine.release_roleplay_finalization(client_session_id)

    def complete_session(self, client_session_id: str, **values: Any) -> Any:
        return learning_plan_engine.complete_roleplay_session(
            client_session_id,
            **values,
        )

    def expire_stale_sessions(self) -> None:
        learning_plan_engine._expire_stale_roleplay_sessions()


roleplay_service = RoleplayService()
