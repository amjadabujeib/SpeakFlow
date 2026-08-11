from __future__ import annotations

from dataclasses import dataclass

from ollama import Client
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import (
    EMBEDDING_DIMENSIONS,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_EMBED_TIMEOUT_SECONDS,
)
from .lexical_retrieval import (
    RetrievedConcept,
    concept_retrieval_text,
    retrieve_lexical_palette,
)
from .models import CurriculumChunk, CurriculumConcept


class RetrievalError(RuntimeError):
    pass


WEEKLY_LEXICAL_CANDIDATE_LIMIT = 24


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    source_id: str
    content: str
    metadata: dict
    score: float
    content_hash: str | None = None


class CurriculumRetriever:
    def __init__(self, client: Client | None = None):
        self.client = client or Client(
            host=OLLAMA_BASE_URL,
            timeout=OLLAMA_EMBED_TIMEOUT_SECONDS,
        )

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
            raise RetrievalError(
                f"local embedding model is unavailable: {exc}"
            ) from exc
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
                [concept_retrieval_text(item) for item in batch],
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
        candidates = (
            session.execute(
                select(CurriculumChunk).where(
                    CurriculumChunk.review_status == "reviewed",
                    CurriculumChunk.metadata_json["cefr"].contains([cefr_level]),
                    or_(
                        *[
                            CurriculumChunk.metadata_json["skill_ids"].contains(
                                [skill_id]
                            )
                            for skill_id in skill_ids
                        ]
                    ),
                )
            )
            .scalars()
            .all()
        )
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
            .order_by(
                func.ts_rank_cd(
                    CurriculumChunk.search_vector,
                    func.plainto_tsquery("english", query),
                ).desc()
            )
        ).all()
        semantic_rank = {row.id: index + 1 for index, row in enumerate(semantic)}
        lexical_rank = {row.id: index + 1 for index, row in enumerate(lexical)}
        by_id = {item.id: item for item in candidates}
        merged = sorted(
            ids,
            key=lambda item_id: (
                -(1 / (60 + semantic_rank[item_id]) + 1 / (60 + lexical_rank[item_id]))
            ),
        )[:limit]
        return [
            RetrievedChunk(
                id=item_id,
                source_id=by_id[item_id].source_id,
                content=by_id[item_id].content,
                metadata=by_id[item_id].metadata_json,
                score=1 / (60 + semantic_rank[item_id])
                + 1 / (60 + lexical_rank[item_id]),
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
        rows = (
            session.execute(
                select(CurriculumChunk).where(
                    CurriculumChunk.review_status == "reviewed",
                    CurriculumChunk.metadata_json["cefr"].contains([cefr_level]),
                    or_(
                        *[
                            CurriculumChunk.metadata_json["skill_ids"].contains(
                                [skill_id]
                            )
                            for skill_id in skill_ids
                        ]
                    ),
                )
            )
            .scalars()
            .all()
        )
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
        selected = sorted(
            {row.id: row for row in rows}.values(), key=lambda row: row.id
        )
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
        deprioritize_ids: set[str] | None = None,
        deprioritize_terms: set[str] | None = None,
        query_text: str | None = None,
    ) -> list[RetrievedConcept]:
        """Select distinct, interest-grounded vocabulary at the exact CEFR level.

        A sparse interest is allowed to return fewer than ``limit`` records.  A
        decorative but unrelated fallback is worse than teaching fewer useful
        words, and duplicate source senses must never surface as repeated
        learner-facing headwords.
        """

        def embed_query(text: str) -> list[float] | None:
            try:
                return self.embed([text])[0]
            except RetrievalError:
                # Reviewed metadata remains a safe degraded path while the
                # local embedding service is temporarily unavailable.
                return None

        return retrieve_lexical_palette(
            session,
            cefr_level=cefr_level,
            interests=interests,
            seed=seed,
            limit=limit,
            exclude_ids=exclude_ids,
            exclude_terms=exclude_terms,
            deprioritize_ids=deprioritize_ids,
            deprioritize_terms=deprioritize_terms,
            query_text=query_text,
            embed_query=embed_query,
        )
