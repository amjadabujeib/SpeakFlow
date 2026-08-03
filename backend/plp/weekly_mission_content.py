"""Lesson-content assembly helpers for weekly mission compilation."""

from __future__ import annotations

import hashlib
import re

from .curated_lessons import SCORED_TYPES, assessment_candidates
from .generator import _DraftActivity
from .learner_glosses import reviewed_learner_gloss
from .retrieval import RetrievedConcept
from .weekly_mission_models import (
    ChoiceRealization,
    ContextRealization,
    PreparedWeek,
    StimulusRealization,
    StimulusRequest,
    WeeklyScenarioDraft,
    _WORD,
)
from .weekly_mission_validation import (
    _correct_option_text,
    _normalize,
    _phrase_pattern,
    _require_exact_ids,
    _unique_by_id,
)


def _activity_phases(activities: list[_DraftActivity], role: str) -> list[str]:
    scored_indexes = [
        index for index, item in enumerate(activities) if item.type in SCORED_TYPES
    ]
    phases: list[str] = []
    for index, item in enumerate(activities):
        if item.type not in SCORED_TYPES:
            phases.append("learn")
        elif role == "independent_transfer":
            phases.append("independent_check")
        elif scored_indexes and index == scored_indexes[-1]:
            phases.append("independent_check")
        else:
            phases.append("guided_practice")
    return phases


def _prototype_card(
    *,
    target: RetrievedConcept,
    definition: str,
    example: str,
) -> dict:
    return {
        "type": "vocabulary_card",
        "data": {
            "concept_id": target.id,
            "word": target.title,
            "part_of_speech": target.part_of_speech or "word",
            "ipa": target.ipa,
            "definition": definition,
            "source_definition": target.definition,
            "definition_origin": (
                "reviewed_project_gloss"
                if reviewed_learner_gloss(target.title, target.part_of_speech) is not None
                else "weekly_writer_simplified"
            ),
            "examples": [example],
            "collocations": [],
            "native_hint": None,
        },
    }


def _fallback_prototype_example(
    target: RetrievedConcept,
    *,
    maximum_words: int,
) -> str:
    for example in target.reference_examples:
        cleaned = " ".join(example.split()).strip()
        if (
            len(_phrase_pattern(target.title).findall(cleaned)) == 1
            and len(_WORD.findall(cleaned)) <= maximum_words
            and re.search(r"\b(?:term|word)\b.*\bmeans\b", cleaned, re.I) is None
        ):
            return cleaned.rstrip(".") + "."
    part_of_speech = (target.part_of_speech or "").casefold()
    if part_of_speech.startswith("verb"):
        return f"The group will {target.title} the new information."
    if part_of_speech.startswith("adjective"):
        return f"The selected option is {target.title} today."
    if part_of_speech.startswith("adverb"):
        return f"The group works {target.title} during the task."
    return f"The group discusses the {target.title} during the task."


def _replace_vocabulary_lesson(
    template: dict,
    target_cards: list[tuple[dict, list[str]]],
    *,
    reviewed_source_id: str,
) -> list[list[str]]:
    """Make the sourced weekly lexical set the vocabulary lesson's real content."""
    if len(target_cards) != 2:
        raise ValueError("a sourced vocabulary replacement needs exactly two targets")
    card_indexes = [
        index for index, item in enumerate(template["activities"])
        if item["type"] == "vocabulary_card"
    ]
    choice_indexes = [
        index for index, item in enumerate(template["activities"])
        if item["type"] == "multiple_choice"
    ]
    fill_indexes = [
        index for index, item in enumerate(template["activities"])
        if item["type"] == "fill_blank"
    ]
    if len(card_indexes) != 2 or len(choice_indexes) != 1 or len(fill_indexes) != 1:
        raise ValueError("reviewed vocabulary template does not match its blueprint")

    source_refs = [[reviewed_source_id] for _ in template["activities"]]
    for index, (card, refs) in zip(card_indexes, target_cards, strict=True):
        template["activities"][index] = card
        source_refs[index] = list(refs)

    first_card, first_refs = target_cards[0]
    second_card, second_refs = target_cards[1]
    first = first_card["data"]
    second = second_card["data"]
    original_choice = template["activities"][choice_indexes[0]]["data"]
    candidates = [
        second["word"],
        *[
            option["text"]
            for option in original_choice["options"]
            if option["id"] != original_choice["correct_option_id"]
        ],
    ]
    distractors: list[str] = []
    seen = {_normalize(first["word"])}
    for value in candidates:
        normalized = _normalize(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            distractors.append(value)
        if len(distractors) == 2:
            break
    if len(distractors) != 2:
        raise ValueError("vocabulary replacement could not build distinct reviewed options")
    template["activities"][choice_indexes[0]]["data"] = _choice_data(
        seed=f"prototype:{first['concept_id']}",
        prompt=f"Which word means ‘{first['definition']}’?",
        canonical_answer=first["word"],
        distractors=distractors,
        explanation=f"{first['word']} means {first['definition']}.",
    )
    source_refs[choice_indexes[0]] = list(
        dict.fromkeys([*first_refs, *second_refs, reviewed_source_id])
    )

    example = second["examples"][0]
    blanked, replacements = _phrase_pattern(second["word"]).subn("___", example)
    if replacements != 1:
        raise ValueError("prototype vocabulary example cannot form one recall blank")
    template["activities"][fill_indexes[0]]["data"] = {
        "prompt": blanked,
        "accepted_answers": [second["word"]],
        "explanation": f"The missing word is {second['word']}. It means {second['definition']}.",
    }
    source_refs[fill_indexes[0]] = list(
        dict.fromkeys([*second_refs, reviewed_source_id])
    )
    return source_refs


def _stimulus_data(
    *,
    request: StimulusRequest,
    realization: StimulusRealization,
    text: str,
    prompt: str,
    answer: str,
    distractors: list[str],
) -> dict:
    question = _choice_data(
        seed=request.request_id,
        prompt=prompt,
        canonical_answer=answer,
        distractors=distractors,
        explanation=realization.explanation,
    )
    if request.mode == "reading":
        return {
            "title": realization.title,
            "passage": text,
            "question": question,
            "native_hint": None,
        }
    return {
        "title": realization.title,
        "transcript": text,
        "question": question,
        "voice": "american",
    }


def _choice_data(
    *,
    seed: str,
    prompt: str,
    canonical_answer: str,
    distractors: list[str],
    explanation: str,
) -> dict:
    values = [(canonical_answer, True), *[(item, False) for item in distractors]]
    values.sort(
        key=lambda pair: hashlib.sha256(
            f"{seed}\x1f{pair[0]}".encode("utf-8")
        ).hexdigest()
    )
    options = [
        {"id": f"option_{index + 1}", "text": text}
        for index, (text, _) in enumerate(values)
    ]
    correct_index = next(index for index, (_, correct) in enumerate(values) if correct)
    return {
        "prompt": prompt,
        "options": options,
        "correct_option_id": options[correct_index]["id"],
        "explanation": f"The correct response is {canonical_answer}. {explanation}",
    }


def _first_canonical_answer(template: dict) -> str | None:
    for item in assessment_candidates(template):
        if item["type"] == "fill_blank":
            return item["data"]["accepted_answers"][0]
    for item in assessment_candidates(template):
        if item["type"] == "multiple_choice":
            return _correct_option_text(item["data"])
    return None


def _partition_realizations(
    draft: WeeklyScenarioDraft,
    prepared: PreparedWeek,
) -> tuple[dict[str, ContextRealization], dict[str, StimulusRealization], dict[str, ChoiceRealization]]:
    if not draft.realizations:
        return (
            _unique_by_id(draft.context_realizations, "request_id", "context"),
            _unique_by_id(draft.stimulus_realizations, "request_id", "stimulus"),
            _unique_by_id(draft.choice_realizations, "request_id", "choice"),
        )
    if draft.context_realizations or draft.stimulus_realizations or draft.choice_realizations:
        raise ValueError("weekly output must not mix flat and legacy realization records")
    flat = _unique_by_id(draft.realizations, "request_id", "realization")
    expected = {
        *prepared.context_requests,
        *prepared.stimulus_requests,
        *prepared.choice_requests,
    }
    _require_exact_ids(flat, expected, "realizations")
    contexts: dict[str, ContextRealization] = {}
    stimuli: dict[str, StimulusRealization] = {}
    choices: dict[str, ChoiceRealization] = {}
    for request_id, item in flat.items():
        if request_id in prepared.context_requests:
            if item.kind != "context":
                raise ValueError(f"{request_id} must have kind=context")
            if any((item.title, item.text, item.prompt, item.explanation)) or item.distractors:
                raise ValueError(f"{request_id} has non-empty fields unused by a context")
            contexts[request_id] = ContextRealization(
                request_id=request_id,
                sentence=item.sentence,
                learner_definition=item.learner_definition,
            )
        elif request_id in prepared.stimulus_requests:
            if item.kind != "stimulus":
                raise ValueError(f"{request_id} must have kind=stimulus")
            if item.sentence:
                raise ValueError(f"{request_id} has a sentence field unused by a stimulus")
            stimuli[request_id] = StimulusRealization(
                request_id=request_id,
                title=item.title,
                text=item.text,
                prompt=item.prompt,
                answer=item.answer,
                distractors=item.distractors,
                explanation=item.explanation,
            )
        else:
            if item.kind != "choice":
                raise ValueError(f"{request_id} must have kind=choice")
            if any((item.sentence, item.title, item.text)):
                raise ValueError(f"{request_id} has non-empty fields unused by a choice")
            choices[request_id] = ChoiceRealization(
                request_id=request_id,
                prompt=item.prompt,
                distractors=item.distractors,
                explanation=item.explanation,
            )
    return contexts, stimuli, choices
