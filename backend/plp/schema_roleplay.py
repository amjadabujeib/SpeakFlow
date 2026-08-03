from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .config import SUPPORTED_LEVELS
from .schema_core import StrictModel

class RoleplayWordReview(StrictModel):
    word: str = Field(min_length=1, max_length=80)
    confidence: int = Field(ge=0, le=100)


class RoleplaySessionInput(StrictModel):
    client_session_id: str = Field(
        pattern=r"^[a-zA-Z0-9_\-]{8,80}$",
    )
    scenario: str = Field(min_length=1, max_length=160)
    duration_seconds: int = Field(default=0, ge=0, le=21600)
    message_count: int = Field(default=0, ge=0, le=500)
    average_word_confidence: int | None = Field(default=None, ge=0, le=100)
    average_fluency: int | None = Field(default=None, ge=0, le=100)
    average_prosody: int | None = Field(default=None, ge=0, le=100)
    review_words: list[RoleplayWordReview] = Field(
        default_factory=list,
        max_length=100,
    )


class RoleplaySessionView(RoleplaySessionInput):
    id: UUID
    created_at: datetime
    scenario_id: str | None = None
    cefr_level: Literal["A1", "A2", "B1", "B2"] = "B1"
    status: Literal["active", "finalizing", "complete", "abandoned"] = "complete"
    successful_turns: int = Field(default=0, ge=0, le=500)
    spoken_word_count: int = Field(default=0, ge=0, le=50000)
    voiced_seconds: float = Field(default=0, ge=0, le=21600)
    alignment_coverage: float | None = Field(default=None, ge=0, le=1)
    objective_state: dict = Field(default_factory=dict)
    evaluation: dict = Field(default_factory=dict)
    ended_reason: str | None = None
    ended_at: datetime | None = None


class RoleplayObjectiveView(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_\-]{2,80}$")
    label: str = Field(min_length=3, max_length=180)
    weight: int = Field(default=1, ge=1, le=5)
    required: bool = True


class RoleplayRubricView(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_\-]{2,80}$")
    label: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=8, max_length=400)
    weight: int = Field(default=1, ge=1, le=5)


class RoleplayScenarioView(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_\-]{2,100}$")
    category: str = Field(min_length=2, max_length=80)
    icon: str = Field(min_length=1, max_length=8)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=3, max_length=500)
    ai_role: str = Field(min_length=3, max_length=200)
    learner_role: str = Field(min_length=3, max_length=200)
    opening: str = Field(min_length=3, max_length=500)
    objectives: list[RoleplayObjectiveView] = Field(min_length=1, max_length=8)
    target_language: list[str] = Field(default_factory=list, max_length=12)
    evaluation_rubric: list[RoleplayRubricView] = Field(
        default_factory=list,
        max_length=5,
    )
    designed_cefr_level: Literal["A1", "A2", "B1", "B2"] | None = None
    custom: bool = False

    @model_validator(mode="after")
    def validate_roleplay_ids(self) -> "RoleplayScenarioView":
        objective_ids = [item.id for item in self.objectives]
        rubric_ids = [item.id for item in self.evaluation_rubric]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("roleplay objective IDs must be unique")
        if len(rubric_ids) != len(set(rubric_ids)):
            raise ValueError("roleplay rubric IDs must be unique")
        return self


class RoleplayScenarioDraftInput(StrictModel):
    category: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=8, max_length=500)

    @field_validator("category", "title", "description")
    @classmethod
    def clean_draft_text(cls, value: str) -> str:
        return " ".join(value.split()).strip()


class RoleplayScenarioDraftView(StrictModel):
    category: str = Field(min_length=2, max_length=80)
    icon: str = Field(min_length=1, max_length=8)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=8, max_length=500)
    ai_role: str = Field(min_length=3, max_length=200)
    learner_role: str = Field(min_length=3, max_length=200)
    opening: str = Field(min_length=3, max_length=500)
    objectives: list[RoleplayObjectiveView] = Field(min_length=3, max_length=6)
    target_language: list[str] = Field(min_length=2, max_length=10)
    evaluation_rubric: list[RoleplayRubricView] = Field(min_length=2, max_length=4)
    designed_cefr_level: Literal["A1", "A2", "B1", "B2"]
    draft_source: Literal["groq", "reviewable_fallback"]


class RoleplayScenarioCreate(StrictModel):
    category: str = Field(min_length=2, max_length=80)
    icon: str | None = Field(default=None, min_length=1, max_length=8)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=8, max_length=500)
    ai_role: str | None = Field(default=None, min_length=3, max_length=200)
    learner_role: str | None = Field(default=None, min_length=3, max_length=200)
    opening: str | None = Field(default=None, min_length=3, max_length=500)
    objectives: list[RoleplayObjectiveView] | None = Field(
        default=None,
        min_length=3,
        max_length=6,
    )
    target_language: list[str] | None = Field(
        default=None,
        min_length=2,
        max_length=10,
    )
    evaluation_rubric: list[RoleplayRubricView] | None = Field(
        default=None,
        min_length=2,
        max_length=4,
    )
    designed_cefr_level: Literal["A1", "A2", "B1", "B2"] | None = None

    @field_validator(
        "category",
        "title",
        "description",
        "ai_role",
        "learner_role",
        "opening",
    )
    @classmethod
    def clean_scenario_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()).strip() if value is not None else None

    @model_validator(mode="after")
    def validate_complete_custom_contract(self) -> "RoleplayScenarioCreate":
        advanced = (
            self.icon,
            self.ai_role,
            self.learner_role,
            self.opening,
            self.objectives,
            self.target_language,
            self.evaluation_rubric,
            self.designed_cefr_level,
        )
        if any(item is not None for item in advanced) and any(
            item is None for item in advanced
        ):
            raise ValueError(
                "an edited custom scenario must provide the complete draft contract"
            )
        return self


class RoleplaySessionStart(StrictModel):
    client_session_id: str = Field(pattern=r"^[a-zA-Z0-9_\-]{8,80}$")
    scenario_id: str = Field(pattern=r"^[a-z0-9_\-]{2,100}$")


class RoleplaySessionStartView(StrictModel):
    client_session_id: str
    status: Literal["active"]
    scenario: RoleplayScenarioView
    objective_state: dict
    cefr_level: Literal["A1", "A2", "B1", "B2"]


class RoleplayTurnInput(StrictModel):
    turn_id: str = Field(pattern=r"^[a-zA-Z0-9_\-]{8,80}$")
    input_mode: Literal["text", "audio"]
    user_text: str = Field(min_length=1, max_length=3000)
    assistant_text: str = Field(min_length=1, max_length=3000)
    grammar_corrected_text: str | None = Field(default=None, max_length=3000)
    grammar_feedback: str | None = Field(default=None, max_length=1200)
    grammar_error_units: float = Field(default=0, ge=0, le=1000)
    word_count: int = Field(default=0, ge=0, le=10000)
    word_feedback: list[dict] = Field(default_factory=list, max_length=1000)
    delivery_metrics: dict = Field(default_factory=dict)
    objective_evidence: list[dict] = Field(default_factory=list, max_length=8)


class RoleplayTranscriptTurnView(StrictModel):
    turn_id: str
    sequence: int = Field(ge=1, le=500)
    input_mode: Literal["text", "audio"]
    user_text: str
    assistant_text: str
    grammar_corrected_text: str | None = Field(default=None, max_length=3000)
    grammar_feedback: str | None = Field(default=None, max_length=1200)
    word_confidence: list[dict] = Field(default_factory=list, max_length=1000)
    created_at: datetime


class RoleplayTranscriptView(StrictModel):
    read_only: Literal[True] = True
    session: RoleplaySessionView
    scenario: RoleplayScenarioView
    turns: list[RoleplayTranscriptTurnView] = Field(
        default_factory=list,
        max_length=500,
    )


class RoleplayFinalizeInput(StrictModel):
    ended_reason: Literal[
        "objective_completed",
        "learner_ended",
        "back_navigation",
        "disconnected",
        "timeout",
    ] = "learner_ended"


class ArabicTranslationInput(StrictModel):
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def clean_escape_text(cls, value: str) -> str:
        clean = " ".join(value.split()).strip()
        if not clean:
            raise ValueError("text cannot be blank")
        return clean


class ArabicTranslationOption(StrictModel):
    style: Literal["natural", "polite", "formal"]
    label: str = Field(min_length=2, max_length=40)
    text: str = Field(min_length=1, max_length=500)


class ArabicTranslationView(StrictModel):
    source_text: str
    options: list[ArabicTranslationOption] = Field(min_length=3, max_length=3)


class RoleplayFinalizeView(StrictModel):
    session: RoleplaySessionView
    corrections: list[dict] = Field(default_factory=list)


def next_level(level: str) -> str:
    if level not in SUPPORTED_LEVELS:
        raise ValueError(f"unsupported CEFR level: {level}")
    return {"A1": "A2", "A2": "B1", "B1": "B2", "B2": "B2"}[level]
