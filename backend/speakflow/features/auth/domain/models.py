from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: UUID
    kind: Literal["registered", "guest", "local_guest"]
    email: str | None
    display_name: str


@dataclass(frozen=True, slots=True)
class IssuedSession:
    access_token: str
    expires_at: datetime
    user: AuthenticatedUser
    token_type: Literal["bearer"] = "bearer"
