"""Narrow production-facing services over the transactional engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ..engine.service import LearningPlanEngine, learning_plan_engine


class LearningPlanService:
    def __init__(self, engine: LearningPlanEngine) -> None:
        self._engine = engine

    def save_profile(self, payload: Any) -> Any:
        return self._engine.save_profile(payload)

    def get_profile(self) -> Any:
        return self._engine.get_profile()

    def reset_learner(self) -> Any:
        return self._engine.reset_local_learner()

    def create_generation(self, regenerate: bool = False) -> Any:
        reason = "manual_regeneration" if regenerate else "onboarding"
        return self._engine.create_generation(reason=reason)

    def latest_generation(self) -> Any:
        return self._engine.get_latest_generation()

    def generation(self, job_id: UUID) -> Any:
        return self._engine.get_generation(job_id)

    def retry_generation(self, job_id: UUID) -> Any:
        return self._engine.retry_generation(job_id)

    def active_document(self) -> Any:
        return self._engine.get_active_document()

    def record_attempt(self, activity_id: str, payload: Any, **trusted: Any) -> Any:
        return self._engine.record_attempt(activity_id, payload, **trusted)

    def adaptation_proposals(self) -> Any:
        return self._engine.list_adaptation_proposals()

    def create_adaptation_proposal(self) -> Any:
        return self._engine.create_adaptation_proposal()

    def decide_adaptation(self, proposal_id: UUID, approve: bool) -> Any:
        return self._engine.decide_adaptation(proposal_id, approve)


class LearningPlanLifecycle:
    def __init__(self, engine: LearningPlanEngine) -> None:
        self._engine = engine

    def start(self) -> None:
        self._engine.start_worker()

    def stop(self) -> bool:
        return self._engine.stop_worker()

    def close(self) -> None:
        self._engine.close()

    def health(self) -> dict:
        return self._engine.health()


class PronunciationAssignmentService:
    def __init__(self, engine: LearningPlanEngine) -> None:
        self._engine = engine

    def validate_target(self, activity_id: str, target: str) -> str:
        return self._engine.validate_pronunciation_target(activity_id, target)

    def record_attempt(self, activity_id: str, payload: Any, **trusted: Any) -> Any:
        return self._engine.record_attempt(activity_id, payload, **trusted)


learning_plan_service = LearningPlanService(learning_plan_engine)
learning_plan_lifecycle = LearningPlanLifecycle(learning_plan_engine)
pronunciation_assignment_service = PronunciationAssignmentService(
    learning_plan_engine
)
