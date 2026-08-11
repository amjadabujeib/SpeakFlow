from __future__ import annotations

import copy
import hashlib
import json
import unittest

from speakflow.features.learning_plan.engine.generator import GenerationError
from speakflow.features.learning_plan.engine.planner import PlanningSkill, build_outline
from speakflow.features.learning_plan.engine.retrieval import (
    RetrievedChunk,
    RetrievedConcept,
)
from speakflow.features.learning_plan.engine.schemas import LearnerProfileInput
from speakflow.features.learning_plan.engine.seed import seed_records
from speakflow.features.learning_plan.engine.service_grading import _sanitize_content
from speakflow.features.learning_plan.engine.weekly_mission import (
    ChoiceRealization,
    ContextRealization,
    LessonSurface,
    StimulusRealization,
    WeeklyMissionGenerator,
    WeeklyScenarioDraft,
    compile_week,
    prepare_week,
    weekly_scenario_schema,
)
from speakflow.features.learning_plan.engine.weekly_mission_payload import (
    _failed_generation_json,
)
from speakflow.features.learning_plan.engine.weekly_mission_validation import (
    _parse_weekly_draft,
    _scored_fingerprints,
)


def _week_fixture(week_sequence: int = 1):
    source, skill_rows, chunk_rows = seed_records()
    skills = [
        PlanningSkill(
            id=item["id"],
            domain=item["domain"],
            level=item["cefr_level"],
            title=item["title"],
            description=item["description"],
            outcomes=item["outcomes"],
        )
        for item in skill_rows
    ]
    profile = LearnerProfileInput(
        cefr_level="B1",
        native_language="Arabic",
        learning_goals=["Speak confidently", "Communicate at work"],
        interests=["Technology", "Travel"],
    )
    outline = build_outline(profile, skills)
    week = next(item for item in outline["weeks"] if item["sequence"] == week_sequence)
    lesson_shells = []
    for lesson in week["units"][0]["lessons"]:
        shell = copy.deepcopy(lesson)
        shell["week_sequence"] = week["sequence"]
        lesson_shells.append(shell)

    required_skill_ids = {
        skill_id for lesson in lesson_shells for skill_id in lesson["skill_ids"]
    }
    chunks = []
    for item in chunk_rows:
        if not required_skill_ids.intersection(item["metadata"]["skill_ids"]):
            continue
        chunks.append(
            RetrievedChunk(
                id=item["id"],
                source_id=item["source_id"],
                content=item["content"],
                metadata=copy.deepcopy(item["metadata"]),
                score=1.0,
                content_hash=hashlib.sha256(
                    item["content"].encode("utf-8")
                ).hexdigest(),
            )
        )
    prepared = prepare_week(
        lessons=lesson_shells,
        chunks=chunks,
        support_language="Arabic",
    )
    return source, lesson_shells, chunks, prepared


def _week_one_fixture():
    return _week_fixture()


def _valid_draft(prepared) -> WeeklyScenarioDraft:
    lesson_surfaces = [
        LessonSurface(
            lesson_key=lesson["lesson_key"],
            title=f"Mission surface {index}",
            description=f"Complete part {index} of the real-world weekly mission.",
            intro=f"Use the supplied evidence to complete mission step {index}.",
        )
        for index, lesson in enumerate(prepared.lessons, start=1)
    ]
    contexts = []
    for index, request in enumerate(prepared.context_requests.values(), start=1):
        contexts.append(
            ContextRealization(
                request_id=request.request_id,
                sentence=(
                    f"The community case {index} uses {request.required_phrase} "
                    "in a clear context."
                ),
                learner_definition=(
                    {
                        "device": "an instrument made for one clear purpose",
                    }.get(
                        request.prototype_target.title.casefold(),
                        "a connected system used to share information",
                    )
                    if request.prototype_target is not None
                    else ""
                ),
            )
        )
    prototype_terms = [
        request.prototype_target.title
        for request in prepared.context_requests.values()
        if request.prototype_target is not None
    ]
    teaching_stimulus_ids = [
        request.request_id
        for request in prepared.stimulus_requests.values()
        if not request.checkpoint
    ]
    assigned_terms = {
        request_id: [
            term
            for term_index, term in enumerate(prototype_terms)
            if teaching_stimulus_ids
            and teaching_stimulus_ids[term_index % len(teaching_stimulus_ids)]
            == request_id
        ]
        for request_id in teaching_stimulus_ids
    }
    stimuli = []
    for index, request in enumerate(prepared.stimulus_requests.values(), start=1):
        stimuli.append(
            StimulusRealization(
                request_id=request.request_id,
                title=f"Real-world input {index}",
                text=(
                    f"{request.canonical_answer}. "
                    f"This supplied detail resolves community case {index}."
                    " The team reviews the supplied notes before meeting."
                    " Each member compares the available choices carefully."
                    " They discuss the evidence and agree on one practical next step."
                    + "".join(
                        f" The community team uses {term}."
                        for term in assigned_terms.get(request.request_id, [])
                    )
                ),
                prompt=f"Which detail resolves real-world input {index}?",
                distractors=[
                    f"Unsupported alternative {index} alpha",
                    f"Unsupported alternative {index} beta",
                ],
                explanation="The supplied input states this detail directly.",
            )
        )
    choices = []
    for index, request in enumerate(prepared.choice_requests.values(), start=1):
        choices.append(
            ChoiceRealization(
                request_id=request.request_id,
                prompt=f"Which response completes checkpoint item {index}?",
                distractors=[
                    f"Unsupported checkpoint {index} alpha",
                    f"Unsupported checkpoint {index} beta",
                ],
                explanation="The reviewed language target supports this response.",
            )
        )
    return WeeklyScenarioDraft(
        scenario_title="A community team solves an Android device problem",
        setting="A community workshop using an Android phone and supplied support notes.",
        roles=["learner", "support partner"],
        lesson_surfaces=lesson_surfaces,
        context_realizations=contexts,
        stimulus_realizations=stimuli,
        choice_realizations=choices,
    )


def _compile(prepared, draft):
    return compile_week(
        prepared=prepared,
        draft=draft,
        provider="groq",
        model="test-scenario-writer",
        response_hash="a" * 64,
    )


def _replace_draft(draft: WeeklyScenarioDraft, **changes) -> WeeklyScenarioDraft:
    payload = draft.model_dump(mode="python")
    payload.update(changes)
    return WeeklyScenarioDraft.model_validate(payload)


class _FakeStructuredWriter:
    def __init__(self, draft: WeeklyScenarioDraft, *, provider: str = "groq"):
        self.provider = provider
        self.model_name = "fake-structured-writer"
        self.last_request_metadata = {
            "request_count": 1,
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
        }
        self.draft = draft
        self.calls: list[dict] = []

    def request_structured(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.draft.model_dump_json()


class WeeklyMissionCompilerTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.lessons, cls.chunks, cls.prepared = _week_one_fixture()
        cls.draft = _valid_draft(cls.prepared)
        cls.compiled = _compile(cls.prepared, cls.draft)


__all__ = [name for name in globals() if not name.startswith("__")]
