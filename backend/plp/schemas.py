from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import SUPPORTED_LEVELS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignUpInput(StrictModel):
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


class SignInInput(StrictModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class GuestSessionInput(StrictModel):
    display_name: str = Field(default="Guest", min_length=2, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        clean = " ".join(value.split()).strip()
        if len(clean) < 2:
            raise ValueError("display name must contain at least two characters")
        return clean


class AuthUserView(StrictModel):
    user_id: UUID
    kind: Literal["registered", "guest", "local_guest"]
    email: str | None = None
    display_name: str


class AuthSessionView(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: AuthUserView


class LearnerProfileInput(StrictModel):
    cefr_level: Literal["A1", "A2", "B1", "B2"]
    native_language: str = Field(min_length=2, max_length=40)
    support_language: str | None = Field(default=None, max_length=40)
    learning_goals: list[str] = Field(min_length=1, max_length=2)
    interests: list[str] = Field(min_length=1, max_length=3)
    # These retained fields keep stored v2 snapshots readable, but they are no
    # longer onboarding choices. The product owns the defaults.
    preferred_contexts: list[str] = Field(default_factory=list, max_length=6)
    accent_preference: Literal["no_preference"] = "no_preference"
    days_per_week: Literal[5] = 5
    minutes_per_day: Literal[20] = 20
    pronunciation_priorities: list[str] = Field(default_factory=list, max_length=8)

    @field_validator(
        "learning_goals",
        "interests",
        "preferred_contexts",
        "pronunciation_priorities",
    )
    @classmethod
    def clean_string_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(value.split()).strip()
            key = normalized.casefold()
            if not normalized or key in seen:
                continue
            if len(normalized) > 80:
                raise ValueError("preference values must be at most 80 characters")
            seen.add(key)
            cleaned.append(normalized)
        return cleaned

    @model_validator(mode="after")
    def derive_product_defaults(self) -> "LearnerProfileInput":
        # Native-language support is useful for hints and L1-aware planning;
        # the learner should not have to answer the same language question
        # twice. Pronunciation targets are derived by the planner, not entered
        # as self-diagnoses during onboarding.
        if self.support_language is None:
            self.support_language = self.native_language
        self.preferred_contexts = []
        self.pronunciation_priorities = []
        from .mission_catalog import (
            CatalogSelectionError,
            normalize_goals,
            normalize_interests,
        )

        try:
            normalize_goals(self.learning_goals)
            normalize_interests(self.interests)
        except CatalogSelectionError as exc:
            raise ValueError(str(exc)) from exc
        return self


class LearnerProfileView(LearnerProfileInput):
    user_id: UUID
    revision: int
    updated_at: datetime


class LocalLearnerResetResult(StrictModel):
    status: Literal["reset"] = "reset"


class SourceView(StrictModel):
    id: str
    title: str
    locator: str
    license: str
    version: str


class CompletionPolicy(StrictModel):
    mode: Literal["required_activities", "minimum_score"]
    minimum_score: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def validate_mode(self) -> "CompletionPolicy":
        if self.mode == "minimum_score" and self.minimum_score is None:
            raise ValueError("minimum_score mode requires minimum_score")
        if self.mode == "required_activities" and self.minimum_score is not None:
            raise ValueError("required_activities must not define minimum_score")
        return self


class VocabularyData(StrictModel):
    concept_id: str | None = Field(default=None, min_length=1, max_length=240)
    word: str = Field(min_length=1, max_length=80)
    part_of_speech: str = Field(min_length=1, max_length=40)
    ipa: str = Field(min_length=1, max_length=100)
    definition: str = Field(min_length=1, max_length=500)
    source_definition: str | None = Field(default=None, min_length=1, max_length=500)
    definition_origin: Literal[
        "source",
        "weekly_writer_simplified",
        "reviewed_project_gloss",
    ] = "source"
    examples: list[str] = Field(min_length=1, max_length=4)
    collocations: list[str] = Field(default_factory=list, max_length=6)
    native_hint: str | None = Field(default=None, max_length=240)


class ConceptData(StrictModel):
    explanation: str = Field(min_length=1, max_length=1200)
    key_points: list[str] = Field(min_length=1, max_length=6)
    examples: list[str] = Field(min_length=1, max_length=6)
    native_hint: str | None = Field(default=None, max_length=300)


class PronunciationData(StrictModel):
    sound_label: str = Field(min_length=1, max_length=80)
    ipa: str = Field(min_length=1, max_length=80)
    instructions: str = Field(min_length=1, max_length=700)
    tips: list[str] = Field(min_length=1, max_length=5)
    practice_items: list[str] = Field(min_length=2, max_length=8)
    native_hint: str | None = Field(default=None, max_length=300)


class ChoiceOption(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_\-]+$", max_length=80)
    text: str = Field(min_length=1, max_length=300)


class MultipleChoiceData(StrictModel):
    prompt: str = Field(min_length=1, max_length=500)
    options: list[ChoiceOption] = Field(min_length=3, max_length=5)
    correct_option_id: str
    explanation: str = Field(min_length=1, max_length=700)

    @model_validator(mode="after")
    def validate_answer(self) -> "MultipleChoiceData":
        ids = [item.id for item in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("option IDs must be unique")
        if self.correct_option_id not in ids:
            raise ValueError("correct_option_id must refer to an option")
        return self


class FillBlankData(StrictModel):
    prompt: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(min_length=1, max_length=8)
    explanation: str = Field(min_length=1, max_length=700)

    @field_validator("accepted_answers")
    @classmethod
    def validate_answers(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.casefold().split()) for value in values]
        if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("accepted answers must be non-empty and unique")
        return values


class ReadingData(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    passage: str = Field(min_length=30, max_length=1800)
    question: MultipleChoiceData
    native_hint: str | None = Field(default=None, max_length=300)


class ListeningData(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    transcript: str = Field(min_length=10, max_length=1000)
    question: MultipleChoiceData
    voice: Literal["american", "british"] = "american"


class SentenceOrderData(StrictModel):
    prompt: str = Field(min_length=1, max_length=300)
    tokens: list[ChoiceOption] = Field(min_length=3, max_length=16)
    correct_order: list[str] = Field(min_length=3, max_length=16)
    explanation: str = Field(min_length=1, max_length=700)

    @model_validator(mode="after")
    def validate_order(self) -> "SentenceOrderData":
        ids = [item.id for item in self.tokens]
        if len(ids) != len(set(ids)) or sorted(ids) != sorted(self.correct_order):
            raise ValueError("correct_order must contain every unique token ID once")
        return self


class GuidedSpeakingData(StrictModel):
    prompt: str = Field(min_length=1, max_length=500)
    target_expressions: list[str] = Field(min_length=1, max_length=6)
    preparation_tip: str = Field(min_length=1, max_length=400)
    minimum_seconds: int = Field(default=10, ge=5, le=120)


ActivityData = Annotated[
    VocabularyData
    | ConceptData
    | PronunciationData
    | MultipleChoiceData
    | FillBlankData
    | ReadingData
    | ListeningData
    | SentenceOrderData
    | GuidedSpeakingData,
    Field(union_mode="left_to_right"),
]


class Activity(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_\-]+$", max_length=100)
    type: Literal[
        "vocabulary_card",
        "concept",
        "pronunciation_drill",
        "multiple_choice",
        "fill_blank",
        "reading_comprehension",
        "listening_comprehension",
        "sentence_order",
        "guided_speaking",
    ]
    phase: Literal[
        "learn", "guided_practice", "independent_check", "review"
    ] = "learn"
    required: bool = True
    source_refs: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list, max_length=8)
    data: dict

    @model_validator(mode="after")
    def validate_typed_data(self) -> "Activity":
        model_by_type = {
            "vocabulary_card": VocabularyData,
            "concept": ConceptData,
            "pronunciation_drill": PronunciationData,
            "multiple_choice": MultipleChoiceData,
            "fill_blank": FillBlankData,
            "reading_comprehension": ReadingData,
            "listening_comprehension": ListeningData,
            "sentence_order": SentenceOrderData,
            "guided_speaking": GuidedSpeakingData,
        }
        self.data = model_by_type[self.type].model_validate(self.data).model_dump()
        return self


class LessonContent(StrictModel):
    intro: str = Field(min_length=1, max_length=700)
    activities: list[Activity] = Field(min_length=2, max_length=10)


class PublicActivity(StrictModel):
    """A validated activity after private answer fields are removed for clients."""

    id: str = Field(pattern=r"^[a-zA-Z0-9_\-]+$", max_length=100)
    type: Literal[
        "vocabulary_card", "concept", "pronunciation_drill", "multiple_choice",
        "fill_blank", "reading_comprehension", "listening_comprehension",
        "sentence_order", "guided_speaking",
    ]
    phase: Literal[
        "learn", "guided_practice", "independent_check", "review"
    ] = "learn"
    required: bool = True
    source_refs: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list, max_length=8)
    data: dict


class PublicLessonContent(StrictModel):
    intro: str = Field(min_length=1, max_length=700)
    activities: list[PublicActivity] = Field(min_length=2, max_length=10)


class LessonGrounding(StrictModel):
    origin: Literal["retrieval_generated", "curated"]
    review_status: Literal["generated_validated", "reviewed", "pending", "failed"]
    retrieval_tags: list[str]
    source_refs: list[str]
    source_chunks: list[dict] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class LessonView(StrictModel):
    id: str
    sequence: int = Field(ge=1)
    type: Literal[
        "vocabulary", "grammar", "pronunciation", "reading", "listening",
        "speaking", "discourse", "assessment"
    ]
    title: str
    description: str
    estimated_minutes: int = Field(ge=5, le=60)
    xp: int = Field(ge=0, le=1000)
    completion_policy: CompletionPolicy
    objectives: list[str]
    skill_ids: list[str]
    required_lesson_ids: list[str]
    personalization_reason: str
    lesson_role: str | None = None
    can_do_statement: str | None = None
    content_instance_id: str | None = None
    grounding: LessonGrounding
    content_status: Literal["pending", "ready", "failed"]
    content: PublicLessonContent | None

    @model_validator(mode="after")
    def validate_content_status(self) -> "LessonView":
        if (self.content_status == "ready") != (self.content is not None):
            raise ValueError("ready lessons require content; other states forbid it")
        return self


class UnitView(StrictModel):
    id: str
    sequence: int = Field(ge=1)
    title: str
    description: str
    objectives: list[str]
    lessons: list[LessonView] = Field(min_length=1)


class WeekView(StrictModel):
    id: str
    sequence: int = Field(ge=1, le=4)
    title: str
    description: str
    objectives: list[str]
    mission: dict | None = None
    units: list[UnitView] = Field(min_length=1)


class ScheduleView(StrictModel):
    duration_weeks: Literal[4] = 4
    days_per_week: Literal[5] = 5
    minutes_per_day: Literal[20] = 20


class PlanView(StrictModel):
    id: str
    revision: int = Field(ge=1)
    architecture: str | None = None
    variation_seed: str | None = None
    title: str
    description: str
    level: dict[str, str]
    schedule: ScheduleView
    focus_areas: list[str]
    weeks: list[WeekView] = Field(min_length=4, max_length=4)


class LearnerSnapshot(StrictModel):
    native_language: str
    support_language: str | None
    learning_goals: list[str]
    interests: list[str]
    preferred_contexts: list[str]
    accent_preference: str
    pronunciation_priorities: list[str]


class GenerationView(StrictModel):
    job_id: UUID
    status: Literal[
        "queued", "generating_week_one", "generating_future_weeks",
        "generating_initial", "generating_next", "idle",
        "complete", "failed", "waiting_for_model"
    ]
    ready_weeks: int = Field(ge=0, le=4)
    total_weeks: Literal[4] = 4
    completed_lessons: int = Field(ge=0)
    total_lessons: int = Field(ge=1)
    failed_lesson_ids: list[str]
    error: str | None = None
    failure_kind: str | None = None
    retry_available_at: datetime | None = None
    retry_after_seconds: int = Field(default=0, ge=0, le=300)


class LessonProgressView(StrictModel):
    status: Literal["in_progress", "completed"]
    progress_fraction: float = Field(ge=0, le=1)
    best_score: int | None = Field(default=None, ge=0, le=100)
    attempts: int = Field(ge=0)
    completed_activity_ids: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None


class ProgressView(StrictModel):
    current_lesson_id: str | None
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    weekly_goal_days: Literal[5] = 5
    studied_dates_this_week: list[str]
    lesson_states: dict[str, LessonProgressView]


class PlpDocumentV2(StrictModel):
    schema_version: Literal[2] = 2
    generation: GenerationView
    plan: PlanView
    learner_snapshot: LearnerSnapshot
    progress: ProgressView
    knowledge_sources: list[SourceView]


class GenerationAccepted(StrictModel):
    job_id: UUID
    plan_id: UUID
    status: Literal["queued"] = "queued"


class ActivityAttemptInput(StrictModel):
    attempt_kind: Literal["initial", "correction"] = "initial"
    attempt_session_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_\-]{8,80}$",
    )
    selected_option_id: str | None = None
    text_answer: str | None = Field(default=None, max_length=1000)
    ordered_token_ids: list[str] | None = None
    transcript: str | None = Field(default=None, max_length=3000)
    duration_seconds: float | None = Field(default=None, ge=0, le=600)


class ActivityAttemptResult(StrictModel):
    correct: bool | None
    score: int = Field(ge=0, le=100)
    explanation: str
    correct_response: dict | None = None
    first_attempt: bool
    mastery_evidence_recorded: bool
    lesson_score: int | None = Field(default=None, ge=0, le=100)
    lesson_completed: bool
    newly_completed: bool = False
    xp_awarded: int = Field(default=0, ge=0)
    lesson_progress: LessonProgressView


class AdaptationProposalView(StrictModel):
    id: UUID
    status: Literal["pending", "approved", "rejected"]
    summary: str
    changes: list[dict]
    evidence: list[dict]
    created_at: datetime


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
    scenario_version: int = Field(default=1, ge=1)
    cefr_level: Literal["A1", "A2", "B1", "B2"] = "B1"
    status: Literal["active", "finalizing", "complete", "abandoned"] = "complete"
    successful_turns: int = Field(default=0, ge=0, le=500)
    spoken_word_count: int = Field(default=0, ge=0, le=50000)
    voiced_seconds: float = Field(default=0, ge=0, le=21600)
    alignment_coverage: float | None = Field(default=None, ge=0, le=1)
    objective_state: dict = Field(default_factory=dict)
    evaluation: dict = Field(default_factory=dict)
    evaluation_version: str | None = None
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
    version: int = Field(default=1, ge=1)
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
