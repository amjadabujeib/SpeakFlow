"""Database import and CLI operations for curriculum snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .curriculum_snapshot import (
    SNAPSHOT_PATH,
    CurriculumSnapshot,
    export_snapshot,
    read_snapshot,
)
from .database import get_engine, session_scope
from .models import CurriculumConcept, CurriculumSource, utc_now


def _upsert_snapshot(session: Session, snapshot: CurriculumSnapshot) -> dict[str, Any]:
    for record in snapshot.sources:
        source_id = str(record["id"])
        source = session.get(CurriculumSource, source_id)
        values = {
            key: record[key]
            for key in (
                "title",
                "author",
                "locator",
                "license",
                "version",
                "checksum",
            )
        }
        if source is None:
            session.add(CurriculumSource(id=source_id, **values))
        else:
            for key, value in values.items():
                setattr(source, key, value)
    session.flush()

    snapshot_ids = {str(record["id"]) for record in snapshot.concepts}
    concept_source_ids = {str(record["source_id"]) for record in snapshot.concepts}
    existing = {
        item.id: item
        for item in session.scalars(
            select(CurriculumConcept).where(
                CurriculumConcept.source_id.in_(sorted(concept_source_ids))
            )
        ).all()
    }
    inserted = updated = unchanged = 0
    now = utc_now()
    for record in snapshot.concepts:
        concept_id = str(record["id"])
        embedding_row = record["embedding_row"]
        embedding = (
            snapshot.embeddings[int(embedding_row)].tolist()
            if embedding_row is not None
            else None
        )
        values = {
            "source_id": record["source_id"],
            "external_id": record["external_id"],
            "concept_type": record["concept_type"],
            "cefr_level": record["cefr_level"],
            "title": record["title"],
            "description": record["description"],
            "topic_tags": record["topic_tags"],
            "attributes": record["attributes"],
            "review_status": record["review_status"],
            "content_hash": record["content_hash"],
            "embedding_model": record["embedding_model"],
            "embedding": embedding,
            "active": bool(record["active"]),
        }
        item = existing.get(concept_id)
        expected_embedded = embedding is not None
        is_unchanged = (
            item is not None
            and item.content_hash == record["content_hash"]
            and item.embedding_model == record["embedding_model"]
            and (item.embedding is not None) == expected_embedded
            and item.active == bool(record["active"])
        )
        if item is None:
            session.add(
                CurriculumConcept(
                    id=concept_id,
                    imported_at=now,
                    **values,
                )
            )
            inserted += 1
        elif is_unchanged:
            for key, value in values.items():
                setattr(item, key, value)
            unchanged += 1
        else:
            for key, value in values.items():
                setattr(item, key, value)
            item.imported_at = now
            updated += 1

    deactivated = 0
    for concept_id, item in existing.items():
        if concept_id not in snapshot_ids and item.active:
            item.active = False
            deactivated += 1
    session.flush()
    return {
        "snapshot_version": snapshot.manifest["snapshot_version"],
        "sources": len(snapshot.sources),
        "concepts": len(snapshot.concepts),
        "embedded": snapshot.embeddings.shape[0],
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deactivated": deactivated,
        "embedding_model": snapshot.manifest["embedding_model"],
    }


def import_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    snapshot = read_snapshot(path)
    with session_scope() as session:
        return _upsert_snapshot(session, snapshot)


def inspect_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    snapshot = read_snapshot(path)
    return {
        **snapshot.manifest,
        "path": str(path),
        "compressed_bytes": path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "import", "inspect"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()
    try:
        if args.command == "export":
            result = export_snapshot(args.snapshot)
        elif args.command == "import":
            result = import_snapshot(args.snapshot)
        else:
            result = inspect_snapshot(args.snapshot)
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        get_engine().dispose()


if __name__ == "__main__":
    main()
