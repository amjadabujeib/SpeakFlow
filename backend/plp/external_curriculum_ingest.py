from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import cmudict
from sqlalchemy import select

from .config import DATA_ROOT
from .database import get_engine, session_scope
from .external_curriculum import (
    DEFAULT_CEFR_J_ROOT,
    DEFAULT_WORDS_CEFR_ROOT,
    ExternalConceptRecord,
    add_frequency_evidence,
    add_lexical_reference_evidence,
    read_cefr_j,
    read_evp,
    read_word_frequencies,
)
from .models import CurriculumConcept, CurriculumSource, utc_now


def ingest_external_concepts(
    *,
    source_data: dict,
    records: list[ExternalConceptRecord],
) -> dict:
    if not records:
        raise ValueError("external curriculum source contains no usable records")
    ids = [record.external_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("external curriculum source contains duplicate concept IDs")
    with session_scope() as session:
        source = session.get(CurriculumSource, source_data["id"])
        if source is None:
            source = CurriculumSource(**source_data)
            session.add(source)
        else:
            for key, value in source_data.items():
                setattr(source, key, value)
        # No ORM relationship links CurriculumSource to CurriculumConcept, so
        # make the foreign-key parent durable in this transaction before the
        # bulk concept flush.
        session.flush()
        existing = {
            item.external_id: item
            for item in session.scalars(
                select(CurriculumConcept).where(
                    CurriculumConcept.source_id == source_data["id"]
                )
            ).all()
        }
        inserted = updated = unchanged = 0
        active_ids: set[str] = set()
        for record in records:
            payload = asdict(record)
            content_hash = hashlib.sha256(
                json.dumps(
                    {"source_id": source_data["id"], **payload},
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            concept_id = f"{source_data['id']}:{record.external_id}"
            active_ids.add(record.external_id)
            item = existing.get(record.external_id)
            values = {
                "concept_type": record.concept_type,
                "cefr_level": record.cefr_level,
                "title": record.title,
                "description": record.description,
                "topic_tags": record.topic_tags,
                "attributes": record.attributes,
                "review_status": record.review_status,
                "content_hash": content_hash,
                "embedding_model": None,
                "embedding": None,
                "active": True,
                "imported_at": utc_now(),
            }
            if item is None:
                session.add(
                    CurriculumConcept(
                        id=concept_id,
                        source_id=source_data["id"],
                        external_id=record.external_id,
                        **values,
                    )
                )
                inserted += 1
            elif item.content_hash == content_hash and item.active:
                unchanged += 1
            else:
                for key, value in values.items():
                    setattr(item, key, value)
                updated += 1
        deactivated = 0
        for external_id, item in existing.items():
            if external_id not in active_ids and item.active:
                item.active = False
                deactivated += 1
    return {
        "source": source_data["id"],
        "records": len(records),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deactivated": deactivated,
    }


def cefr_j_source(root: Path = DEFAULT_CEFR_J_ROOT) -> dict:
    files = [
        root / "cefrj-vocabulary-profile-1.5.csv",
        root / "cefrj-grammar-profile-20180315.csv",
    ]
    checksum = hashlib.sha256()
    for path in files:
        checksum.update(path.name.encode())
        checksum.update(path.read_bytes())
    return {
        "id": "cefr_j_profiles_2020",
        "title": "CEFR-J Vocabulary and Grammar Profiles",
        "author": "Tono Laboratory, Tokyo University of Foreign Studies",
        "locator": "https://github.com/openlanguageprofiles/olp-en-cefrj",
        "license": "Evaluation source; citation required by provider terms",
        "version": "vocabulary-1.5+grammar-20180315",
        "checksum": checksum.hexdigest(),
    }


def words_cefr_source(root: Path = DEFAULT_WORDS_CEFR_ROOT) -> dict:
    files = [root / "csv" / "words.csv", root / "csv" / "word_pos.csv"]
    checksum = hashlib.sha256()
    for path in files:
        checksum.update(path.name.encode())
        checksum.update(path.read_bytes())
    return {
        "id": "words_cefr_frequency_2024",
        "title": "Words CEFR Dataset frequency evidence",
        "author": "Maximax67",
        "locator": "https://github.com/Maximax67/Words-CEFR-Dataset",
        "license": "MIT project dataset; derived sources acknowledged upstream",
        "version": "repository snapshot",
        "checksum": checksum.hexdigest(),
    }


def upsert_external_source(source_data: dict) -> None:
    with session_scope() as session:
        source = session.get(CurriculumSource, source_data["id"])
        if source is None:
            session.add(CurriculumSource(**source_data))
        else:
            for key, value in source_data.items():
                setattr(source, key, value)


def lexical_reference_sources() -> list[dict]:
    wordnet_path = DATA_ROOT.parent / "nltk_data" / "corpora" / "wordnet.zip"
    cmudict_path = Path(cmudict.__file__).parent / "data" / "cmudict.dict"
    if not wordnet_path.is_file():
        raise ValueError(f"WordNet corpus is missing at {wordnet_path}")
    return [
        {
            "id": "princeton_wordnet_3_0",
            "title": "Princeton WordNet 3.0",
            "author": "Princeton University",
            "locator": "https://wordnet.princeton.edu/",
            "license": "Princeton WordNet License",
            "version": "3.0",
            "checksum": hashlib.sha256(wordnet_path.read_bytes()).hexdigest(),
        },
        {
            "id": "cmudict_local",
            "title": "CMU Pronouncing Dictionary",
            "author": "Carnegie Mellon University",
            "locator": "https://github.com/cmusphinx/cmudict",
            "license": "BSD-style CMUdict license",
            "version": "installed Python package snapshot",
            "checksum": hashlib.sha256(cmudict_path.read_bytes()).hexdigest(),
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import external curriculum claims for private evaluation."
    )
    parser.add_argument("--cefr-j-root", type=Path, default=DEFAULT_CEFR_J_ROOT)
    parser.add_argument(
        "--words-cefr-root", type=Path, default=DEFAULT_WORDS_CEFR_ROOT
    )
    parser.add_argument("--evp-csv", type=Path)
    args = parser.parse_args()
    reports = []
    cefr_source = cefr_j_source(args.cefr_j_root)
    records = read_cefr_j(args.cefr_j_root)
    if args.words_cefr_root.exists():
        frequency_source = words_cefr_source(args.words_cefr_root)
        upsert_external_source(frequency_source)
        records = add_frequency_evidence(
            records, read_word_frequencies(args.words_cefr_root)
        )
    for reference_source in lexical_reference_sources():
        upsert_external_source(reference_source)
    records = add_lexical_reference_evidence(records)
    reports.append(
        ingest_external_concepts(
            source_data=cefr_source,
            records=records,
        )
    )
    if args.evp_csv is not None:
        evp_checksum = hashlib.sha256(args.evp_csv.read_bytes()).hexdigest()
        reports.append(
            ingest_external_concepts(
                source_data={
                    "id": "english_vocabulary_profile_evaluation",
                    "title": "English Vocabulary Profile evaluation snapshot",
                    "author": "Cambridge English Profile",
                    "locator": str(args.evp_csv),
                    "license": "Private prototype evaluation; permission pending",
                    "version": args.evp_csv.name,
                    "checksum": evp_checksum,
                },
                records=read_evp(args.evp_csv),
            )
        )
    from .retrieval import CurriculumRetriever

    retriever = CurriculumRetriever()
    try:
        with session_scope() as session:
            reports.append(retriever.backfill_concept_embeddings(session))
    finally:
        retriever.close()
    print(json.dumps(reports, indent=2))
    get_engine().dispose()
