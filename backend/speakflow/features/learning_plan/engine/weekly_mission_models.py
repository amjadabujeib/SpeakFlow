"""One-call weekly scenario realization and deterministic lesson compilation.

The writer is deliberately a surface-language component.  Reviewed curriculum
owns skills and canonical teaching/answer anchors; the planner owns order and
progression; this compiler owns IDs, answer keys, skill bindings, phases,
shuffling, validation, and provenance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .retrieval import RetrievedChunk, RetrievedConcept

_WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?")


class _StrictDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LessonSurface(_StrictDraft):
    lesson_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    intro: str = Field(min_length=1, max_length=700)


class ContextRealization(_StrictDraft):
    request_id: str = Field(min_length=1, max_length=160)
    sentence: str = Field(min_length=3, max_length=500)
    learner_definition: str = Field(default="", max_length=240)


class StimulusRealization(_StrictDraft):
    request_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    # The production format requires opening/evidence/closing because the
    # provider repeatedly violated array minItems. `sentences` and `text`
    # remain only for deterministic fixtures captured under older schemas.
    sentences: list[str] = Field(default_factory=list, max_length=24)
    text: str = Field(default="", max_length=1800)
    opening: str = Field(default="", max_length=500)
    evidence: str = Field(default="", max_length=500)
    closing: str = Field(default="", max_length=500)
    prompt: str = Field(min_length=1, max_length=500)
    # Kept optional in the Python model so old deterministic fixtures remain
    # readable. The production JSON schema requires it.
    answer: str = Field(default="", max_length=160)
    distractors: list[str] = Field(min_length=2, max_length=2)
    explanation: str = Field(min_length=1, max_length=700)


class ChoiceRealization(_StrictDraft):
    request_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=500)
    distractors: list[str] = Field(min_length=2, max_length=2)
    explanation: str = Field(min_length=1, max_length=700)


class FlatRealization(_StrictDraft):
    """Provider-friendly uniform record; unused fields must be empty."""

    request_id: str = Field(min_length=1, max_length=160)
    kind: Literal["context", "stimulus", "choice"]
    sentence: str = Field(default="", max_length=500)
    learner_definition: str = Field(default="", max_length=240)
    title: str = Field(default="", max_length=160)
    text: str = Field(default="", max_length=1800)
    prompt: str = Field(default="", max_length=500)
    answer: str = Field(default="", max_length=160)
    distractors: list[str] = Field(default_factory=list, max_length=2)
    explanation: str = Field(default="", max_length=700)


class WeeklyScenarioDraft(_StrictDraft):
    scenario_title: str = Field(min_length=1, max_length=160)
    setting: str = Field(min_length=1, max_length=500)
    roles: list[str] = Field(min_length=1, max_length=4)
    lesson_surfaces: list[LessonSurface] = Field(min_length=5, max_length=5)
    realizations: list[FlatRealization] = Field(default_factory=list, max_length=40)
    # The flat list is retained only so already captured first-draft fixtures
    # remain readable. The production provider schema emits the typed buckets.
    context_realizations: list[ContextRealization] = Field(
        default_factory=list, max_length=20
    )
    stimulus_realizations: list[StimulusRealization] = Field(
        default_factory=list, max_length=16
    )
    choice_realizations: list[ChoiceRealization] = Field(
        default_factory=list, max_length=8
    )


@dataclass(frozen=True)
class ContextRequest:
    request_id: str
    lesson_key: str
    skill_id: str
    activity_index: int | None
    purpose: Literal[
        "vocabulary_example",
        "concept_example",
        "prototype_vocabulary",
    ]
    required_phrase: str
    prototype_target: RetrievedConcept | None = None


@dataclass(frozen=True)
class StimulusRequest:
    request_id: str
    lesson_key: str
    skill_id: str
    activity_index: int | None
    mode: Literal["reading", "listening"]
    source_prompt: str
    canonical_answer: str
    reviewed_distractors: tuple[str, str]
    checkpoint: bool


@dataclass(frozen=True)
class ChoiceRequest:
    request_id: str
    lesson_key: str
    skill_id: str
    source_prompt: str
    canonical_answer: str
    reviewed_distractors: tuple[str, str]
    activity_index: int | None
    checkpoint: bool


@dataclass(frozen=True)
class PreparedWeek:
    lessons: tuple[dict, ...]
    templates: dict[str, dict]
    chunks_by_skill: dict[str, RetrievedChunk]
    writer_payload: dict
    context_requests: dict[str, ContextRequest]
    stimulus_requests: dict[str, StimulusRequest]
    choice_requests: dict[str, ChoiceRequest]
    checkpoint_pronunciation_activities: dict[str, dict]


def _text_schema(minimum: int, maximum: int) -> dict:
    return {"type": "string", "minLength": minimum, "maxLength": maximum}


def _strict_object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def weekly_scenario_schema(
    context_ids: list[str] | None = None,
    stimulus_ids: list[str] | None = None,
    choice_ids: list[str] | None = None,
    sentence_character_limit: int = 180,
    lesson_ids: list[str] | None = None,
) -> dict:
    surface = _strict_object(
        {
            "lesson_key": (
                {"type": "string", "enum": lesson_ids}
                if lesson_ids
                else _text_schema(1, 100)
            ),
            "title": _text_schema(1, 160),
            "description": _text_schema(1, 500),
            "intro": _text_schema(1, 700),
        }
    )
    context = _strict_object(
        {
            "sentence": _text_schema(3, 500),
            "learner_definition": _text_schema(0, 240),
        }
    )
    stimulus = _strict_object(
        {
            "title": _text_schema(1, 160),
            "opening": _text_schema(3, sentence_character_limit),
            "evidence": _text_schema(3, sentence_character_limit),
            "closing": _text_schema(3, sentence_character_limit),
            "prompt": _text_schema(1, 500),
            "answer": _text_schema(1, 160),
            "distractors": {
                "type": "array",
                "items": _text_schema(1, 300),
                "minItems": 2,
                "maxItems": 2,
            },
            "explanation": _text_schema(1, 700),
        }
    )
    choice = _strict_object(
        {
            "prompt": _text_schema(1, 500),
            "distractors": {
                "type": "array",
                "items": _text_schema(1, 300),
                "minItems": 2,
                "maxItems": 2,
            },
            "explanation": _text_schema(1, 700),
        }
    )
    return _strict_object(
        {
            "scenario_title": _text_schema(1, 160),
            "setting": _text_schema(1, 500),
            "roles": {
                "type": "array",
                "items": _text_schema(1, 100),
                "minItems": 1,
                "maxItems": 4,
            },
            "lesson_surfaces": {
                "type": "array",
                "items": surface,
                "minItems": 5,
                "maxItems": 5,
            },
            "context_realizations": {
                "type": "object",
                "properties": {
                    request_id: context for request_id in (context_ids or [])
                },
                "required": context_ids or [],
                "additionalProperties": False,
            },
            "stimulus_realizations": {
                "type": "object",
                "properties": {
                    request_id: stimulus for request_id in (stimulus_ids or [])
                },
                "required": stimulus_ids or [],
                "additionalProperties": False,
            },
            "choice_realizations": {
                "type": "object",
                "properties": {request_id: choice for request_id in (choice_ids or [])},
                "required": choice_ids or [],
                "additionalProperties": False,
            },
        }
    )
