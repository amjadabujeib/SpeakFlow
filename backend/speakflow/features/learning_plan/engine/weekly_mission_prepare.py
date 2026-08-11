"""Deterministic preparation of reviewed weekly lesson anchors."""

from __future__ import annotations

import copy
import hashlib

from .curated_lessons import assessment_candidates
from .lexical_policy import (
    LearnerDefinition,
    definition_word_limit,
    resolve_learner_definition,
)
from .retrieval import RetrievedChunk, RetrievedConcept
from .standard import PLP_ARCHITECTURE, PLP_FORMAT_REVISION, PLP_PIPELINE
from .weekly_mission_content import (
    _correct_option_text,
    _first_canonical_answer,
)
from .weekly_mission_models import (
    ChoiceRequest,
    ContextRequest,
    PreparedWeek,
    StimulusRequest,
)
from .weekly_mission_validation import (
    _incorrect_option_texts,
)


def _weekly_lexical_targets(
    candidates: list[RetrievedConcept],
) -> list[RetrievedConcept]:
    """Choose one topical and one contextual term when both are available."""

    direct = [item for item in candidates if item.selection_tier == "direct_interest"]
    related = [item for item in candidates if item.selection_tier == "related_interest"]
    general = [item for item in candidates if item.selection_tier == "general_context"]
    topical = [*direct, *related]
    selected: list[RetrievedConcept] = []
    if topical:
        selected.append(topical[0])
    if general:
        selected.append(general[0])
    for item in [*topical, *general]:
        if item not in selected:
            selected.append(item)
        if len(selected) == 2:
            break
    return selected


def prepare_week(
    *,
    lessons: list[dict],
    chunks: list[RetrievedChunk],
    lexical_palette: list[RetrievedConcept] | None = None,
    support_language: str | None,
    generation_attempt: int = 1,
) -> PreparedWeek:
    if generation_attempt < 1:
        raise ValueError("generation_attempt must be at least 1")
    ordered = tuple(
        sorted((copy.deepcopy(item) for item in lessons), key=lambda x: x["sequence"])
    )
    if len(ordered) != 5 or ordered[-1]["type"] != "assessment":
        raise ValueError(
            "a weekly-mission cohort must contain four teaching lessons and one checkpoint"
        )
    if any(
        item["specification"].get("architecture") != PLP_ARCHITECTURE
        for item in ordered
    ):
        raise ValueError("weekly mission compilation received an incompatible lesson")
    week_values = {item["week_sequence"] for item in ordered}
    if len(week_values) != 1:
        raise ValueError("all weekly cohort lessons must belong to the same week")

    chunks_by_skill: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        if not isinstance(chunk.metadata.get("lesson_template"), dict):
            continue
        for skill_id in chunk.metadata.get("skill_ids", []):
            if skill_id in chunks_by_skill:
                raise ValueError(
                    f"multiple mandatory templates found for skill {skill_id}"
                )
            chunks_by_skill[skill_id] = chunk
    all_skill_ids = list(
        dict.fromkeys(
            skill_id for lesson in ordered for skill_id in lesson["skill_ids"]
        )
    )
    missing = [
        skill_id for skill_id in all_skill_ids if skill_id not in chunks_by_skill
    ]
    if missing:
        raise ValueError(f"reviewed lesson templates are missing for {missing}")

    first_spec = ordered[0]["specification"]
    realization = first_spec["cefr_realization"]
    maximum_sentence_words = int(realization["maximum_sentence_words"])
    # Models are unreliable at counting right up to a semantic boundary. Give
    # the writer 20% headroom while retaining the planner's original value as
    # the compiler's hard rejection limit below.
    writer_sentence_words = max(6, int(maximum_sentence_words * 0.8))
    maximum_input_words = int(realization["input_word_range"][1])
    minimum_stimulus_words = max(12, maximum_sentence_words)
    maximum_stimulus_words = max(
        minimum_stimulus_words,
        maximum_input_words * 2 // 3,
    )
    writer_realization = copy.deepcopy(realization)
    writer_realization["maximum_sentence_words"] = writer_sentence_words
    variation_seed = first_spec.get("variation_seed", "default")
    surface_retry_seed = hashlib.sha256(
        f"{variation_seed}\x1f{ordered[0]['week_sequence']}\x1f{generation_attempt}".encode()
    ).hexdigest()[:24]

    templates: dict[str, dict] = {}
    context_requests: dict[str, ContextRequest] = {}
    stimulus_requests: dict[str, StimulusRequest] = {}
    choice_requests: dict[str, ChoiceRequest] = {}
    checkpoint_pronunciation_activities: dict[str, dict] = {}
    anchors: list[dict] = []

    # A week teaches one small lexical set together. Prefer the dedicated
    # vocabulary lesson; otherwise pre-teach the set in input/noticing. Never
    # scatter unrelated cards positionally across all four lessons.
    vocabulary_lesson = next(
        (item for item in ordered[:-1] if item["type"] == "vocabulary"),
        None,
    )
    learner_definition_limit = definition_word_limit(first_spec["cefr_level"])
    resolved_definitions: dict[str, LearnerDefinition] = {}
    safe_candidates: list[RetrievedConcept] = []
    for item in lexical_palette or []:
        resolved = resolve_learner_definition(
            title=item.title,
            part_of_speech=item.part_of_speech,
            cefr_level=item.cefr_level,
            source_definition=item.definition,
            request_id=item.id,
        )
        if not item.ipa or resolved is None:
            continue
        resolved_definitions[item.id] = resolved
        safe_candidates.append(item)
    eligible_targets = _weekly_lexical_targets(safe_candidates)
    # Only safe, potentially teachable entries belong in the writer contract.
    # Retrievers may over-fetch so an unusable WordNet sense does not suppress
    # the entire weekly lexical set.
    lexical_palette = eligible_targets
    prototype_targets = eligible_targets if len(eligible_targets) == 2 else []
    prototype_host_key = (
        vocabulary_lesson["lesson_key"]
        if vocabulary_lesson is not None
        else ordered[0]["lesson_key"]
    )

    for lesson in ordered[:-1]:
        if len(lesson["skill_ids"]) != 1:
            raise ValueError("a weekly-mission lesson must bind one exact skill")
        skill_id = lesson["skill_ids"][0]
        template = copy.deepcopy(chunks_by_skill[skill_id].metadata["lesson_template"])
        templates[lesson["lesson_key"]] = template
        replacing_vocabulary = (
            lesson["lesson_key"] == prototype_host_key
            and lesson["type"] == "vocabulary"
            and len(prototype_targets) == 2
        )
        anchors.append(
            {
                "lesson_key": lesson["lesson_key"],
                "role": lesson["specification"]["lesson_role"],
                "domain": lesson["type"],
                "skill_id": skill_id,
                "reviewed_title": template["title"],
                "reviewed_description": template["description"],
                "can_do": lesson["specification"]["can_do"],
                "pronunciation_focus": lesson["specification"].get(
                    "pronunciation_focus", []
                ),
            }
        )
        concept_phrase = _first_canonical_answer(template)
        concept_requested = False
        for activity_index, activity in enumerate(template["activities"]):
            activity_type = activity["type"]
            data = activity["data"]
            if activity_type == "vocabulary_card" and not (
                lesson["lesson_key"] == prototype_host_key and replacing_vocabulary
            ):
                request = ContextRequest(
                    request_id=f"{lesson['lesson_key']}:vocab:{activity_index}",
                    lesson_key=lesson["lesson_key"],
                    skill_id=skill_id,
                    activity_index=activity_index,
                    purpose="vocabulary_example",
                    required_phrase=data["word"],
                )
                context_requests[request.request_id] = request
            elif (
                activity_type == "concept" and concept_phrase and not concept_requested
            ):
                request = ContextRequest(
                    request_id=f"{lesson['lesson_key']}:concept:{activity_index}",
                    lesson_key=lesson["lesson_key"],
                    skill_id=skill_id,
                    activity_index=activity_index,
                    purpose="concept_example",
                    required_phrase=concept_phrase,
                )
                context_requests[request.request_id] = request
                concept_requested = True
            elif activity_type in {"reading_comprehension", "listening_comprehension"}:
                question = data["question"]
                answer = _correct_option_text(question)
                request = StimulusRequest(
                    request_id=f"{lesson['lesson_key']}:stimulus:{activity_index}",
                    lesson_key=lesson["lesson_key"],
                    skill_id=skill_id,
                    activity_index=activity_index,
                    mode="reading"
                    if activity_type == "reading_comprehension"
                    else "listening",
                    source_prompt=question["prompt"],
                    canonical_answer=answer,
                    reviewed_distractors=_incorrect_option_texts(question),
                    checkpoint=False,
                )
                stimulus_requests[request.request_id] = request

    checkpoint = ordered[-1]
    for target in prototype_targets:
        host = next(
            item for item in ordered[:-1] if item["lesson_key"] == prototype_host_key
        )
        request = ContextRequest(
            request_id=f"{host['lesson_key']}:prototype_vocab:{target.id[-16:]}",
            lesson_key=host["lesson_key"],
            skill_id=host["skill_ids"][0],
            activity_index=None,
            purpose="prototype_vocabulary",
            required_phrase=target.title,
            prototype_target=target,
        )
        context_requests[request.request_id] = request
    for index, skill_id in enumerate(checkpoint["skill_ids"]):
        template = chunks_by_skill[skill_id].metadata["lesson_template"]
        candidates = assessment_candidates(template)
        if not candidates:
            raise ValueError(f"skill {skill_id} has no reviewed checkpoint anchor")
        receptive = next(
            (
                item
                for item in candidates
                if item["type"] in {"reading_comprehension", "listening_comprehension"}
            ),
            None,
        )
        request_id = f"{checkpoint['lesson_key']}:skill:{index}"
        pronunciation = next(
            (item for item in candidates if item["type"] == "pronunciation_drill"),
            None,
        )
        if pronunciation is not None:
            checkpoint_pronunciation_activities[request_id] = copy.deepcopy(
                pronunciation
            )
        elif receptive is not None:
            question = receptive["data"]["question"]
            stimulus_requests[request_id] = StimulusRequest(
                request_id=request_id,
                lesson_key=checkpoint["lesson_key"],
                skill_id=skill_id,
                activity_index=None,
                mode=(
                    "reading"
                    if receptive["type"] == "reading_comprehension"
                    else "listening"
                ),
                source_prompt=question["prompt"],
                canonical_answer=_correct_option_text(question),
                reviewed_distractors=_incorrect_option_texts(question),
                checkpoint=True,
            )
        else:
            choice = next(
                (item for item in candidates if item["type"] == "multiple_choice"),
                None,
            )
            if choice is None:
                raise ValueError(
                    f"skill {skill_id} needs a reviewed choice or receptive checkpoint anchor"
                )
            data = choice["data"]
            choice_requests[request_id] = ChoiceRequest(
                request_id=request_id,
                lesson_key=checkpoint["lesson_key"],
                skill_id=skill_id,
                source_prompt=data["prompt"],
                canonical_answer=_correct_option_text(data),
                reviewed_distractors=_incorrect_option_texts(data),
                activity_index=None,
                checkpoint=True,
            )

    writer_definitions = {
        item.id: resolved_definitions[item.id].text for item in (lexical_palette or [])
    }
    writer_payload = {
        "pipeline": PLP_PIPELINE,
        "format_revision": PLP_FORMAT_REVISION,
        "week": ordered[0]["week_sequence"],
        "variation_seed": variation_seed,
        "generation_attempt": generation_attempt,
        "surface_retry_seed": surface_retry_seed,
        "cefr_level": first_spec["cefr_level"],
        "mission": first_spec["mission"],
        "goal": first_spec["goal"],
        "interest": first_spec["interest"],
        "scenario_archetype": first_spec["scenario"],
        "cefr_constraints": writer_realization,
        "support_language": support_language,
        "support_rule": (
            "English remains primary. Do not make claims about an L1 group."
            if support_language
            else "Use English only."
        ),
        "lesson_anchors": anchors,
        "lexical_palette": [
            {
                "concept_id": item.id,
                "source_id": item.source_id,
                "term": item.title,
                "part_of_speech": item.part_of_speech,
                "cefr_level": item.cefr_level,
                "topic_tags": item.topic_tags,
                "definition": writer_definitions[item.id],
                "definition_origin": resolved_definitions[item.id].origin,
                "definition_source_id": item.definition_source_id,
                "pronunciation_source_id": item.pronunciation_source_id,
                "selection_tier": item.selection_tier,
                "previously_seen": item.previously_seen,
                "prototype_target": item in prototype_targets,
            }
            for item in (lexical_palette or [])
        ],
        "weekly_vocabulary_to_reuse": [item.title for item in prototype_targets],
        "checkpoint": {
            "lesson_key": checkpoint["lesson_key"],
            "can_do": checkpoint["specification"]["can_do"],
            "skill_ids": checkpoint["skill_ids"],
        },
        "context_requests": [
            {
                "request_id": item.request_id,
                "lesson_key": item.lesson_key,
                "purpose": item.purpose,
                "required_phrase": item.required_phrase,
                "maximum_words": writer_sentence_words,
                "source_definition": (
                    writer_definitions[item.prototype_target.id]
                    if item.prototype_target is not None
                    else None
                ),
                "learner_definition_maximum_words": (
                    learner_definition_limit if item.prototype_target is not None else 0
                ),
            }
            for item in context_requests.values()
        ],
        "stimulus_requests": [
            {
                "request_id": item.request_id,
                "lesson_key": item.lesson_key,
                "mode": item.mode,
                "purpose": "fresh_checkpoint" if item.checkpoint else "teaching_input",
                "prompt_goal": (
                    "Ask for one short, explicit fact stated in the new scenario input."
                ),
                "answer_rule": (
                    "Create a concrete answer of at most ten words, copy it exactly into "
                    "the input, and make both distractors unsupported by the input."
                ),
                "maximum_words_per_sentence": writer_sentence_words,
                "minimum_total_words": minimum_stimulus_words,
                "maximum_total_words": maximum_stimulus_words,
            }
            for item in stimulus_requests.values()
        ],
        "choice_requests": [
            {
                "request_id": item.request_id,
                "lesson_key": item.lesson_key,
                "purpose": (
                    "fresh_parallel_checkpoint"
                    if item.checkpoint
                    else "mission_context_controlled_practice"
                ),
                "prompt_goal": (
                    "Ask for the best response in the new weekly scenario."
                ),
                "canonical_correct_answer": item.canonical_answer,
                "reviewed_question_intent": item.source_prompt,
            }
            for item in choice_requests.values()
        ],
        "required_bucket_counts": {
            "context_realizations": len(context_requests),
            "stimulus_realizations": len(stimulus_requests),
            "choice_realizations": len(choice_requests),
        },
        "output_rules": [
            "Return five surfaces and fill all three typed realization buckets to their exact required counts.",
            "Write a fresh scenario-specific prompt for every stimulus and choice.",
            "Use exactly two plausible but false distractors per stimulus or choice.",
            "Use the variation seed and generation attempt to choose a fresh real-world subject and scenario surface.",
            "Write every stimulus as natural scenario content only; learner questions and directions belong in prompt, never opening, evidence, or closing.",
            "Make every inference answerable from supplied text or the reviewed language target.",
            "Prefer real places, organizations, public works, sports, tools, and natural phenomena.",
            "Use only facts supplied in this request or stable general facts; never fabricate attributed quotations, statistics, reviews, rules, or policies.",
            "Clearly label changing prices, schedules, availability, entry rules, service incidents, and similar operational details as simulated practice data.",
            "Count words before returning: every context and every stimulus sentence must stay within its request limit.",
            "For prototype vocabulary, make learner_definition concrete and easier than source_definition without changing its meaning.",
        ],
    }
    return PreparedWeek(
        lessons=ordered,
        templates=templates,
        chunks_by_skill=chunks_by_skill,
        writer_payload=writer_payload,
        context_requests=context_requests,
        stimulus_requests=stimulus_requests,
        choice_requests=choice_requests,
        checkpoint_pronunciation_activities=checkpoint_pronunciation_activities,
    )
