from __future__ import annotations

import json
import re
from collections import defaultdict

from sqlalchemy import select

from .config import OLLAMA_EMBED_MODEL
from .database import get_engine, session_scope
from .external_curriculum import cefr_j_source, read_cefr_j, words_cefr_source
from .mission_catalog import INTEREST_TAGS
from .models import CurriculumConcept, CurriculumSource


def audit_curriculum() -> dict:
    parsed = read_cefr_j()
    parsed_ids = {item.external_id for item in parsed}
    expected_sources = {
        item["id"]: item
        for item in (cefr_j_source(), words_cefr_source())
    }
    with session_scope() as session:
        stored_sources = {
            item.id: item
            for item in session.scalars(
                select(CurriculumSource).where(
                    CurriculumSource.id.in_(expected_sources)
                )
            )
        }
        db_external_ids = set(
            session.scalars(
                select(CurriculumConcept.external_id).where(
                    CurriculumConcept.source_id == "cefr_j_profiles_2020",
                    CurriculumConcept.active.is_(True),
                )
            )
        )
        rows = session.execute(
            select(
                CurriculumConcept.title,
                CurriculumConcept.cefr_level,
                CurriculumConcept.topic_tags,
                CurriculumConcept.attributes,
                CurriculumConcept.embedding_model,
                CurriculumConcept.embedding.is_not(None),
            ).where(
                CurriculumConcept.active.is_(True),
                CurriculumConcept.concept_type == "vocabulary",
                CurriculumConcept.review_status == "prototype_ready",
            )
        ).all()

    coverage: dict[str, dict[str, set[str]]] = {
        item.id: defaultdict(set) for item in INTEREST_TAGS
    }
    malformed_definitions = 0
    reviewed_overrides = 0
    embedded = 0
    examples = {}
    watched = {
        "browser", "fitness", "language", "match", "student", "teacher"
    }
    for title, level, tags, attributes, embedding_model, has_embedding in rows:
        term = title.casefold()
        for tag in set(tags):
            if tag in coverage:
                coverage[tag][level].add(term)
        definition = attributes.get("definition", "")
        if re.search(r";\s*;|[;:]\s*$", definition):
            malformed_definitions += 1
        if attributes.get("sense_selection") == "reviewed_override":
            reviewed_overrides += 1
        if has_embedding and embedding_model == OLLAMA_EMBED_MODEL:
            embedded += 1
        if term in watched:
            examples.setdefault(term, []).append(
                {
                    "level": level,
                    "synset": attributes.get("wordnet_synset"),
                    "definition": definition,
                    "tags": tags,
                }
            )

    return {
        "source_integrity": {
            source_id: {
                "present": source_id in stored_sources,
                "checksum_match": (
                    stored_sources[source_id].checksum == expected["checksum"]
                    if source_id in stored_sources
                    else False
                ),
            }
            for source_id, expected in expected_sources.items()
        },
        "record_integrity": {
            "parsed_records": len(parsed_ids),
            "active_database_records": len(db_external_ids),
            "missing_from_database": len(parsed_ids - db_external_ids),
            "extra_in_database": len(db_external_ids - parsed_ids),
        },
        "prototype_integrity": {
            "records": len(rows),
            "embedded": embedded,
            "reviewed_sense_overrides": reviewed_overrides,
            "malformed_definitions": malformed_definitions,
        },
        "direct_interest_coverage": {
            interest: {
                level: len(counts[level])
                for level in ("A1", "A2", "B1", "B2")
            }
            for interest, counts in coverage.items()
        },
        "watched_senses": examples,
    }


def main() -> None:
    try:
        print(json.dumps(audit_curriculum(), indent=2, ensure_ascii=False))
    finally:
        get_engine().dispose()


if __name__ == "__main__":
    main()
