from __future__ import annotations

from typing import Protocol
from uuid import UUID

from speakflow.shared import JsonObject


class LearningPlanRepository(Protocol):
    def active_plan(self, user_id: UUID) -> JsonObject: ...

    def save_profile(self, user_id: UUID, profile: JsonObject) -> JsonObject: ...

    def record_attempt(
        self, user_id: UUID, activity_id: str, attempt: JsonObject
    ) -> JsonObject: ...


class GenerationJobPort(Protocol):
    def enqueue(self, user_id: UUID, reason: str) -> UUID: ...

    def status(self, user_id: UUID, job_id: UUID) -> JsonObject: ...
