"""Small reviewed learner-facing glosses for known ambiguous source entries.

WordNet definitions remain provenance evidence, but some of its first senses
are either dated or too technical for direct display.  This bank is deliberately
small: the weekly writer handles general CEFR simplification, while these
reviewed entries also repair already-generated prototype packs safely.
"""

from __future__ import annotations


_REVIEWED_GLOSSES: dict[tuple[str, str | None], str] = {
    ("browser", "noun"): (
        "a program used to open and view pages on the internet"
    ),
    ("choir", "noun"): (
        "a group of people who sing together"
    ),
    ("digital", "adjective"): (
        "using electronic signals or computer technology"
    ),
    ("empire", "noun"): (
        "a group of regions ruled by one leader or state"
    ),
    ("fitness", "noun"): (
        "the condition of being physically healthy and strong"
    ),
    ("guitarist", "noun"): (
        "a person who plays the guitar"
    ),
    ("historian", "noun"): (
        "a person who studies and writes about history"
    ),
    ("historic", "adjective"): (
        "important or famous in history"
    ),
    ("historical", "adjective"): (
        "connected with history or past events"
    ),
    ("jazz", "noun"): (
        "a music style with strong rhythm and improvisation"
    ),
    ("modem", "noun"): (
        "a device that connects a computer or network to the internet"
    ),
    ("network", "noun"): (
        "a group of connected computers, devices, or people"
    ),
    ("orchestra", "noun"): (
        "a large group of musicians who play instruments together"
    ),
    ("recording", "noun"): (
        "the process of saving sound or video"
    ),
    ("robot", "noun"): (
        "a machine that can move or perform tasks automatically"
    ),
    ("sportsmanship", "noun"): (
        "fair and respectful behavior while playing a sport"
    ),
    ("telecommunications", "noun"): (
        "systems for sending information electronically over a distance"
    ),
    ("workout", "noun"): (
        "a period of physical exercise or training"
    ),
    ("website", "noun"): (
        "a group of connected pages that you can visit on the internet"
    ),
    ("web", "noun"): (
        "the connected pages and information that people use on the internet"
    ),
    ("screen", "noun"): (
        "the part of a phone or computer that shows text and pictures"
    ),
    ("software", "noun"): (
        "the programs and apps that run on a computer or other device"
    ),
}


def reviewed_learner_gloss(
    word: str,
    part_of_speech: str | None = None,
) -> str | None:
    normalized_word = " ".join(word.casefold().split())
    normalized_pos = part_of_speech.casefold().strip() if part_of_speech else None
    return (
        _REVIEWED_GLOSSES.get((normalized_word, normalized_pos))
        or _REVIEWED_GLOSSES.get((normalized_word, None))
    )
