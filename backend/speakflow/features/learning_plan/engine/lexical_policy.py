"""Runtime eligibility policy for source-attributed vocabulary concepts."""

from __future__ import annotations

from dataclasses import dataclass

from .learner_glosses import reviewed_learner_gloss
from .lexical_definition_policy import optional_learner_definition
from .mission_catalog import CEFR_CONSTRAINT_BY_LEVEL

SUPPORTED_LEXICAL_PARTS_OF_SPEECH = frozenset({"noun", "verb", "adjective", "adverb"})


@dataclass(frozen=True, slots=True)
class LearnerDefinition:
    text: str
    origin: str


def normalized_part_of_speech(value: str | None) -> str:
    return (value or "").casefold().strip()


def supports_lexical_prototype(value: str | None) -> bool:
    """Return whether WordNet can safely honor the source part of speech."""

    return normalized_part_of_speech(value) in SUPPORTED_LEXICAL_PARTS_OF_SPEECH


def definition_word_limit(cefr_level: str) -> int:
    constraint = CEFR_CONSTRAINT_BY_LEVEL.get(cefr_level)
    if constraint is None:
        return 0
    return max(8, min(14, constraint.maximum_sentence_words))


def resolve_learner_definition(
    *,
    title: str,
    part_of_speech: str | None,
    cefr_level: str,
    source_definition: str,
    request_id: str,
) -> LearnerDefinition | None:
    """Resolve a reviewed gloss or validate a source definition for display."""

    if not supports_lexical_prototype(part_of_speech) or not source_definition:
        return None
    gloss = reviewed_learner_gloss(title, part_of_speech)
    if gloss is not None:
        return LearnerDefinition(gloss, "reviewed_project_gloss")
    maximum_words = definition_word_limit(cefr_level)
    if maximum_words == 0:
        return None
    validated = optional_learner_definition(
        source_definition,
        target=title,
        source_definition=source_definition,
        maximum_words=maximum_words,
        request_id=request_id,
    )
    if validated is None:
        return None
    return LearnerDefinition(validated, "lexical_source")


def is_teachable_lexical_concept(
    *,
    title: str,
    part_of_speech: str | None,
    cefr_level: str,
    source_definition: str,
    ipa: str,
    request_id: str,
) -> bool:
    return bool(
        ipa
        and resolve_learner_definition(
            title=title,
            part_of_speech=part_of_speech,
            cefr_level=cefr_level,
            source_definition=source_definition,
            request_id=request_id,
        )
        is not None
    )
