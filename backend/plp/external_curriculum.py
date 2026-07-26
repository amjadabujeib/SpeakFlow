from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import cmudict
from nltk.corpus import wordnet as wn
from sqlalchemy import select

from .config import DATA_ROOT
from .database import get_engine, session_scope
from .models import CurriculumConcept, CurriculumSource, utc_now


DEFAULT_CEFR_J_ROOT = Path(
    DATA_ROOT / "curriculum_sources" / "cefr_j" / "raw"
)
DEFAULT_WORDS_CEFR_ROOT = Path(
    DATA_ROOT / "curriculum_sources" / "words_cefr" / "raw"
)
_CEFR = re.compile(r"\b([ABC][12])\b", re.IGNORECASE)
_ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "F": "f", "G": "ɡ",
    "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ",
    "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
_WORDNET_POS = {
    "noun": wn.NOUN,
    "verb": wn.VERB,
    "adjective": wn.ADJ,
    "adverb": wn.ADV,
}
_SOURCE_TOPIC_INTERESTS = {
    "education": ("education",),
    "language": ("education",),
    "books and literature": ("education", "culture", "entertainment"),
    "work and jobs": ("business",),
    "services": ("business", "daily_life"),
    "shopping": ("business", "daily_life"),
    "things in the town, shops and shopping": ("business", "daily_life"),
    "travel": ("travel",),
    "travel and services vocab": ("travel",),
    "ways of travelling": ("travel",),
    "ways of traveling": ("travel",),
    "holidays": ("travel", "culture"),
    "nationalities and countries": ("culture",),
    "arts": ("culture", "entertainment"),
    "art": ("culture", "entertainment"),
    "film": ("culture", "entertainment"),
    "media": ("entertainment",),
    "free time, entertainment": ("entertainment",),
    "hobbies and pastimes": ("entertainment",),
    "hobbies and lifestyles": ("entertainment",),
    "leisure activities": ("entertainment",),
    "scientific development": ("science", "technology"),
    "health and body care": ("science", "daily_life"),
    "weather": ("science", "daily_life"),
    "house and home, environment": ("science", "daily_life"),
    "daily life": ("daily_life",),
    "family life": ("daily_life",),
    "food and drink": ("daily_life",),
    "objects and rooms": ("daily_life",),
    "clothes": ("daily_life",),
    "personal identification": ("daily_life",),
    "personal information": ("daily_life",),
    "relations with other people": ("daily_life",),
    "places": ("daily_life",),
}
_TITLE_KEYWORDS = {
    "technology": (
        "blog", "blogger", "browser", "cd-rom", "computer", "cyberspace",
        "database", "digital", "email", "hardware", "internet", "laptop",
        "modem", "network", "online", "robot", "software", "telecommunications",
        "website", "web",
    ),
    "sports": (
        "aerobic", "athlete", "athletic", "badminton", "baseball",
        "basketball", "boxing", "cricket", "fitness", "football", "golf",
        "gym", "gymnastics", "hockey", "referee", "rugby", "soccer",
        "sportsmanship", "tennis", "tournament", "volleyball", "workout",
        "yoga",
    ),
    "music": (
        "album", "choir", "concert", "guitar", "guitarist", "lyrics",
        "jazz", "melody", "music", "musical", "musician", "orchestra", "piano",
        "rehearsal", "rhythm", "singer", "song",
    ),
    "history": (
        "ancient", "archaeology", "archive", "century", "empire",
        "heritage", "historian", "historic", "historical", "history",
        "museum",
    ),
}
_REVIEWED_WORDNET_SENSES = {
    ("actor", "noun"): "actor.n.01",
    ("appointment", "noun"): "date.n.03",
    ("book", "noun"): "book.n.01",
    ("browser", "noun"): "browser.n.02",
    ("calculator", "noun"): "calculator.n.02",
    ("club", "noun"): "club.n.02",
    ("commerce", "noun"): "commerce.n.01",
    ("digital", "adjective"): "digital.a.03",
    ("fitness", "noun"): "fitness.n.02",
    ("jazz", "noun"): "jazz.n.02",
    ("language", "noun"): "language.n.01",
    ("match", "noun"): "match.n.02",
    ("network", "noun"): "network.n.01",
    ("recording", "noun"): "recording.n.02",
    ("screen", "noun"): "screen.n.03",
    ("society", "noun"): "society.n.01",
    ("student", "noun"): "student.n.01",
    ("teacher", "noun"): "teacher.n.01",
    ("video", "noun"): "video_recording.n.01",
    ("village", "noun"): "village.n.02",
    ("web", "noun"): "world_wide_web.n.01",
    ("yoga", "noun"): "yoga.n.02",
}


@dataclass(frozen=True)
class ExternalConceptRecord:
    external_id: str
    concept_type: str
    cefr_level: str
    title: str
    description: str | None
    topic_tags: list[str]
    attributes: dict
    review_status: str = "evaluation_only"


def normalize_cefr(value: str | None) -> str | None:
    match = _CEFR.search(value or "")
    return match.group(1).upper() if match else None


def concept_from_vocabulary_row(row: dict[str, str]) -> ExternalConceptRecord:
    headword = (row.get("headword") or "").strip()
    part_of_speech = (row.get("pos") or "").strip()
    level = normalize_cefr(row.get("CEFR"))
    if not headword or not level:
        raise ValueError("CEFR-J vocabulary row requires headword and CEFR")
    topic_text = " | ".join(
        filter(
            None,
            (
                row.get("CoreInventory 1", "").strip(),
                row.get("CoreInventory 2", "").strip(),
                row.get("Threshold", "").strip(),
            ),
        )
    )
    # CEFR-J has no stable vocabulary row ID. Preserve case and the complete
    # level/topic claim so homographs such as the month ``March`` and the noun
    # ``march`` do not collapse into one database object.
    key = hashlib.sha256(
        "\x1f".join(
            (
                headword,
                part_of_speech,
                row.get("CEFR", "").strip(),
                topic_text,
            )
        ).encode()
    ).hexdigest()[:24]
    return ExternalConceptRecord(
        external_id=f"vocabulary:{key}",
        concept_type="vocabulary",
        cefr_level=level,
        title=headword,
        description=None,
        topic_tags=_interest_tags(topic_text, title=headword),
        attributes={
            "part_of_speech": part_of_speech or None,
            "source_level": row.get("CEFR", "").strip(),
            "source_topics": topic_text,
        },
    )


def concept_from_grammar_row(
    row: dict[str, str],
) -> ExternalConceptRecord | None:
    source_level = (row.get("CEFR-J Level") or "").strip()
    level = normalize_cefr(source_level)
    if level is None:
        for key in ("FREQ*DISP", "Core Inventory", "EGP", "GSELO"):
            level = normalize_cefr(row.get(key))
            if level is not None:
                break
    if level is None:
        return None
    item = (row.get("Grammatical Item") or "").strip()
    shorthand = (row.get("Shorthand Code") or "").strip()
    source_id = (row.get("ID") or shorthand).strip()
    if not item or not source_id:
        raise ValueError("CEFR-J grammar row requires ID and grammatical item")
    external_key = hashlib.sha256(
        f"{source_id}\x1f{shorthand}".encode()
    ).hexdigest()[:24]
    return ExternalConceptRecord(
        external_id=f"grammar:{external_key}",
        concept_type="grammar",
        cefr_level=level,
        title=item,
        description=(row.get("Notes") or "").strip() or None,
        topic_tags=[],
        attributes={
            "source_id": source_id,
            "shorthand_code": shorthand,
            "sentence_type": (row.get("Sentence Type") or "").strip() or None,
            "source_level": source_level or None,
            "frequency_dispersion_level": (row.get("FREQ*DISP") or "").strip() or None,
            "core_inventory_level": (row.get("Core Inventory") or "").strip() or None,
            "english_grammar_profile_level": (row.get("EGP") or "").strip() or None,
            "gselo_level": (row.get("GSELO") or "").strip() or None,
        },
    )


def concept_from_evp_row(row: dict[str, str]) -> ExternalConceptRecord:
    """Normalize a private EVP evaluation export with documented column names."""
    headword = (row.get("headword") or "").strip()
    part_of_speech = (row.get("part_of_speech") or "").strip()
    sense_id = (row.get("sense_id") or "").strip()
    level = normalize_cefr(row.get("cefr_level"))
    if not headword or not level:
        raise ValueError("EVP row requires headword and cefr_level")
    key = hashlib.sha256(
        f"{headword.casefold()}\x1f{part_of_speech.casefold()}\x1f{sense_id}".encode()
    ).hexdigest()[:24]
    topic = (row.get("topic") or "").strip()
    return ExternalConceptRecord(
        external_id=f"evp:{key}",
        concept_type="vocabulary",
        cefr_level=level,
        title=headword,
        description=(row.get("definition") or "").strip() or None,
        topic_tags=_interest_tags(topic, title=headword),
        attributes={
            "part_of_speech": part_of_speech or None,
            "sense_id": sense_id or None,
            "source_level": row.get("cefr_level", "").strip(),
            "source_topic": topic or None,
            "phrase_type": (row.get("phrase_type") or "").strip() or None,
        },
    )


def read_cefr_j(root: Path = DEFAULT_CEFR_J_ROOT) -> list[ExternalConceptRecord]:
    records: list[ExternalConceptRecord] = []
    with (root / "cefrj-vocabulary-profile-1.5.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        records.extend(concept_from_vocabulary_row(row) for row in csv.DictReader(source))
    with (root / "cefrj-grammar-profile-20180315.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        records.extend(
            concept
            for row in csv.DictReader(source)
            if (concept := concept_from_grammar_row(row)) is not None
        )
    return records


def read_evp(path: Path) -> list[ExternalConceptRecord]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [concept_from_evp_row(row) for row in csv.DictReader(source)]


def read_word_frequencies(root: Path = DEFAULT_WORDS_CEFR_ROOT) -> dict[str, int]:
    words: dict[str, str] = {}
    with (root / "csv" / "words.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            words[row["word_id"]] = row["word"].strip().casefold()
    frequencies: dict[str, int] = {}
    with (root / "csv" / "word_pos.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            word = words.get(row["word_id"])
            if not word:
                continue
            frequency = int(row["frequency_count"] or 0)
            frequencies[word] = max(frequencies.get(word, 0), frequency)
    return frequencies


def add_frequency_evidence(
    records: list[ExternalConceptRecord],
    frequencies: dict[str, int],
) -> list[ExternalConceptRecord]:
    enriched: list[ExternalConceptRecord] = []
    for record in records:
        if record.concept_type != "vocabulary":
            enriched.append(record)
            continue
        frequency = frequencies.get(record.title.casefold())
        attributes = dict(record.attributes)
        if frequency is not None:
            attributes.update(
                {
                    "frequency_count": frequency,
                    "frequency_source_id": "words_cefr_frequency_2024",
                }
            )
        enriched.append(replace(record, attributes=attributes))
    return enriched


def add_lexical_reference_evidence(
    records: list[ExternalConceptRecord],
) -> list[ExternalConceptRecord]:
    """Promote locally grounded lexical rows for prototype lesson use."""
    pronunciations = cmudict.dict()
    enriched: list[ExternalConceptRecord] = []
    for record in records:
        if record.concept_type != "vocabulary":
            enriched.append(record)
            continue
        pos = _WORDNET_POS.get(record.attributes.get("part_of_speech"))
        synsets = wn.synsets(record.title.replace(" ", "_"), pos=pos)
        phones = pronunciations.get(record.title.casefold())
        if not synsets or not phones:
            enriched.append(record)
            continue
        synset, sense_selection = _select_wordnet_synset(record, synsets)
        definition = _clean_reference_text(synset.definition())
        ipa = _phones_to_ipa(phones[0])
        if not definition or not ipa:
            enriched.append(record)
            continue
        attributes = dict(record.attributes)
        attributes.update(
            {
                "definition": definition,
                "ipa": ipa,
                "reference_examples": [
                    _clean_reference_text(item)
                    for item in synset.examples()[:4]
                    if _clean_reference_text(item)
                ],
                "wordnet_synset": synset.name(),
                "sense_selection": sense_selection,
                "definition_source_id": "princeton_wordnet_3_0",
                "pronunciation_source_id": "cmudict_local",
            }
        )
        enriched.append(
            replace(
                record,
                attributes=attributes,
                review_status="prototype_ready",
            )
        )
    return enriched


def _select_wordnet_synset(
    record: ExternalConceptRecord, synsets: list
) -> tuple[object, str]:
    """Use a reviewed exception or WordNet's corpus-frequency default.

    CEFR-J assigns levels to word/POS rows, not WordNet senses. Broad topic
    substring scoring previously overruled WordNet with false confidence and
    selected definitions such as ``language`` = song lyrics. Only explicit,
    reviewed exceptions may now override the source's first sense.
    """
    key = (
        record.title.casefold(),
        (record.attributes.get("part_of_speech") or "").casefold(),
    )
    override = _REVIEWED_WORDNET_SENSES.get(key)
    if override:
        selected = next(
            (synset for synset in synsets if synset.name() == override),
            None,
        )
        if selected is not None:
            return selected, "reviewed_override"
    return synsets[0], "wordnet_frequency_default"


def _clean_reference_text(value: str) -> str:
    text = " ".join(value.split())
    text = re.sub(r"(?:\s*;\s*){2,}.*$", "", text)
    text = re.sub(r"[;:\s]+$", "", text)
    return text.strip()[:500]


def _phones_to_ipa(phones: list[str]) -> str:
    values: list[str] = []
    for phone in phones:
        match = re.fullmatch(r"([A-Z]+)([012])?", phone.upper())
        if match is None or match.group(1) not in _ARPABET_TO_IPA:
            return ""
        base, stress = match.groups()
        value = _ARPABET_TO_IPA[base]
        if base == "AH" and stress == "0":
            value = "ə"
        elif base == "ER" and stress == "0":
            value = "ɚ"
        if stress == "1":
            value = "ˈ" + value
        elif stress == "2":
            value = "ˌ" + value
        values.append(value)
    return "".join(values)


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


def _interest_tags(value: str, *, title: str = "") -> list[str]:
    source_topics = {
        item.strip().casefold()
        for item in value.split("|")
        if item.strip()
    }
    normalized_title = " ".join(title.casefold().split())
    tags: list[str] = []
    for topic in sorted(source_topics):
        for interest in _SOURCE_TOPIC_INTERESTS.get(topic, ()):
            if interest not in tags:
                tags.append(interest)
    for interest, keywords in _TITLE_KEYWORDS.items():
        if any(normalized_title == keyword for keyword in keywords):
            if interest not in tags:
                tags.append(interest)
    return tags


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


if __name__ == "__main__":
    main()
