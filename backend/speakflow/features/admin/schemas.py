from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictAdminModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminModelState(StrictAdminModel):
    whisperx: bool
    pronunciation: bool
    grammar: bool
    tts: bool


class AdminHealthView(StrictAdminModel):
    status: str
    postgres: str
    ollama: str
    groq: str
    curriculum: str = "ready"
    plp_workers: int
    active_jobs: int
    models: AdminModelState


class RecentRegistrationView(StrictAdminModel):
    id: UUID
    email: str
    type: str
    created_at: datetime


class AdminUserSummary(StrictAdminModel):
    total_registered: int
    total_guests: int
    active_sessions: int
    recent_registrations: list[RecentRegistrationView]


class AdminDashboardView(StrictAdminModel):
    health: AdminHealthView
    users: AdminUserSummary


class AdminUserView(StrictAdminModel):
    id: UUID
    email: str | None
    display_name: str
    kind: str
    is_admin: bool
    active_sessions: int
    created_at: datetime


class AdminUserPage(StrictAdminModel):
    items: list[AdminUserView]
    page: int
    page_size: int
    total: int


class AdminAuditEventView(StrictAdminModel):
    id: UUID
    actor_user_id: UUID | None
    target_user_id: UUID | None
    action: str
    detail: dict
    created_at: datetime


class AdminAuditEventPage(StrictAdminModel):
    items: list[AdminAuditEventView]
    page: int
    page_size: int
    total: int


class LessonStatusSummary(StrictAdminModel):
    total: int
    ready: int
    pending: int
    failed: int


class AdminLearningView(StrictAdminModel):
    lessons: LessonStatusSummary
    jobs_by_status: dict[str, int]
    lessons_by_type: dict[str, int]


class RecentRoleplaySessionView(StrictAdminModel):
    id: UUID
    scenario: str
    cefr_level: str
    status: str
    message_count: int
    average_fluency: int | None
    created_at: datetime


class AdminRoleplayView(StrictAdminModel):
    total_sessions: int
    sessions_today: int
    active_now: int
    avg_fluency: float | None
    avg_prosody: float | None
    avg_word_confidence: float | None
    avg_alignment_coverage: float | None
    recent_sessions: list[RecentRoleplaySessionView]


class AdminErrorView(StrictAdminModel):
    job_id: UUID
    failure_kind: str
    message: str
    attempts: int
    updated_at: datetime


class AdminErrorFeedView(StrictAdminModel):
    errors: list[AdminErrorView]


class RevokeSessionsInput(StrictAdminModel):
    reason: str = Field(min_length=3, max_length=200)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if len(normalized) < 3:
            raise ValueError("revocation reason must contain at least 3 characters")
        return normalized


class RevokeSessionsResult(StrictAdminModel):
    status: str
    revoked_count: int
    audit_event_id: UUID
