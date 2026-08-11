from __future__ import annotations

import copy
import hashlib
import json
import re

from .generator import (
    DOMAIN_ACTIVITY_TYPES,
    LessonGenerator,
    _LessonDraft,
)
from .learner_glosses import reviewed_learner_gloss
from .lexical_definition_policy import (
    contains_phrase as _contains_phrase,
)
from .lexical_definition_policy import (
    optional_learner_definition,
    validate_learner_definition,
)
from .weekly_mission_checkpoint import compile_checkpoint
from .weekly_mission_content import (
    _activity_phases,
    _fallback_prototype_example,
    _partition_realizations,
    _prototype_card,
    _replace_vocabulary_lesson,
    _stimulus_data,
)
from .weekly_mission_models import _WORD, PreparedWeek, WeeklyScenarioDraft
from .weekly_mission_payload import _generated_payload
from .weekly_mission_validation import (
    _checkpoint_position,
    _contextualize_choice_prompt,
    _contextualize_stimulus_prompt,
    _is_stimulus_instruction,
    _lesson_display_title,
    _normalize,
    _phrase_pattern,
    _require_exact_ids,
    _require_fresh_text,
    _scored_fingerprints,
    _sentences,
    _stimulus_segments,
    _unique_by_id,
    _validate_options,
    _writer_or_reviewed_distractors,
)


def compile_week(
    *,
    prepared: PreparedWeek,
    draft: WeeklyScenarioDraft,
    provider: str,
    model: str,
    response_hash: str,
    generation_metadata: dict | None = None,
) -> dict[str, tuple[dict, list[str]]]:
    expected_lesson_ids = [item["lesson_key"] for item in prepared.lessons]
    try:
        surfaces = _unique_by_id(draft.lesson_surfaces, "lesson_key", "lesson surface")
        _require_exact_ids(surfaces, set(expected_lesson_ids), "lesson surfaces")
        surface_ids_rebound = False
    except ValueError:
        # Surfaces contain only titles/descriptions/intros. If a provider
        # duplicates or invents one cosmetic lesson key, bind the five records
        # to the already-ordered planner shells instead of wasting the entire
        # weekly call. Scored request IDs remain strict below.
        if len(draft.lesson_surfaces) != len(expected_lesson_ids):
            raise
        surfaces = {
            lesson_id: surface.model_copy(update={"lesson_key": lesson_id})
            for lesson_id, surface in zip(
                expected_lesson_ids, draft.lesson_surfaces, strict=True
            )
        }
        surface_ids_rebound = True
    surfaces = {
        lesson["lesson_key"]: surface.model_copy(
            update={"title": _lesson_display_title(lesson)}
        )
        for lesson in prepared.lessons
        for surface in [surfaces[lesson["lesson_key"]]]
    }
    normalized_titles = [_normalize(item.title) for item in surfaces.values()]
    if len(normalized_titles) != len(set(normalized_titles)):
        raise ValueError("deterministic lesson titles must be unique within a week")
    contexts, stimuli, choices = _partition_realizations(draft, prepared)
    _require_exact_ids(contexts, set(prepared.context_requests), "context realizations")
    _require_exact_ids(
        stimuli, set(prepared.stimulus_requests), "stimulus realizations"
    )
    _require_exact_ids(choices, set(prepared.choice_requests), "choice realizations")

    constraints = prepared.lessons[0]["specification"]["cefr_realization"]
    max_sentence_words = int(constraints["maximum_sentence_words"])
    minimum_input_words = max(12, max_sentence_words)
    max_input_words = max(
        minimum_input_words,
        int(constraints["input_word_range"][1]) * 2 // 3,
    )
    seen_surface_text: set[str] = set()
    preserved_context_ids: set[str] = set()
    learner_definitions: dict[str, str] = {}
    learner_definition_origins: dict[str, str] = {}
    stimulus_texts: dict[str, str] = {}
    stimulus_prompts: dict[str, str] = {}
    stimulus_answers: dict[str, str] = {}
    choice_prompts: dict[str, str] = {}
    stimulus_distractors: dict[str, list[str]] = {}
    choice_distractors: dict[str, list[str]] = {}
    preserved_distractor_ids: set[str] = set()
    inserted_answer_evidence_ids: set[str] = set()
    extended_input_context_ids: set[str] = set()
    for request_id, request in prepared.context_requests.items():
        sentence = contexts[request_id].sentence.strip()
        sentence_word_count = len(_WORD.findall(sentence))
        normalized = _normalize(sentence)
        invalid = (
            len(_phrase_pattern(request.required_phrase).findall(sentence)) != 1
            or sentence_word_count > max_sentence_words
            or not normalized
            or normalized in seen_surface_text
            or (
                request.prototype_target is not None
                and re.search(r"\b(?:term|word)\b.*\bmeans\b", sentence, re.I)
                is not None
            )
        )
        if invalid:
            # Context requests only personalize already-reviewed examples. A
            # bad optional realization must not destroy an otherwise valid
            # five-lesson pack: retain the reviewed anchor for this activity.
            preserved_context_ids.add(request_id)
        else:
            seen_surface_text.add(normalized)
        if request.prototype_target is not None:
            target = request.prototype_target
            reviewed = reviewed_learner_gloss(
                target.title,
                target.part_of_speech,
            )
            if reviewed is not None:
                learner_definitions[request_id] = reviewed
                learner_definition_origins[request_id] = "reviewed_project_gloss"
            else:
                generated = optional_learner_definition(
                    contexts[request_id].learner_definition,
                    target=target.title,
                    source_definition=target.definition,
                    maximum_words=max(8, min(14, max_sentence_words)),
                    request_id=request_id,
                )
                learner_definitions[request_id] = (
                    generated
                    or validate_learner_definition(
                        target.definition,
                        target=target.title,
                        source_definition=target.definition,
                        maximum_words=max(8, min(14, max_sentence_words)),
                        request_id=request_id,
                    )
                )
                learner_definition_origins[request_id] = (
                    "weekly_writer_simplified" if generated else "source"
                )
        elif contexts[request_id].learner_definition.strip():
            raise ValueError(
                f"{request_id} supplied a definition for a non-vocabulary context"
            )
    for request_id, request in prepared.stimulus_requests.items():
        item = stimuli[request_id]
        prompt = _contextualize_stimulus_prompt(
            "What key detail is stated?",
            mode=request.mode,
            position=(
                _checkpoint_position(request_id)
                if request.checkpoint
                else (request.activity_index or 1)
            ),
            checkpoint=request.checkpoint,
        )
        stimulus_prompts[request_id] = prompt
        segments = _stimulus_segments(item, request_id)
        supplied_answer = " ".join(item.answer.split()).strip().rstrip(".!?").strip()
        answer = supplied_answer or request.canonical_answer
        if supplied_answer and (
            len(_WORD.findall(answer)) > max_sentence_words
            or len(_sentences(answer)) > 1
        ):
            raise ValueError(
                f"{request_id} answer must be one phrase of at most "
                f"{max_sentence_words} words"
            )
        stimulus_answers[request_id] = answer
        if any(_is_stimulus_instruction(segment) for segment in segments) or any(
            _normalize(segment) == _normalize(item.prompt) for segment in segments
        ):
            raise ValueError(
                f"{request_id} puts learner instructions inside the passage or transcript"
            )
        text = ("\n" if request.mode == "listening" else " ").join(segments)
        if supplied_answer and not _contains_phrase(text, answer):
            # The writer owns the supplied scenario fact, so making it explicit
            # is a bounded consistency repair rather than inventing
            # an answer. It also prevents an otherwise good week from failing
            # because the writer paraphrased its own short answer.
            evidence = (
                f"Speaker: {answer}."
                if request.mode == "listening"
                else f"Result: {answer}."
            )
            segments.append(evidence)
            text = ("\n" if request.mode == "listening" else " ").join(segments)
            inserted_answer_evidence_ids.add(request_id)
        stimulus_texts[request_id] = text
        effective_distractors, preserved = _writer_or_reviewed_distractors(
            item.distractors,
            request.reviewed_distractors,
            answer,
            request_id,
        )
        if any(
            _contains_phrase(text, distractor) for distractor in effective_distractors
        ):
            reviewed_distractors = list(request.reviewed_distractors)
            _validate_options(reviewed_distractors, answer, request_id)
            if any(
                _contains_phrase(text, distractor)
                for distractor in reviewed_distractors
            ):
                raise ValueError(f"{request_id} states every available distractor set")
            effective_distractors = reviewed_distractors
            preserved = True
        stimulus_distractors[request_id] = effective_distractors
        if preserved:
            preserved_distractor_ids.add(request_id)
        if not _contains_phrase(text, answer):
            raise ValueError(f"{request_id} does not state its declared answer")
        input_word_count = len(_WORD.findall(text))
        if input_word_count < minimum_input_words:
            raise ValueError(
                f"{request_id} is below the {minimum_input_words}-word input "
                f"minimum ({input_word_count} words)"
            )
        if input_word_count > max_input_words:
            raise ValueError(
                f"{request_id} exceeds the {max_input_words}-word CEFR input limit"
            )
        sentence_word_counts = [len(_WORD.findall(sentence)) for sentence in segments]
        longest_sentence = max(sentence_word_counts, default=0)
        if longest_sentence > max_sentence_words:
            raise ValueError(
                f"{request_id} contains a sentence above the CEFR sentence limit "
                f"({longest_sentence} > {max_sentence_words} words)"
            )
        _require_fresh_text(text, seen_surface_text, f"{request_id} stimulus")
        _require_fresh_text(prompt, seen_surface_text, request_id)
    for request_id, request in prepared.choice_requests.items():
        item = choices[request_id]
        # Standalone language-function choices cannot be proven from an input
        # passage. The writer may place the reviewed answer in this mission,
        # but it may not author alternatives: generated plausible distractors
        # previously created multi-answer questions even when structurally valid.
        choice_distractors[request_id] = list(request.reviewed_distractors)
        preserved_distractor_ids.add(request_id)
        prompt_text = (
            request.source_prompt
            if request.skill_id.startswith("pronunciation.")
            else item.prompt
        )
        prompt = _contextualize_choice_prompt(
            prompt_text,
            request_id,
            checkpoint=request.checkpoint,
        )
        choice_prompts[request_id] = prompt
        _require_fresh_text(prompt, seen_surface_text, request_id)

    weekly_pack_id = hashlib.sha256(
        json.dumps(
            {
                "week": prepared.lessons[0]["week_sequence"],
                "scenario": draft.scenario_title,
                "response": response_hash,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:24]
    compiled: dict[str, tuple[dict, list[str]]] = {}
    teaching_fingerprints: set[str] = set()

    for lesson in prepared.lessons[:-1]:
        lesson_key = lesson["lesson_key"]
        template = copy.deepcopy(prepared.templates[lesson_key])
        surface = surfaces[lesson_key]
        template["title"] = surface.title
        template["description"] = surface.description
        template["intro"] = surface.intro
        for request_id, request in prepared.context_requests.items():
            if request.lesson_key != lesson_key:
                continue
            if request.purpose == "prototype_vocabulary":
                continue
            if request_id in preserved_context_ids:
                continue
            assert request.activity_index is not None
            data = template["activities"][request.activity_index]["data"]
            sentence = contexts[request_id].sentence.strip()
            if request.purpose == "vocabulary_example":
                data["examples"] = [sentence]
            elif request.purpose == "concept_example":
                examples = list(data["examples"])
                if _normalize(sentence) not in {_normalize(item) for item in examples}:
                    examples.append(sentence)
                data["examples"] = examples[:6]
        for request_id, request in prepared.stimulus_requests.items():
            if request.lesson_key != lesson_key or request.checkpoint:
                continue
            activity = template["activities"][request.activity_index]
            activity["data"] = _stimulus_data(
                request=request,
                realization=stimuli[request_id],
                text=stimulus_texts[request_id],
                prompt=stimulus_prompts[request_id],
                answer=stimulus_answers[request_id],
                distractors=stimulus_distractors[request_id],
            )

        skill_id = lesson["skill_ids"][0]
        chunk = prepared.chunks_by_skill[skill_id]
        source_ids = [chunk.source_id]
        activity_source_refs = [[chunk.source_id] for _ in template["activities"]]
        target_requests = [
            (request_id, request)
            for request_id, request in prepared.context_requests.items()
            if request.lesson_key == lesson_key
            and request.purpose == "prototype_vocabulary"
        ]
        target_cards: list[tuple[dict, list[str]]] = []
        for request_id, request in target_requests:
            target = request.prototype_target
            assert target is not None
            example = (
                contexts[request_id].sentence.strip()
                if request_id not in preserved_context_ids
                else (
                    _fallback_prototype_example(
                        target,
                        maximum_words=max_sentence_words,
                    )
                )
            )
            target_refs = [
                target.source_id,
                target.definition_source_id,
                target.pronunciation_source_id,
            ]
            clean_refs = [item for item in target_refs if item]
            target_cards.append(
                (
                    _prototype_card(
                        target=target,
                        definition=learner_definitions[request_id],
                        definition_origin=learner_definition_origins[request_id],
                        example=example,
                    ),
                    clean_refs,
                )
            )
            source_ids.extend(clean_refs)
        if target_cards:
            if lesson["type"] == "vocabulary" and len(target_cards) == 2:
                activity_source_refs = _replace_vocabulary_lesson(
                    template,
                    target_cards,
                    reviewed_source_id=chunk.source_id,
                )
            else:
                template["activities"][:0] = [item[0] for item in target_cards]
                activity_source_refs[:0] = [item[1] for item in target_cards]
        source_ids = list(dict.fromkeys(source_ids))
        draft_lesson = _LessonDraft.model_validate(template)
        content = LessonGenerator._validate_and_assign(
            draft=draft_lesson,
            lesson_key=lesson_key,
            allowed_types={
                *DOMAIN_ACTIVITY_TYPES[lesson["type"]],
                "vocabulary_card",
            },
            source_ids=source_ids,
            domain=lesson["type"],
            default_skill_ids=[skill_id],
            activity_source_refs=activity_source_refs,
            activity_phases=_activity_phases(
                draft_lesson.activities,
                lesson["specification"]["lesson_role"],
            ),
        )
        teaching_fingerprints.update(
            _scored_fingerprints(content.model_dump(mode="json"))
        )
        compiled[lesson_key] = (
            _generated_payload(
                lesson=lesson,
                surface=surface,
                content=content.model_dump(mode="json"),
                chunks=[chunk],
                provider=provider,
                model=model,
                response_hash=response_hash,
                weekly_pack_id=weekly_pack_id,
                scenario_title=draft.scenario_title,
                setting=draft.setting,
                roles=draft.roles,
                generation_metadata=generation_metadata,
                preserved_context_ids=sorted(
                    request_id
                    for request_id in preserved_context_ids
                    if prepared.context_requests[request_id].lesson_key == lesson_key
                ),
                preserved_distractor_ids=sorted(
                    request_id
                    for request_id in preserved_distractor_ids
                    if (
                        (
                            request_id in prepared.stimulus_requests
                            and prepared.stimulus_requests[request_id].lesson_key
                            == lesson_key
                        )
                        or (
                            request_id in prepared.choice_requests
                            and prepared.choice_requests[request_id].lesson_key
                            == lesson_key
                        )
                    )
                ),
                inserted_answer_evidence_ids=sorted(
                    request_id
                    for request_id in inserted_answer_evidence_ids
                    if prepared.stimulus_requests[request_id].lesson_key == lesson_key
                ),
                extended_input_context_ids=sorted(
                    request_id
                    for request_id in extended_input_context_ids
                    if prepared.stimulus_requests[request_id].lesson_key == lesson_key
                ),
                surface_ids_rebound=surface_ids_rebound,
            ),
            source_ids,
        )

    checkpoint_key, checkpoint_payload = compile_checkpoint(
        prepared=prepared,
        draft=draft,
        surfaces=surfaces,
        stimuli=stimuli,
        choices=choices,
        stimulus_texts=stimulus_texts,
        stimulus_prompts=stimulus_prompts,
        stimulus_answers=stimulus_answers,
        stimulus_distractors=stimulus_distractors,
        choice_prompts=choice_prompts,
        choice_distractors=choice_distractors,
        teaching_fingerprints=teaching_fingerprints,
        provider=provider,
        model=model,
        response_hash=response_hash,
        weekly_pack_id=weekly_pack_id,
        generation_metadata=generation_metadata,
        preserved_distractor_ids=preserved_distractor_ids,
        inserted_answer_evidence_ids=inserted_answer_evidence_ids,
        extended_input_context_ids=extended_input_context_ids,
        surface_ids_rebound=surface_ids_rebound,
    )
    compiled[checkpoint_key] = checkpoint_payload
    return compiled
