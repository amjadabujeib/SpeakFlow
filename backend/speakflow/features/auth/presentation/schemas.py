from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignUpInput(StrictAuthModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        clean = value.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean):
            raise ValueError("enter a valid email address")
        return clean

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        clean = " ".join(value.split()).strip()
        if len(clean) < 2:
            raise ValueError("display name must contain at least two characters")
        return clean


class SignInInput(StrictAuthModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class GuestSessionInput(StrictAuthModel):
    display_name: str = Field(default="Guest", min_length=2, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        clean = " ".join(value.split()).strip()
        if len(clean) < 2:
            raise ValueError("display name must contain at least two characters")
        return clean


class AuthUserView(StrictAuthModel):
    user_id: UUID
    kind: Literal["registered", "guest", "local_guest"]
    email: str | None = None
    display_name: str
    is_admin: bool = False


class AuthSessionView(StrictAuthModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: AuthUserView
