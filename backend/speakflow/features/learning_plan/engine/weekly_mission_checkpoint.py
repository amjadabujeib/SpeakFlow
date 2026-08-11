"""Compile the independent checkpoint at the end of a weekly mission."""

from __future__ import annotations

from .curated_lessons import SCORED_TYPES
from .generator import LessonGenerator, _DraftActivity, _LessonDraft
from .weekly_mission_content import _choice_data, _stimulus_data
from .weekly_mission_models import PreparedWeek, WeeklyScenarioDraft
from .weekly_mission_payload import _generated_payload
from .weekly_mission_validation import _scored_fingerprints


def compile_checkpoint(
    *,
    prepared: PreparedWeek,
    draft: WeeklyScenarioDraft,
    surfaces: dict,
    stimuli: dict,
    choices: dict,
    stimulus_texts: dict[str, str],
    stimulus_prompts: dict[str, str],
    stimulus_answers: dict[str, str],
    stimulus_distractors: dict[str, list[str]],
    choice_prompts: dict[str, str],
    choice_distractors: dict[str, list[str]],
    teaching_fingerprints: set[str],
    provider: str,
    model: str,
    response_hash: str,
    weekly_pack_id: str,
    generation_metadata: dict | None,
    preserved_distractor_ids: set[str],
    inserted_answer_evidence_ids: set[str],
    extended_input_context_ids: set[str],
    surface_ids_rebound: bool,
) -> tuple[str, tuple[dict, list[str]]]:
    checkpoint = prepared.lessons[-1]
    checkpoint_surface = surfaces[checkpoint["lesson_key"]]
    checkpoint_activities: list[_DraftActivity] = []
    activity_skill_ids: list[list[str]] = []
    for index, skill_id in enumerate(checkpoint["skill_ids"]):
        request_id = f"{checkpoint['lesson_key']}:skill:{index}"
        if request_id in prepared.checkpoint_pronunciation_activities:
            pronunciation = prepared.checkpoint_pronunciation_activities[request_id]
            activity_type = "pronunciation_drill"
            data = pronunciation["data"]
        elif request_id in prepared.stimulus_requests:
            request = prepared.stimulus_requests[request_id]
            activity_type = (
                "reading_comprehension"
                if request.mode == "reading"
                else "listening_comprehension"
            )
            data = _stimulus_data(
                request=request,
                realization=stimuli[request_id],
                text=stimulus_texts[request_id],
                prompt=stimulus_prompts[request_id],
                answer=stimulus_answers[request_id],
                distractors=stimulus_distractors[request_id],
            )
        else:
            request = prepared.choice_requests[request_id]
            activity_type = "multiple_choice"
            data = _choice_data(
                seed=request_id,
                prompt=choice_prompts[request_id],
                canonical_answer=request.canonical_answer,
                distractors=choice_distractors[request_id],
                explanation=choices[request_id].explanation,
            )
        checkpoint_activities.append(_DraftActivity(type=activity_type, data=data))
        activity_skill_ids.append([skill_id])

    checkpoint_draft = _LessonDraft(
        title=checkpoint_surface.title,
        description=checkpoint_surface.description,
        intro=checkpoint_surface.intro,
        activities=checkpoint_activities,
    )
    checkpoint_chunks = [
        prepared.chunks_by_skill[skill_id] for skill_id in checkpoint["skill_ids"]
    ]
    checkpoint_source_ids = sorted({chunk.source_id for chunk in checkpoint_chunks})
    checkpoint_content = LessonGenerator._validate_and_assign(
        draft=checkpoint_draft,
        lesson_key=checkpoint["lesson_key"],
        allowed_types=set(SCORED_TYPES),
        source_ids=checkpoint_source_ids,
        domain="assessment",
        default_skill_ids=checkpoint["skill_ids"],
        activity_skill_ids=activity_skill_ids,
        activity_phases=[
            (
                "review"
                if skill_ids[0]
                in checkpoint["specification"].get("review_skill_ids", [])
                else "independent_check"
            )
            for skill_ids in activity_skill_ids
        ],
    )
    checkpoint_fingerprints = _scored_fingerprints(
        checkpoint_content.model_dump(mode="json")
    )
    if teaching_fingerprints & checkpoint_fingerprints:
        raise ValueError(
            "a checkpoint reuses an exposed teaching prompt/answer fingerprint"
        )
    payload = _generated_payload(
        lesson=checkpoint,
        surface=checkpoint_surface,
        content=checkpoint_content.model_dump(mode="json"),
        chunks=checkpoint_chunks,
        provider=provider,
        model=model,
        response_hash=response_hash,
        weekly_pack_id=weekly_pack_id,
        scenario_title=draft.scenario_title,
        setting=draft.setting,
        roles=draft.roles,
        generation_metadata=generation_metadata,
        preserved_context_ids=[],
        preserved_distractor_ids=sorted(preserved_distractor_ids),
        inserted_answer_evidence_ids=sorted(inserted_answer_evidence_ids),
        extended_input_context_ids=sorted(extended_input_context_ids),
        surface_ids_rebound=surface_ids_rebound,
    )
    return checkpoint["lesson_key"], (payload, checkpoint_source_ids)
