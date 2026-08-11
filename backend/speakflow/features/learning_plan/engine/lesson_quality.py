from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from speakflow.features.pronunciation.domain import parse_focus_ipa
from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    LocalG2pCanonicalizer,
)

from .schemas import Activity

# The planner owns lesson order; this blueprint owns the internal learning arc.
# Exact counts make a small local writer fill purposeful slots instead of
# deciding an arbitrary mixture of activities.
ACTIVITY_BLUEPRINTS: dict[str, dict[str, tuple[int, int]]] = {
    "vocabulary": {
        "vocabulary_card": (2, 2),
        "multiple_choice": (1, 1),
        "fill_blank": (1, 1),
    },
    "grammar": {
        "concept": (1, 1),
        "multiple_choice": (1, 1),
        "fill_blank": (1, 1),
        "sentence_order": (1, 1),
    },
    "reading": {
        "concept": (1, 1),
        "reading_comprehension": (2, 3),
    },
    "listening": {
        "concept": (1, 1),
        "listening_comprehension": (2, 3),
    },
    "speaking": {
        "concept": (1, 1),
        "multiple_choice": (1, 1),
        "fill_blank": (1, 1),
        "sentence_order": (1, 1),
    },
    "pronunciation": {
        "pronunciation_drill": (2, 3),
        "multiple_choice": (1, 1),
    },
    "discourse": {
        "concept": (1, 1),
        "multiple_choice": (1, 1),
        "sentence_order": (2, 2),
    },
    "assessment": {
        "pronunciation_drill": (0, 5),
        "multiple_choice": (0, 5),
        "fill_blank": (0, 5),
        "reading_comprehension": (0, 5),
        "listening_comprehension": (0, 5),
        "sentence_order": (0, 5),
    },
}


BLUEPRINT_PURPOSES = {
    "vocabulary": [
        "Teach exactly two useful words or phrases in context.",
        "Check meaning with one unambiguous scenario choice.",
        "Finish with one contextual recall blank.",
    ],
    "grammar": [
        "Explain one form/meaning contrast with examples.",
        "Move from recognition to controlled production and sentence building.",
    ],
    "reading": [
        "Teach one reading strategy before testing it.",
        "Use three short texts with one single-answer evidence question each.",
    ],
    "listening": [
        "Teach one listening strategy before testing it.",
        "Use three short transcripts with one single-answer detail question each.",
    ],
    "speaking": [
        "Teach one reusable conversation move and model language.",
        "Practise choosing, completing, and building a useful spoken response.",
        "Never grade a personal opinion as correct or incorrect.",
    ],
    "pronunciation": [
        "Teach two related targets, then consolidate them in connected speech.",
        "Every practice item must visibly contain its target sound spelling.",
        "Finish with one objective perception or form check.",
    ],
    "discourse": [
        "Teach one linking or organization strategy.",
        "Practise choosing a connector and ordering two coherent turns.",
    ],
    "assessment": [
        "Use four or five independent tasks: current skills plus one spaced-review skill when available.",
        "Assess only reviewed target skills; do not introduce new teaching.",
    ],
}


_AMBIGUOUS_CHOICE = re.compile(
    r"\b(what do you think|in your opinion|select all|choose all|"
    r"what are some|which (?:of the following )?are|examples of|"
    r"which is best|which is your favorite)\b",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"^(optional|none|n/?a|not applicable|hint)$", re.I)
_WORD = re.compile(r"[a-z0-9']+", re.I)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "with",
}


def validate_lesson_pedagogy(activities: list[Activity], domain: str) -> None:
    if domain == "assessment":
        _validate_assessment(activities)
        return
    blueprint = ACTIVITY_BLUEPRINTS[domain]
    prototype_cards = [
        item
        for item in activities
        if item.type == "vocabulary_card"
        and (
            item.data.get("concept_id")
            or any(ref.startswith("concept:") for ref in item.source_refs)
        )
    ]
    if len(prototype_cards) > 2:
        raise ValueError(
            "a teaching lesson may introduce at most two weekly vocabulary targets"
        )
    # In the dedicated vocabulary lesson these sourced cards replace the two
    # reviewed placeholder cards and therefore are the core lesson. Elsewhere
    # they are a compact pre-teaching set outside the domain blueprint.
    core_activities = (
        activities
        if domain == "vocabulary"
        else [item for item in activities if item not in prototype_cards]
    )
    counts = Counter(item.type for item in core_activities)
    expected_types = set(blueprint)
    if set(counts) != expected_types:
        raise ValueError(
            f"{domain} lesson needs activity types {sorted(expected_types)}; "
            f"received {sorted(counts)}"
        )
    for activity_type, (minimum, maximum) in blueprint.items():
        count = counts[activity_type]
        if count < minimum or count > maximum:
            raise ValueError(
                f"{domain} requires {minimum}..{maximum} {activity_type} "
                f"activities; received {count}"
            )

    seen_prompts: set[str] = set()
    seen_practice_items: set[str] = set()
    seen_vocabulary: set[str] = set()
    for item in activities:
        data = item.data
        if item.type == "vocabulary_card":
            word = _normalize(data["word"])
            if word in seen_vocabulary:
                raise ValueError("vocabulary cards must teach different items")
            seen_vocabulary.add(word)
            _require_unique_text(data["examples"], "vocabulary examples")
            _require_unique_text(data["collocations"], "vocabulary collocations")
        elif item.type == "concept":
            _validate_concept(data)
        elif item.type == "multiple_choice":
            _validate_choice(data, domain=domain)
            _add_unique_prompt(data["prompt"], seen_prompts)
        elif item.type == "fill_blank":
            _validate_fill_blank(data)
            _add_unique_prompt(data["prompt"], seen_prompts)
        elif item.type in {"reading_comprehension", "listening_comprehension"}:
            context_key = (
                "passage" if item.type == "reading_comprehension" else "transcript"
            )
            question = data["question"]
            _validate_choice(question, domain=domain, context=data[context_key])
            _add_unique_prompt(question["prompt"], seen_prompts)
        elif item.type == "sentence_order":
            _validate_sentence_order(data)
            _add_unique_prompt(data["prompt"], seen_prompts)
        elif item.type == "pronunciation_drill":
            _validate_pronunciation(data, seen_practice_items)


def _validate_concept(data: dict) -> None:
    explanation = data["explanation"].strip()
    if explanation.endswith("?") and re.match(
        r"^(what|why|how|which|do|does|is|are|should|can)\b",
        explanation,
        re.I,
    ):
        raise ValueError("a concept explanation must teach, not ask an open question")
    _require_unique_text(data["key_points"], "concept key points")
    _require_unique_text(data["examples"], "concept examples")
    hint = data.get("native_hint")
    if hint and _PLACEHOLDER.fullmatch(hint.strip()):
        raise ValueError("native_hint must contain a useful hint or be null")


def _validate_choice(data: dict, *, domain: str, context: str | None = None) -> None:
    prompt = data["prompt"].strip()
    if _AMBIGUOUS_CHOICE.search(prompt):
        raise ValueError(
            "a single-answer question must not ask for opinions, examples, or multiple answers"
        )
    options = data["options"]
    if len(options) < 3:
        raise ValueError(
            "a multiple-choice check needs one answer and at least two distractors"
        )
    texts = [_normalize(item["text"]) for item in options]
    if len(texts) != len(set(texts)):
        raise ValueError("multiple-choice option texts must be unique")
    if any(text in {"all of the above", "none of the above"} for text in texts):
        raise ValueError("all/none-of-the-above options are not allowed")

    correct = next(
        item["text"] for item in options if item["id"] == data["correct_option_id"]
    )
    if _token_overlap(correct, data["explanation"]) < 0.5:
        raise ValueError(
            "the explanation must explicitly identify the correct response"
        )

    if domain == "speaking" and not re.search(
        r"\b(say|reply|respond|response|phrase|clarif|follow-up|conversation|ask)\b",
        f"{prompt} {data['explanation']}",
        re.I,
    ):
        raise ValueError("a speaking choice must practise a conversational response")

    if context is not None:
        correct_option = next(
            option for option in options if option["id"] == data["correct_option_id"]
        )
        if _token_overlap(correct_option["text"], context) < 0.6:
            raise ValueError("the stated correct option is not supported by the text")
        normalized_context = _normalize(context)
        repeated_distractors = [
            option["id"]
            for option in options
            if option["id"] != data["correct_option_id"]
            and _normalize(option["text"]) in normalized_context
        ]
        if repeated_distractors:
            raise ValueError(
                "reading/listening distractors must not be copied from the text"
            )


def _validate_fill_blank(data: dict) -> None:
    if not re.search(r"_{2,}|\[[^\]]+\]", data["prompt"]):
        raise ValueError("fill_blank prompt must contain one visible blank")
    answers = data["accepted_answers"]
    base_tokens = _content_tokens(answers[0])
    for answer in answers[1:]:
        tokens = _content_tokens(answer)
        same_head = bool(base_tokens and tokens and base_tokens[-1] == tokens[-1])
        if _set_similarity(set(base_tokens), set(tokens)) < 0.5 and not same_head:
            raise ValueError(
                "accepted fill-blank answers must be variants of one answer, not different ideas"
            )
    if max(_token_overlap(answer, data["explanation"]) for answer in answers) < 0.5:
        raise ValueError("fill-blank explanation must state the expected answer")


def _validate_sentence_order(data: dict) -> None:
    texts = [_normalize(item["text"]) for item in data["tokens"]]
    if len(texts) != len(set(texts)):
        raise ValueError("sentence-order token texts must be unique")
    if len(texts) < 3:
        raise ValueError("sentence-order practice needs at least three chunks")
    if [item["id"] for item in data["tokens"]] == data["correct_order"]:
        raise ValueError("sentence-order chunks must begin in a shuffled order")


def _validate_pronunciation(data: dict, seen_items: set[str]) -> None:
    items = data["practice_items"]
    _require_unique_text(items, "pronunciation practice items")
    focus = parse_focus_ipa(data["ipa"])
    if not focus:
        raise ValueError(
            "pronunciation drills require at least one assessable segmental IPA target"
        )
    ipa = data["ipa"].casefold().replace("/", "").strip()
    spelling_patterns = {
        "p": r"p",
        "b": r"b",
        "f": r"(?:f|ph)",
        "v": r"v",
        "θ": r"th",
        "ð": r"th",
    }
    pattern = spelling_patterns.get(ipa)
    if pattern:
        for practice in items:
            if not re.search(pattern, practice, re.I):
                raise ValueError(
                    f"pronunciation item {practice!r} does not contain target {data['ipa']}"
                )
    canonicalizer = _pronunciation_canonicalizer()
    for practice in items:
        pronunciation = canonicalizer.canonicalize(practice)
        present = {
            normalized
            for phone in pronunciation.ipa_phones
            for normalized in parse_focus_ipa(phone)
        }
        missing = [phone for phone in focus if phone not in present]
        if missing:
            display = ", ".join(f"/{phone}/" for phone in missing)
            raise ValueError(
                f"pronunciation item {practice!r} has no canonical occurrence of {display}"
            )
    guidance = f"{data['instructions']} {' '.join(data['tips'])}"
    if not re.search(
        r"\b(lip|tongue|teeth|throat|voice|voic|vibrat|air|breath|jaw|"
        r"stress|syllable|pitch|lengthen|shorten|rhythm)\w*\b",
        guidance,
        re.I,
    ):
        raise ValueError(
            "pronunciation guidance needs a concrete physical or prosodic cue"
        )
    for practice in items:
        normalized = _normalize(practice)
        if normalized in seen_items:
            raise ValueError("pronunciation items must not repeat across target sounds")
        seen_items.add(normalized)


@lru_cache(maxsize=1)
def _pronunciation_canonicalizer() -> LocalG2pCanonicalizer:
    return LocalG2pCanonicalizer()


def _add_unique_prompt(prompt: str, seen: set[str]) -> None:
    normalized = _normalize(prompt)
    if normalized in seen:
        raise ValueError("lesson question prompts must be unique")
    seen.add(normalized)


def _require_unique_text(values: list[str], label: str) -> None:
    normalized = [_normalize(value) for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must be unique")


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold()))


def _content_tokens(value: str) -> list[str]:
    raw = _WORD.findall(value.casefold())
    filtered = [token for token in raw if token not in _STOPWORDS]
    return filtered or raw


def _token_overlap(needle: str, haystack: str) -> float:
    needle_raw = _WORD.findall(needle.casefold())
    needle_content = [token for token in needle_raw if token not in _STOPWORDS]
    needle_tokens = set(needle_content or needle_raw)
    haystack_raw = _WORD.findall(haystack.casefold())
    haystack_tokens = set(
        [token for token in haystack_raw if token not in _STOPWORDS]
        if needle_content
        else haystack_raw
    )
    if not needle_tokens:
        return 0.0
    return len(needle_tokens & haystack_tokens) / len(needle_tokens)


def _set_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _validate_assessment(activities: list[Activity]) -> None:
    if not 2 <= len(activities) <= 5:
        raise ValueError("a checkpoint needs two to five scored activities")
    allowed = set(ACTIVITY_BLUEPRINTS["assessment"])
    if any(item.type not in allowed for item in activities):
        raise ValueError("a checkpoint may contain only objectively scored activities")
    seen_prompts: set[str] = set()
    seen_practice_items: set[str] = set()
    for item in activities:
        data = item.data
        if item.type == "pronunciation_drill":
            _validate_pronunciation(data, seen_practice_items)
        elif item.type == "multiple_choice":
            _validate_choice(data, domain="assessment")
            _add_unique_prompt(data["prompt"], seen_prompts)
        elif item.type == "fill_blank":
            _validate_fill_blank(data)
            _add_unique_prompt(data["prompt"], seen_prompts)
        elif item.type in {"reading_comprehension", "listening_comprehension"}:
            context_key = (
                "passage" if item.type == "reading_comprehension" else "transcript"
            )
            question = data["question"]
            _validate_choice(question, domain="assessment", context=data[context_key])
            _add_unique_prompt(question["prompt"], seen_prompts)
        else:
            _validate_sentence_order(data)
            _add_unique_prompt(data["prompt"], seen_prompts)
