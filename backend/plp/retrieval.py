from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from ollama import Client
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import EMBEDDING_DIMENSIONS, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from .mission_catalog import normalize_interests
from .models import CurriculumChunk, CurriculumConcept


class RetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    source_id: str
    content: str
    metadata: dict
    score: float
    content_hash: str | None = None


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


class CurriculumRetriever:
    def __init__(self, client: Client | None = None):
        self.client = client or Client(host=OLLAMA_BASE_URL)

    def embed(
        self, texts: list[str], *, keep_alive: int | str = 0
    ) -> list[list[float]]:
        try:
            response = self.client.embed(
                model=OLLAMA_EMBED_MODEL,
                input=texts,
                keep_alive=keep_alive,
            )
            embeddings = response["embeddings"]
        except Exception as exc:
            raise RetrievalError(f"local embedding model is unavailable: {exc}") from exc
        if len(embeddings) != len(texts):
            raise RetrievalError("embedding response count does not match input count")
        for embedding in embeddings:
            if len(embedding) != EMBEDDING_DIMENSIONS:
                raise RetrievalError(
                    f"{OLLAMA_EMBED_MODEL} returned {len(embedding)} values; expected {EMBEDDING_DIMENSIONS}"
                )
        return [list(map(float, embedding)) for embedding in embeddings]

    def backfill_concept_embeddings(
        self,
        session: Session,
        *,
        batch_size: int = 256,
    ) -> dict:
        rows = session.scalars(
            select(CurriculumConcept)
            .where(
                CurriculumConcept.active.is_(True),
                CurriculumConcept.concept_type == "vocabulary",
                CurriculumConcept.review_status == "prototype_ready",
                or_(
                    CurriculumConcept.embedding.is_(None),
                    CurriculumConcept.embedding_model != OLLAMA_EMBED_MODEL,
                ),
            )
            .order_by(CurriculumConcept.id)
        ).all()
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            vectors = self.embed(
                [_concept_retrieval_text(item) for item in batch],
                keep_alive="5m",
            )
            for item, vector in zip(batch, vectors, strict=True):
                item.embedding = vector
                item.embedding_model = OLLAMA_EMBED_MODEL
            session.flush()
        return {
            "embedded": len(rows),
            "embedding_model": OLLAMA_EMBED_MODEL,
        }

    def close(self) -> None:
        transport = getattr(self.client, "_client", None)
        if transport is not None:
            transport.close()

    def retrieve(
        self,
        session: Session,
        *,
        query: str,
        cefr_level: str,
        skill_ids: list[str],
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        vector = self.embed([query])[0]
        # Hard filters are applied before rank fusion. Exact cosine search is
        # deliberate for the small reviewed corpus.
        candidates = session.execute(
            select(CurriculumChunk).where(
                CurriculumChunk.review_status == "reviewed",
                CurriculumChunk.metadata_json["cefr"].contains([cefr_level]),
                or_(
                    *[
                        CurriculumChunk.metadata_json["skill_ids"].contains([skill_id])
                        for skill_id in skill_ids
                    ]
                ),
            )
        ).scalars().all()
        if not candidates:
            raise RetrievalError(
                f"no reviewed curriculum matches {cefr_level} and {skill_ids}"
            )

        ids = [item.id for item in candidates]
        semantic = session.execute(
            select(
                CurriculumChunk.id,
                CurriculumChunk.embedding.cosine_distance(vector).label("distance"),
            )
            .where(CurriculumChunk.id.in_(ids))
            .order_by("distance")
        ).all()
        lexical = session.execute(
            select(
                CurriculumChunk.id,
                func.ts_rank_cd(
                    CurriculumChunk.search_vector,
                    func.plainto_tsquery("english", query),
                ).label("rank"),
            )
            .where(CurriculumChunk.id.in_(ids))
            .order_by(func.ts_rank_cd(
                CurriculumChunk.search_vector,
                func.plainto_tsquery("english", query),
            ).desc())
        ).all()
        semantic_rank = {row.id: index + 1 for index, row in enumerate(semantic)}
        lexical_rank = {row.id: index + 1 for index, row in enumerate(lexical)}
        by_id = {item.id: item for item in candidates}
        merged = sorted(
            ids,
            key=lambda item_id: -(
                1 / (60 + semantic_rank[item_id]) +
                1 / (60 + lexical_rank[item_id])
            ),
        )[:limit]
        return [
            RetrievedChunk(
                id=item_id,
                source_id=by_id[item_id].source_id,
                content=by_id[item_id].content,
                metadata=by_id[item_id].metadata_json,
                score=1 / (60 + semantic_rank[item_id]) + 1 / (60 + lexical_rank[item_id]),
                content_hash=by_id[item_id].content_hash,
            )
            for item_id in merged
        ]

    def retrieve_exact(
        self,
        session: Session,
        *,
        cefr_level: str,
        skill_ids: list[str],
    ) -> list[RetrievedChunk]:
        """Fetch mandatory reviewed curriculum without starting an embed model.

        Weekly mission compilation already knows the exact skills selected by
        the deterministic planner. Vector search cannot improve that decision;
        it only wastes memory and startup time when the reviewed bank contains
        one canonical object per skill.
        """
        if not skill_ids:
            raise RetrievalError("exact curriculum retrieval requires skill IDs")
        rows = session.execute(
            select(CurriculumChunk).where(
                CurriculumChunk.review_status == "reviewed",
                CurriculumChunk.metadata_json["cefr"].contains([cefr_level]),
                or_(
                    *[
                        CurriculumChunk.metadata_json["skill_ids"].contains([skill_id])
                        for skill_id in skill_ids
                    ]
                ),
            )
        ).scalars().all()
        by_skill: dict[str, list[CurriculumChunk]] = {item: [] for item in skill_ids}
        for row in rows:
            for skill_id in row.metadata_json.get("skill_ids", []):
                if skill_id in by_skill:
                    by_skill[skill_id].append(row)
        missing = [skill_id for skill_id, values in by_skill.items() if not values]
        if missing:
            raise RetrievalError(
                f"no reviewed curriculum matches {cefr_level} and {missing}"
            )
        # Stable ordering is part of the writer/compiler cache contract.
        selected = sorted({row.id: row for row in rows}.values(), key=lambda row: row.id)
        return [
            RetrievedChunk(
                id=row.id,
                source_id=row.source_id,
                content=row.content,
                metadata=row.metadata_json,
                score=1.0,
                content_hash=row.content_hash,
            )
            for row in selected
        ]

    def retrieve_lexical_palette(
        self,
        session: Session,
        *,
        cefr_level: str,
        interests: list[str],
        seed: str,
        limit: int = 12,
        exclude_ids: set[str] | None = None,
        exclude_terms: set[str] | None = None,
        query_text: str | None = None,
    ) -> list[RetrievedConcept]:
        """Select distinct, interest-grounded vocabulary at the exact CEFR level.

        A sparse interest is allowed to return fewer than ``limit`` records.  A
        decorative but unrelated fallback is worse than teaching fewer useful
        words, and duplicate source senses must never surface as repeated
        learner-facing headwords.
        """
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
        excluded_terms = {
            _normalize_term(item) for item in (exclude_terms or set()) if item
        }
        rows = [
            item for item in rows
            if item.id not in excluded
            and _normalize_term(item.title) not in excluded_terms
        ]
        exact_interest_set = set(interest_ids)
        related_interest_set: set[str] = set()
        for interest_id in interest_ids:
            related_interest_set.update({
                "music": {"entertainment", "culture"},
                "history": {"culture", "education"},
            }.get(interest_id, set()))
        preferred = [
            item
            for item in rows
            if exact_interest_set.intersection(item.topic_tags)
            or related_interest_set.intersection(item.topic_tags)
        ]

        semantic_scores: dict[str, float] = {}
        if query_text and any(
            item.embedding is not None
            and item.embedding_model == OLLAMA_EMBED_MODEL
            for item in rows
        ):
            try:
                vector = self.embed([query_text])[0]
                semantic_scores = {
                    row.id: max(0.0, 1.0 - float(row.distance))
                    for row in session.execute(
                        select(
                            CurriculumConcept.id,
                            CurriculumConcept.embedding.cosine_distance(
                                vector
                            ).label("distance"),
                        ).where(
                            CurriculumConcept.id.in_([item.id for item in rows]),
                            CurriculumConcept.embedding.is_not(None),
                            CurriculumConcept.embedding_model
                            == OLLAMA_EMBED_MODEL,
                        )
                    )
                }
            except RetrievalError:
                # Exact reviewed metadata remains a safe degraded path if the
                # small local embedding service is temporarily unavailable.
                semantic_scores = {}

        query_terms = set(_normalize_term(query_text or "").split())

        def relevance(item: CurriculumConcept) -> float:
            item_topics = set(item.topic_tags)
            graph_score = (
                1.0
                if exact_interest_set.intersection(item_topics)
                else 0.45
                if related_interest_set.intersection(item_topics)
                else 0.0
            )
            document_terms = set(
                _normalize_term(_concept_retrieval_text(item)).split()
            )
            lexical_score = (
                len(query_terms.intersection(document_terms))
                / max(1, len(query_terms))
            )
            frequency = int(item.attributes.get("frequency_count") or 0)
            frequency_score = min(1.0, math.log1p(frequency) / 20.0)
            return (
                0.58 * semantic_scores.get(item.id, 0.0)
                + 0.22 * graph_score
                + 0.15 * lexical_score
                + 0.05 * frequency_score
            )

        def ranked(values: list[CurriculumConcept]) -> list[CurriculumConcept]:
            if semantic_scores:
                values.sort(
                    key=lambda item: (
                        -(
                            relevance(item)
                            + 0.02
                            * (
                                int(
                                    hashlib.sha256(
                                        f"{seed}\x1f{item.id}".encode()
                                    ).hexdigest()[:8],
                                    16,
                                )
                                / 0xFFFFFFFF
                            )
                        ),
                        item.id,
                    )
                )
            else:
                values.sort(
                    key=lambda item: (
                        len(item.topic_tags),
                        -int(item.attributes.get("frequency_count") or 0),
                    )
                )
            distinct: list[CurriculumConcept] = []
            distinct_terms: set[str] = set()
            for item in values:
                normalized = _normalize_term(item.title)
                if not normalized or normalized in distinct_terms:
                    continue
                distinct_terms.add(normalized)
                distinct.append(item)
            if semantic_scores:
                return distinct
            pool = distinct[: max(limit * 5, limit)]
            pool.sort(
                key=lambda item: hashlib.sha256(
                    f"{seed}\x1f{item.id}".encode()
                ).hexdigest()
            )
            return pool

        selected: list[CurriculumConcept] = []
        seen_terms: set[str] = set(excluded_terms)
        candidate_rows = rows if semantic_scores else preferred
        for item in ranked(candidate_rows):
            normalized = _normalize_term(item.title)
            if not normalized or normalized in seen_terms:
                continue
            seen_terms.add(normalized)
            selected.append(item)
            if len(selected) == limit:
                break
        return [
            RetrievedConcept(
                id=item.id,
                source_id=item.source_id,
                title=item.title,
                cefr_level=item.cefr_level or cefr_level,
                part_of_speech=item.attributes.get("part_of_speech"),
                topic_tags=list(item.topic_tags),
                definition=item.attributes.get("definition", ""),
                ipa=item.attributes.get("ipa", ""),
                reference_examples=tuple(
                    item.attributes.get("reference_examples", [])
                ),
                definition_source_id=item.attributes.get("definition_source_id"),
                pronunciation_source_id=item.attributes.get(
                    "pronunciation_source_id"
                ),
            )
            for item in selected
        ]


def _normalize_term(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+(?:['’][a-z0-9]+)?", value.casefold()))


def _concept_retrieval_text(item: CurriculumConcept) -> str:
    attributes = item.attributes or {}
    parts = [
        f"Word: {item.title}.",
        f"Part of speech: {attributes.get('part_of_speech') or 'unknown'}.",
        f"CEFR level: {item.cefr_level or 'unknown'}.",
        f"Definition: {attributes.get('definition') or item.description or ''}.",
        f"Source topics: {attributes.get('source_topics') or ''}.",
        f"Learning interests: {', '.join(item.topic_tags or [])}.",
    ]
    return " ".join(parts)
