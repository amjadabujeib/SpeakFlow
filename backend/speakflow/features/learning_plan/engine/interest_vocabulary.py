"""Reviewed interest links for source-grounded CEFR vocabulary.

CEFR-J owns the word, part of speech, and level claim. WordNet and CMUdict own
the lexical evidence. This module only reviews which existing exact concepts
are useful for a learner-selected interest; it never invents a level, sense,
definition, or pronunciation.
"""

from __future__ import annotations

from collections.abc import Iterable

TermKey = tuple[str, str, str]

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
    "scientific development": ("science",),
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
        "blog",
        "blogger",
        "browser",
        "cd-rom",
        "computer",
        "cyberspace",
        "database",
        "digital",
        "email",
        "hardware",
        "internet",
        "laptop",
        "modem",
        "network",
        "online",
        "robot",
        "software",
        "telecommunications",
        "website",
        "web",
    ),
    "sports": (
        "aerobic",
        "athlete",
        "athletic",
        "badminton",
        "baseball",
        "basketball",
        "boxing",
        "cricket",
        "fitness",
        "football",
        "golf",
        "gym",
        "gymnastics",
        "hockey",
        "referee",
        "rugby",
        "soccer",
        "sportsmanship",
        "tennis",
        "tournament",
        "volleyball",
        "workout",
        "yoga",
    ),
    "music": (
        "album",
        "choir",
        "concert",
        "guitar",
        "guitarist",
        "lyrics",
        "jazz",
        "melody",
        "music",
        "musical",
        "musician",
        "orchestra",
        "piano",
        "rehearsal",
        "rhythm",
        "singer",
        "song",
    ),
    "history": (
        "ancient",
        "archaeology",
        "archive",
        "century",
        "empire",
        "heritage",
        "historian",
        "historic",
        "historical",
        "history",
        "museum",
    ),
}


def _terms(level: str, part_of_speech: str, *titles: str) -> set[TermKey]:
    return {
        (level, " ".join(title.casefold().split()), part_of_speech) for title in titles
    }


REVIEWED_INTEREST_TERMS: dict[str, frozenset[TermKey]] = {
    "technology": frozenset(
        _terms(
            "A1",
            "noun",
            "camera",
            "file",
            "machine",
            "message",
            "phone",
            "radio",
            "technology",
            "telephone",
            "television",
            "TV",
            "video",
        )
        | _terms("A2", "verb", "download")
        | _terms("A2", "noun", "PC", "screen")
        | _terms("B1", "adjective", "electronic")
        | _terms("B1", "verb", "fax", "upload")
        | _terms(
            "B1",
            "noun",
            "calculator",
            "device",
            "format",
            "keyboard",
            "net",
            "switch",
        )
        | _terms("B2", "verb", "access")
        | _terms("B2", "adverb", "electronically")
        | _terms(
            "B2",
            "noun",
            "amplifier",
            "circuit",
            "circuitry",
            "cursor",
            "data",
            "electronics",
            "icon",
            "input",
            "microcomputer",
            "microphone",
            "programmer",
            "ram",
            "spreadsheet",
            "transistor",
        )
    ),
    "sports": frozenset(
        _terms(
            "A1",
            "noun",
            "coach",
            "match",
            "Olympics",
            "sport",
            "swimming",
            "team",
        )
        | _terms(
            "A2",
            "noun",
            "championship",
            "competition",
            "cycling",
            "exercise",
            "running",
            "stadium",
            "training",
        )
        | _terms("B2", "verb", "coach")
        | _terms(
            "B2",
            "noun",
            "athletics",
            "boxer",
            "coaching",
            "defeat",
            "judo",
            "opponent",
            "stopwatch",
            "stroke",
            "win",
        )
    ),
    "music": frozenset(
        _terms(
            "A2",
            "noun",
            "composer",
            "disco",
            "instrument",
            "performance",
            "singing",
            "symphony",
            "violin",
        )
        | _terms("B1", "noun", "DJ", "flute", "performer", "trumpet")
        | _terms("B2", "adjective", "orchestral", "solo")
        | _terms(
            "B2",
            "noun",
            "ballad",
            "ballet",
            "cello",
            "conductor",
            "karaoke",
            "refrain",
            "reggae",
        )
    ),
    "history": frozenset(
        _terms("A1", "adverb", "ago")
        | _terms(
            "A1",
            "noun",
            "fight",
            "king",
            "nationality",
            "palace",
            "peace",
            "prince",
            "princess",
            "ruler",
            "war",
            "year",
        )
        | _terms("A2", "adjective", "national", "royal", "traditional")
        | _terms(
            "A2",
            "noun",
            "account",
            "castle",
            "country",
            "crown",
            "government",
            "nation",
            "queen",
            "soldier",
            "tradition",
        )
        | _terms("B1", "adjective", "past")
        | _terms("B1", "adverb", "traditionally")
        | _terms(
            "B1",
            "noun",
            "army",
            "battle",
            "constitution",
            "democracy",
            "emperor",
            "invasion",
            "myth",
            "record",
            "settlement",
        )
        | _terms("B2", "adjective", "federal", "governmental", "prehistoric")
        | _terms(
            "B2",
            "noun",
            "ally",
            "battlefield",
            "bureaucracy",
            "engagement",
            "holocaust",
            "ideology",
            "impressionism",
            "province",
            "relic",
            "tyranny",
        )
    ),
}

REVIEWED_INTEREST_EXCLUSIONS: frozenset[tuple[str, TermKey]] = frozenset(
    {
        ("technology", ("B1", "breeding", "noun")),
        ("technology", ("B1", "chemical", "noun")),
        ("technology", ("B2", "chemotherapy", "noun")),
    }
)


def concept_term_key(
    *,
    cefr_level: str | None,
    title: str,
    part_of_speech: str | None,
) -> TermKey:
    return (
        (cefr_level or "").upper(),
        " ".join(title.casefold().split()),
        (part_of_speech or "").casefold().strip(),
    )


def effective_interest_tags(
    stored_tags: Iterable[str],
    *,
    cefr_level: str | None,
    title: str,
    part_of_speech: str | None,
) -> list[str]:
    """Merge reviewed exact links and removals with stored source-derived tags."""

    key = concept_term_key(
        cefr_level=cefr_level,
        title=title,
        part_of_speech=part_of_speech,
    )
    tags = list(dict.fromkeys(str(item) for item in stored_tags if item))
    tags = [item for item in tags if (item, key) not in REVIEWED_INTEREST_EXCLUSIONS]
    for interest, terms in REVIEWED_INTEREST_TERMS.items():
        if key in terms and interest not in tags:
            tags.append(interest)
    return tags


def reviewed_term_count() -> int:
    return sum(len(items) for items in REVIEWED_INTEREST_TERMS.values())


def source_interest_tags(value: str, *, title: str = "") -> list[str]:
    """Map exact source topics and reviewed exact headwords to interest IDs."""

    source_topics = {
        item.strip().casefold() for item in value.split("|") if item.strip()
    }
    normalized_title = " ".join(title.casefold().split())
    tags: list[str] = []
    for topic in sorted(source_topics):
        for interest in _SOURCE_TOPIC_INTERESTS.get(topic, ()):
            if interest not in tags:
                tags.append(interest)
    for interest, keywords in _TITLE_KEYWORDS.items():
        if normalized_title in keywords and interest not in tags:
            tags.append(interest)
    return tags
