from __future__ import annotations

import argparse
import hashlib
import json

from sqlalchemy import delete

from .config import OLLAMA_EMBED_MODEL
from .database import get_engine, session_scope
from .models import (
    CurriculumChunk,
    CurriculumSource,
    Skill,
    SkillPrerequisite,
)
from .retrieval import CurriculumRetriever
from .seed import seed_records


def ingest_reviewed_seed() -> dict:
    source_data, skills, chunks = seed_records()
    _validate_skill_graph(skills)
    retriever = CurriculumRetriever()
    try:
        embeddings = retriever.embed([item["content"] for item in chunks])
        inserted = updated = unchanged = 0
        with session_scope() as session:
            source = session.get(CurriculumSource, source_data["id"])
            if source is None:
                source = CurriculumSource(**source_data)
                session.add(source)
            else:
                for key, value in source_data.items():
                    setattr(source, key, value)
            for item in skills:
                skill = session.get(Skill, item["id"])
                values = {
                    "domain": item["domain"],
                    "cefr_level": item["cefr_level"],
                    "title": item["title"],
                    "description": item["description"],
                    "outcomes": item["outcomes"],
                    "l1_tags": item["l1_tags"],
                    "active": True,
                }
                if skill is None:
                    session.add(Skill(id=item["id"], **values))
                else:
                    for key, value in values.items():
                        setattr(skill, key, value)
            session.flush()
            seeded_ids = [item["id"] for item in skills]
            session.execute(
                delete(SkillPrerequisite).where(
                    SkillPrerequisite.skill_id.in_(seeded_ids)
                )
            )
            for item in skills:
                for prerequisite in item["prerequisites"]:
                    session.add(
                        SkillPrerequisite(
                            skill_id=item["id"], prerequisite_skill_id=prerequisite
                        )
                    )
            for item, embedding in zip(chunks, embeddings, strict=True):
                # The reviewed teaching payload lives partly in JSON metadata.
                # Hash the whole durable object so answer-key/template edits are
                # not skipped merely because the search text stayed the same.
                content_hash = hashlib.sha256(
                    json.dumps(
                        {
                            "content": item["content"],
                            "metadata": item["metadata"],
                            "review_status": item["review_status"],
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                existing = session.get(CurriculumChunk, item["id"])
                if (
                    existing is not None
                    and existing.content_hash == content_hash
                    and existing.embedding_model == OLLAMA_EMBED_MODEL
                ):
                    unchanged += 1
                    continue
                values = {
                    "source_id": item["source_id"],
                    "object_type": item["object_type"],
                    "content": item["content"],
                    "metadata_json": item["metadata"],
                    "review_status": item["review_status"],
                    "content_hash": content_hash,
                    "embedding_model": OLLAMA_EMBED_MODEL,
                    "embedding": embedding,
                }
                if existing is None:
                    session.add(CurriculumChunk(id=item["id"], **values))
                    inserted += 1
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    updated += 1
    finally:
        retriever.close()
    return {
        "source": source_data["id"],
        "skills": len(skills),
        "chunks": len(chunks),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "embedding_model": OLLAMA_EMBED_MODEL,
    }


def _validate_skill_graph(skills: list[dict]) -> None:
    by_id = {item["id"]: item for item in skills}
    if len(by_id) != len(skills):
        raise ValueError("duplicate skill IDs")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(skill_id: str) -> None:
        if skill_id in visiting:
            raise ValueError(f"skill prerequisite cycle at {skill_id}")
        if skill_id in visited:
            return
        visiting.add(skill_id)
        for prerequisite in by_id[skill_id]["prerequisites"]:
            if prerequisite not in by_id:
                raise ValueError(f"unknown prerequisite {prerequisite}")
            visit(prerequisite)
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in by_id:
        visit(skill_id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest the reviewed A1–B2 curriculum seed into PostgreSQL."
    )
    parser.parse_args()
    try:
        print(json.dumps(ingest_reviewed_seed(), indent=2))
    finally:
        get_engine().dispose()


if __name__ == "__main__":
    main()
