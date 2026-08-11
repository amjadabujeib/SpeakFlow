from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from sqlalchemy import select

from .config import OLLAMA_EMBED_MODEL
from .database import get_engine, session_scope
from .external_curriculum import read_cefr_j
from .external_curriculum_ingest import cefr_j_source, words_cefr_source
from .interest_vocabulary import (
    REVIEWED_INTEREST_TERMS,
    concept_term_key,
    effective_interest_tags,
    reviewed_term_count,
)
from .lexical_policy import (
    is_teachable_lexical_concept,
    supports_lexical_prototype,
)
from .mission_catalog import INTEREST_TAGS
from .models import CurriculumConcept, CurriculumSource


def audit_curriculum() -> dict:
    try:
        parsed_ids: set[str] | None = {item.external_id for item in read_cefr_j()}
    except FileNotFoundError:
        parsed_ids = None
    source_factories = {
        "cefr_j_profiles_2020": cefr_j_source,
        "words_cefr_frequency_2024": words_cefr_source,
    }
    expected_sources = {}
    for source_id, factory in source_factories.items():
        try:
            expected_sources[source_id] = factory()
        except FileNotFoundError:
            expected_sources[source_id] = None
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
        catalog_rows = session.execute(
            select(
                CurriculumConcept.title,
                CurriculumConcept.cefr_level,
                CurriculumConcept.topic_tags,
                CurriculumConcept.attributes,
                CurriculumConcept.embedding_model,
                CurriculumConcept.embedding.is_not(None),
                CurriculumConcept.concept_type,
                CurriculumConcept.review_status,
            ).where(CurriculumConcept.active.is_(True))
        ).all()
    rows = [
        row
        for row in catalog_rows
        if row.concept_type == "vocabulary" and row.review_status == "prototype_ready"
    ]

    coverage: dict[str, dict[str, set[str]]] = {
        item.id: defaultdict(set) for item in INTEREST_TAGS
    }
    teachable_coverage: dict[str, dict[str, set[str]]] = {
        item.id: defaultdict(set) for item in INTEREST_TAGS
    }
    malformed_definitions = 0
    reviewed_overrides = 0
    embedded = 0
    examples = {}
    watched = {"browser", "fitness", "language", "match", "student", "teacher"}
    matched_reviewed_terms: set[tuple[str, str, str]] = set()
    safe_topical = 0
    safe_general = 0
    unsupported_part_of_speech = 0
    stored_interest_tagged = 0
    effective_interest_tagged = 0
    for row in rows:
        (
            title,
            level,
            tags,
            attributes,
            embedding_model,
            has_embedding,
            _,
            _,
        ) = row
        term = title.casefold()
        key = concept_term_key(
            cefr_level=level,
            title=title,
            part_of_speech=attributes.get("part_of_speech"),
        )
        effective_tags = effective_interest_tags(
            tags,
            cefr_level=level,
            title=title,
            part_of_speech=attributes.get("part_of_speech"),
        )
        if any(key in terms for terms in REVIEWED_INTEREST_TERMS.values()):
            matched_reviewed_terms.add(key)
        for tag in set(effective_tags):
            if tag in coverage:
                coverage[tag][level].add(term)
        definition = attributes.get("definition", "")
        if tags:
            stored_interest_tagged += 1
        if effective_tags:
            effective_interest_tagged += 1
        if not supports_lexical_prototype(attributes.get("part_of_speech")):
            unsupported_part_of_speech += 1
        teachable = is_teachable_lexical_concept(
            title=title,
            part_of_speech=attributes.get("part_of_speech"),
            cefr_level=level,
            source_definition=definition,
            ipa=attributes.get("ipa", ""),
            request_id=key[1],
        )
        if teachable:
            if effective_tags:
                safe_topical += 1
            else:
                safe_general += 1
            for tag in set(effective_tags):
                if tag in teachable_coverage:
                    teachable_coverage[tag][level].add(term)
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
                    "tags": effective_tags,
                }
            )

    return {
        "source_integrity": {
            source_id: {
                "present": source_id in stored_sources,
                "local_source_available": expected is not None,
                "checksum_match": None
                if expected is None
                else (
                    stored_sources[source_id].checksum == expected["checksum"]
                    if source_id in stored_sources
                    else False
                ),
            }
            for source_id, expected in expected_sources.items()
        },
        "record_integrity": {
            "local_source_available": parsed_ids is not None,
            "parsed_records": len(parsed_ids) if parsed_ids is not None else None,
            "active_database_records": len(db_external_ids),
            "missing_from_database": (
                len(parsed_ids - db_external_ids) if parsed_ids is not None else None
            ),
            "extra_in_database": (
                len(db_external_ids - parsed_ids) if parsed_ids is not None else None
            ),
        },
        "catalog_composition": {
            "active_records": len(catalog_rows),
            "concept_types": dict(
                sorted(Counter(row.concept_type for row in catalog_rows).items())
            ),
            "review_statuses": dict(
                sorted(Counter(row.review_status for row in catalog_rows).items())
            ),
            "vocabulary_records": sum(
                row.concept_type == "vocabulary" for row in catalog_rows
            ),
            "distinct_vocabulary_headwords": len(
                {
                    row.title.casefold()
                    for row in catalog_rows
                    if row.concept_type == "vocabulary"
                }
            ),
        },
        "prototype_integrity": {
            "records": len(rows),
            "embedded": embedded,
            "reviewed_sense_overrides": reviewed_overrides,
            "malformed_definitions": malformed_definitions,
        },
        "runtime_lexical_roles": {
            "source_interest_tagged": stored_interest_tagged,
            "effectively_interest_tagged": effective_interest_tagged,
            "safe_topical": safe_topical,
            "safe_general": safe_general,
            "excluded_or_not_teachable": len(rows) - safe_topical - safe_general,
            "unsupported_part_of_speech": unsupported_part_of_speech,
        },
        "reviewed_interest_vocabulary": {
            "assignments": reviewed_term_count(),
            "matched_concepts": len(matched_reviewed_terms),
            "missing_assignments": reviewed_term_count() - len(matched_reviewed_terms),
        },
        "direct_interest_coverage": {
            interest: {level: len(counts[level]) for level in ("A1", "A2", "B1", "B2")}
            for interest, counts in coverage.items()
        },
        "teachable_interest_coverage": {
            interest: {level: len(counts[level]) for level in ("A1", "A2", "B1", "B2")}
            for interest, counts in teachable_coverage.items()
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
