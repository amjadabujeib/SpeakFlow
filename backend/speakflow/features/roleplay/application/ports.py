from __future__ import annotations

from typing import Protocol
from uuid import UUID

from speakflow.shared import JsonObject


class RoleplayRepository(Protocol):
    def session_context(self, user_id: UUID, session_id: str) -> JsonObject: ...

    def append_turn(self, user_id: UUID, session_id: str, turn: JsonObject) -> None: ...

    def finalize(self, user_id: UUID, session_id: str, result: JsonObject) -> JsonObject: ...


class ChatProvider(Protocol):
    def reply(self, context: JsonObject, learner_text: str) -> JsonObject: ...
