"""Parsing and semantic validation helpers for weekly mission surfaces."""

from __future__ import annotations

import hashlib
import json
import re

from .weekly_mission_models import StimulusRealization, WeeklyScenarioDraft, _WORD


def _correct_option_text(question: dict) -> str:
    answer_id = question["correct_option_id"]
    try:
        return next(
            item["text"]
            for item in question["options"]
            if item["id"] == answer_id
        )
    except StopIteration as exc:
        raise ValueError(
            "a reviewed choice has no matching correct option"
        ) from exc


def _incorrect_option_texts(question: dict) -> tuple[str, str]:
    answer_id = question["correct_option_id"]
    values = tuple(
        item["text"].strip()
        for item in question["options"]
        if item["id"] != answer_id and item["text"].strip()
    )
    if len(values) < 2:
        raise ValueError("a reviewed choice needs at least two incorrect options")
    return values[0], values[1]


def _parse_weekly_draft(raw: str) -> WeeklyScenarioDraft:
    """Convert fixed-ID schema buckets into the compiler's typed records."""
    payload = json.loads(raw)
    for bucket in (
        "context_realizations",
        "stimulus_realizations",
        "choice_realizations",
    ):
        values = payload.get(bucket)
        if isinstance(values, dict):
            payload[bucket] = [
                {"request_id": request_id, **value}
                for request_id, value in values.items()
            ]
    return WeeklyScenarioDraft.model_validate(payload)


def _unique_by_id(values: list, field: str, label: str) -> dict:
    result = {}
    for value in values:
        key = getattr(value, field)
        if key in result:
            raise ValueError(f"duplicate {label} ID: {key}")
        result[key] = value
    return result


def _require_exact_ids(actual: dict, expected: set[str], label: str) -> None:
    actual_ids = set(actual)
    if actual_ids != expected:
        raise ValueError(
            f"{label} mismatch; missing={sorted(expected - actual_ids)}, "
            f"unexpected={sorted(actual_ids - expected)}"
        )


def _normalize(value: str) -> str:
    return " ".join(_WORD.findall(value.casefold().replace("’", "'")))


def _lesson_display_title(lesson: dict) -> str:
    specification = lesson["specification"]
    mission_title = specification["mission"]["title"].strip()
    topic = re.sub(
        r"^(?:make|resolve|choose|handle|coordinate|report|clarify|plan|solve|"
        r"compare|discuss|organize|explain)\s+",
        "",
        mission_title,
        flags=re.IGNORECASE,
    ).strip()
    topic = re.sub(r"\s+for a purpose$", "", topic, flags=re.IGNORECASE).strip()
    topic = re.sub(
        r"^(?:familiar|fictional|supplied|everyday)\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    ).strip()
    topic = topic or mission_title
    domain = lesson["type"]
    if domain == "assessment":
        return f"Mission check: {topic}"
    interest = specification["interest"]["label"].strip().casefold()
    templates = {
        "listening": f"Listen for details about {topic}",
        "reading": f"Read for details about {topic}",
        "pronunciation": f"Practise clear sounds for talking about {topic}",
        "vocabulary": f"Learn useful {interest} words",
        "grammar": f"Build sentences for {topic}",
        "speaking": f"Practise a conversation about {topic}",
        "discourse": f"Connect ideas about {topic}",
    }
    return templates.get(domain, f"Practise {topic}")


def _learner_definition(
    value: str,
    *,
    target: str,
    source_definition: str,
    maximum_words: int,
    request_id: str,
) -> str:
    definition = " ".join(value.split()).strip().rstrip(".;:").strip()
    words = _WORD.findall(definition)
    if len(words) < 3 or len(words) > maximum_words:
        raise ValueError(
            f"{request_id} learner definition must contain 3-{maximum_words} words"
        )
    if _contains_phrase(definition, target):
        raise ValueError(f"{request_id} learner definition is circular")
    if len(_sentences(definition)) != 1 or "\n" in definition or "\r" in definition:
        raise ValueError(f"{request_id} learner definition must be one sentence")
    if not (_meaning_tokens(definition) & _meaning_tokens(source_definition)):
        raise ValueError(
            f"{request_id} learner definition has no lexical anchor to its source meaning"
        )
    return definition


def _meaning_tokens(value: str) -> set[str]:
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "is", "it", "of", "on", "or", "that", "the", "to", "used",
        "which", "with",
    }
    result: set[str] = set()
    for token in _normalize(value).split():
        if token in stopwords or len(token) < 4:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[:-len(suffix)]
                break
        result.add(token)
    return result


def _contains_phrase(value: str, phrase: str) -> bool:
    needle = _normalize(phrase).split()
    haystack = _normalize(value).split()
    return bool(needle) and any(
        haystack[index:index + len(needle)] == needle
        for index in range(len(haystack) - len(needle) + 1)
    )


def _is_stimulus_instruction(value: str) -> bool:
    normalized = _normalize(value)
    return bool(
        re.search(
            r"\b(?:please\s+answer|answer\s+(?:this|the)\s+question|"
            r"choose\s+(?:an|the)\s+(?:answer|option)|"
            r"select\s+(?:an|the)\s+(?:answer|option))\b",
            normalized,
        )
    )


def _phrase_pattern(phrase: str) -> re.Pattern:
    parts = re.split(r"\s+", phrase.strip())
    body = r"\s+".join(re.escape(part) for part in parts)
    left = r"(?<!\w)" if phrase[:1].isalnum() else ""
    right = r"(?!\w)" if phrase[-1:].isalnum() else ""
    return re.compile(f"{left}{body}{right}", re.IGNORECASE)


def _stimulus_segments(
    realization: StimulusRealization,
    request_id: str,
) -> list[str]:
    fixed_segments = [
        realization.opening.strip(),
        realization.evidence.strip(),
        realization.closing.strip(),
    ]
    if any(fixed_segments):
        if not all(fixed_segments):
            raise ValueError(f"{request_id} has an incomplete three-part stimulus")
        if realization.sentences or realization.text.strip():
            raise ValueError(f"{request_id} mixes fixed and legacy stimulus fields")
        expanded: list[str] = []
        for item in fixed_segments:
            if "\n" in item or "\r" in item:
                raise ValueError(
                    f"{request_id} must not place line breaks inside a stimulus field"
                )
            expanded.extend(_sentences(item))
        return expanded
    if realization.sentences and realization.text.strip():
        raise ValueError(f"{request_id} mixes structured sentences with legacy text")
    if realization.sentences:
        segments = [item.strip() for item in realization.sentences]
        if any(not item for item in segments):
            raise ValueError(f"{request_id} contains an empty stimulus sentence")
        for item in segments:
            if "\n" in item or "\r" in item or len(_sentences(item)) != 1:
                raise ValueError(
                    f"{request_id} must use one complete sentence or turn per array element"
                )
        return segments
    legacy = realization.text.strip()
    if not legacy:
        raise ValueError(f"{request_id} has no stimulus sentences")
    return _sentences(legacy)


def _contextualize_stimulus_prompt(
    value: str,
    *,
    mode: str,
    position: int,
    checkpoint: bool,
) -> str:
    lead = value[:1].lower() + value[1:] if value else value
    medium = "transcript" if mode == "listening" else "passage"
    scope = "checkpoint" if checkpoint else "lesson"
    return f"In {scope} {medium} {position}, {lead}"


def _contextualize_choice_prompt(
    value: str,
    request_id: str,
    *,
    checkpoint: bool,
) -> str:
    lead = value[:1].lower() + value[1:] if value else value
    if checkpoint:
        position = _checkpoint_position(request_id)
        return f"In checkpoint situation {position}, {lead}"
    return f"For this mission, {lead}"


def _checkpoint_position(request_id: str) -> int:
    match = re.search(r":skill:(\d+)$", request_id)
    return int(match.group(1)) + 1 if match else 1


def _sentences(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", value) if item.strip()]


def _validate_options(distractors: list[str], answer: str, request_id: str) -> None:
    normalized = [_normalize(answer), *[_normalize(item) for item in distractors]]
    if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
        raise ValueError(f"{request_id} has empty or duplicate answer options")


def _writer_or_reviewed_distractors(
    proposed: list[str],
    reviewed: tuple[str, str],
    answer: str,
    request_id: str,
) -> tuple[list[str], bool]:
    try:
        _validate_options(proposed, answer, request_id)
        return proposed, False
    except ValueError:
        fallback = list(reviewed)
        # Reviewed templates are validated during ingestion and again during
        # compilation, but keep this local assertion so source corruption can
        # never be hidden by the repair path.
        _validate_options(fallback, answer, request_id)
        return fallback, True


def _require_fresh_text(value: str, seen: set[str], request_id: str) -> None:
    normalized = _normalize(value)
    if normalized in seen:
        raise ValueError(f"{request_id} duplicates another weekly realization")
    seen.add(normalized)


def _scored_fingerprints(content: dict) -> set[str]:
    result: set[str] = set()
    for activity in content["activities"]:
        data = activity["data"]
        if activity["type"] in {"reading_comprehension", "listening_comprehension"}:
            question = data["question"]
            prompt = question["prompt"]
            answer = _correct_option_text(question)
        elif activity["type"] == "multiple_choice":
            prompt = data["prompt"]
            answer = _correct_option_text(data)
        elif activity["type"] == "fill_blank":
            prompt = data["prompt"]
            answer = data["accepted_answers"][0]
        elif activity["type"] == "sentence_order":
            prompt = data["prompt"]
            by_id = {item["id"]: item["text"] for item in data["tokens"]}
            answer = " ".join(by_id[item] for item in data["correct_order"])
        else:
            continue
        result.add(
            hashlib.sha256(
                f"{_normalize(prompt)}\x1f{_normalize(answer)}".encode("utf-8")
            ).hexdigest()
        )
    return result
