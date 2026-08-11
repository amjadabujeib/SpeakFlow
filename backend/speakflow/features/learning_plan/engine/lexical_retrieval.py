from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import OLLAMA_EMBED_MODEL
from .interest_vocabulary import effective_interest_tags
from .lexical_policy import (
    is_teachable_lexical_concept,
    supports_lexical_prototype,
)
from .mission_catalog import normalize_interests
from .models import CurriculumConcept

GENERAL_CONTEXT_MIN_SEMANTIC_SCORE = 0.46


@dataclass(frozen=True)
class RetrievedConcept:
    id: str
    source_id: str
    title: str
    cefr_level: str
    part_of_speech: str | None
    topic_tags: list[str]
    definition: str = ""
    ipa: str = ""
    reference_examples: tuple[str, ...] = ()
    definition_source_id: str | None = None
    pronunciation_source_id: str | None = None
    selection_tier: str = "direct_interest"
    previously_seen: bool = False


def retrieve_lexical_palette(
    session: Session,
    *,
    cefr_level: str,
    interests: list[str],
    seed: str,
    limit: int,
    exclude_ids: set[str] | None,
    exclude_terms: set[str] | None,
    deprioritize_ids: set[str] | None,
    deprioritize_terms: set[str] | None,
    query_text: str | None,
    embed_query: Callable[[str], list[float] | None],
) -> list[RetrievedConcept]:
    """Select exact-level vocabulary from topical and safe general tiers."""
    interest_ids = list(normalize_interests(interests))
    if limit < 1:
        return []
    rows = session.scalars(
        select(CurriculumConcept).where(
            CurriculumConcept.active.is_(True),
            CurriculumConcept.concept_type == "vocabulary",
            CurriculumConcept.cefr_level == cefr_level,
            CurriculumConcept.review_status == "prototype_ready",
        )
    ).all()
    excluded = exclude_ids or set()
    normalized_excluded_terms = {
        _normalize_term(item) for item in (exclude_terms or set()) if item
    }
    deprioritized_ids = deprioritize_ids or set()
    normalized_deprioritized_terms = {
        _normalize_term(item) for item in (deprioritize_terms or set()) if item
    }
    rows = [
        item
        for item in rows
        if item.id not in excluded
        and _normalize_term(item.title) not in normalized_excluded_terms
        and supports_lexical_prototype(item.attributes.get("part_of_speech"))
        and is_teachable_lexical_concept(
            title=item.title,
            part_of_speech=item.attributes.get("part_of_speech"),
            cefr_level=item.cefr_level or cefr_level,
            source_definition=item.attributes.get("definition", ""),
            ipa=item.attributes.get("ipa", ""),
            request_id=item.id,
        )
    ]

    def interest_tags(item: CurriculumConcept) -> list[str]:
        return effective_interest_tags(
            item.topic_tags,
            cefr_level=item.cefr_level,
            title=item.title,
            part_of_speech=item.attributes.get("part_of_speech"),
        )

    exact_interest_set = set(interest_ids)
    related_interest_set: set[str] = set()
    for interest_id in interest_ids:
        related_interest_set.update(
            {
                "music": {"entertainment", "culture"},
                "history": {"culture", "education"},
            }.get(interest_id, set())
        )
    exact_candidates = [
        item for item in rows if exact_interest_set.intersection(interest_tags(item))
    ]
    related_candidates = [
        item
        for item in rows
        if not exact_interest_set.intersection(interest_tags(item))
        and related_interest_set.intersection(interest_tags(item))
    ]
    general_candidates = [item for item in rows if not interest_tags(item)]
    eligible_candidates = exact_candidates + related_candidates + general_candidates
    semantic_scores = _semantic_scores(
        session,
        candidates=eligible_candidates,
        query_text=query_text,
        embed_query=embed_query,
    )
    query_terms = set(_normalize_term(query_text or "").split())

    def relevance(item: CurriculumConcept) -> float:
        item_topics = set(interest_tags(item))
        graph_score = (
            1.0
            if exact_interest_set.intersection(item_topics)
            else 0.45
            if related_interest_set.intersection(item_topics)
            else 0.0
        )
        document_terms = set(_normalize_term(concept_retrieval_text(item)).split())
        lexical_score = len(query_terms.intersection(document_terms)) / max(
            1, len(query_terms)
        )
        frequency = int(item.attributes.get("frequency_count") or 0)
        frequency_score = min(1.0, math.log1p(frequency) / 20.0)
        return (
            0.58 * semantic_scores.get(item.id, 0.0)
            + 0.22 * graph_score
            + 0.15 * lexical_score
            + 0.05 * frequency_score
        )

    def was_seen(item: CurriculumConcept) -> bool:
        return (
            item.id in deprioritized_ids
            or _normalize_term(item.title) in normalized_deprioritized_terms
        )

    def ranked(values: list[CurriculumConcept]) -> list[CurriculumConcept]:
        if semantic_scores:
            values.sort(
                key=lambda item: (
                    was_seen(item),
                    -(relevance(item) + 0.02 * _seed_fraction(seed, item.id)),
                    item.id,
                )
            )
        else:
            values.sort(
                key=lambda item: (
                    was_seen(item),
                    len(interest_tags(item)),
                    -int(item.attributes.get("frequency_count") or 0),
                )
            )
        distinct = _distinct_terms(values)
        if semantic_scores:
            return distinct
        pool = distinct[: max(limit * 5, limit)]
        pool.sort(
            key=lambda item: (
                was_seen(item),
                hashlib.sha256(f"{seed}\x1f{item.id}".encode()).hexdigest(),
            )
        )
        return pool

    ranked_exact = ranked(exact_candidates)
    ranked_related = ranked(related_candidates)
    ranked_general = [
        item
        for item in ranked(general_candidates)
        if semantic_scores.get(item.id, 0.0) >= GENERAL_CONTEXT_MIN_SEMANTIC_SCORE
    ]
    selected = _select_tiered_candidates(
        ranked_exact=ranked_exact,
        ranked_related=ranked_related,
        ranked_general=ranked_general,
        excluded_terms=normalized_excluded_terms,
        limit=limit,
    )
    return [
        RetrievedConcept(
            id=item.id,
            source_id=item.source_id,
            title=item.title,
            cefr_level=item.cefr_level or cefr_level,
            part_of_speech=item.attributes.get("part_of_speech"),
            topic_tags=interest_tags(item),
            definition=item.attributes.get("definition", ""),
            ipa=item.attributes.get("ipa", ""),
            reference_examples=tuple(item.attributes.get("reference_examples", [])),
            definition_source_id=item.attributes.get("definition_source_id"),
            pronunciation_source_id=item.attributes.get("pronunciation_source_id"),
            selection_tier=tier,
            previously_seen=was_seen(item),
        )
        for item, tier in selected
    ]


def _semantic_scores(
    session: Session,
    *,
    candidates: list[CurriculumConcept],
    query_text: str | None,
    embed_query: Callable[[str], list[float] | None],
) -> dict[str, float]:
    if not query_text or not any(
        item.embedding is not None and item.embedding_model == OLLAMA_EMBED_MODEL
        for item in candidates
    ):
        return {}
    vector = embed_query(query_text)
    if vector is None:
        return {}
    return {
        row.id: max(0.0, 1.0 - float(row.distance))
        for row in session.execute(
            select(
                CurriculumConcept.id,
                CurriculumConcept.embedding.cosine_distance(vector).label("distance"),
            ).where(
                CurriculumConcept.id.in_([item.id for item in candidates]),
                CurriculumConcept.embedding.is_not(None),
                CurriculumConcept.embedding_model == OLLAMA_EMBED_MODEL,
            )
        )
    }


def _select_tiered_candidates(
    *,
    ranked_exact: list[CurriculumConcept],
    ranked_related: list[CurriculumConcept],
    ranked_general: list[CurriculumConcept],
    excluded_terms: set[str],
    limit: int,
) -> list[tuple[CurriculumConcept, str]]:
    topical = [*ranked_exact, *ranked_related]
    general_budget = min(len(ranked_general), limit // 2)
    topical_budget = min(len(topical), limit - general_budget)
    selected: list[tuple[CurriculumConcept, str]] = []
    seen_terms = set(excluded_terms)

    def append(candidates: list[CurriculumConcept], maximum: int, tier: str) -> None:
        for item in candidates:
            if maximum <= 0:
                break
            normalized = _normalize_term(item.title)
            if not normalized or normalized in seen_terms:
                continue
            seen_terms.add(normalized)
            selected.append((item, tier))
            maximum -= 1

    append(ranked_exact, topical_budget, "direct_interest")
    append(ranked_related, topical_budget - len(selected), "related_interest")
    append(ranked_general, general_budget, "general_context")
    for candidates, tier in (
        (ranked_exact, "direct_interest"),
        (ranked_related, "related_interest"),
        (ranked_general, "general_context"),
    ):
        append(candidates, limit - len(selected), tier)
    return selected


def _distinct_terms(values: list[CurriculumConcept]) -> list[CurriculumConcept]:
    distinct: list[CurriculumConcept] = []
    seen: set[str] = set()
    for item in values:
        normalized = _normalize_term(item.title)
        if normalized and normalized not in seen:
            seen.add(normalized)
            distinct.append(item)
    return distinct


def _seed_fraction(seed: str, item_id: str) -> float:
    return int(
        hashlib.sha256(f"{seed}\x1f{item_id}".encode()).hexdigest()[:8], 16
    ) / float(0xFFFFFFFF)


def _normalize_term(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+(?:['’][a-z0-9]+)?", value.casefold()))


def concept_retrieval_text(item: CurriculumConcept) -> str:
    attributes = item.attributes or {}
    parts = [
        f"Word: {item.title}.",
        f"Part of speech: {attributes.get('part_of_speech') or 'unknown'}.",
        f"CEFR level: {item.cefr_level or 'unknown'}.",
        f"Definition: {attributes.get('definition') or getattr(item, 'description', '') or ''}.",
        f"Source topics: {attributes.get('source_topics') or ''}.",
        f"Learning interests: {', '.join(item.topic_tags or [])}.",
    ]
    return " ".join(parts)
