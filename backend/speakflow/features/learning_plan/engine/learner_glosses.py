"""Reviewed WordNet senses and learner-facing glosses for ambiguous entries.

WordNet definitions remain provenance evidence, but some of its first senses
are either dated or too technical for direct display.  This bank is deliberately
small: the weekly writer handles general CEFR simplification, while these
reviewed entries also repair already-generated prototype packs safely.
"""

from __future__ import annotations

_REVIEWED_WORDNET_SENSES: dict[tuple[str, str], str] = {
    ("actor", "noun"): "actor.n.01",
    ("appointment", "noun"): "date.n.03",
    ("book", "noun"): "book.n.01",
    ("browser", "noun"): "browser.n.02",
    ("calculator", "noun"): "calculator.n.02",
    ("championship", "noun"): "championship.n.02",
    ("club", "noun"): "club.n.02",
    ("commerce", "noun"): "commerce.n.01",
    ("competition", "noun"): "contest.n.01",
    ("digital", "adjective"): "digital.a.03",
    ("fitness", "noun"): "fitness.n.02",
    ("hardware", "noun"): "hardware.n.03",
    ("instrument", "noun"): "musical_instrument.n.01",
    ("jazz", "noun"): "jazz.n.02",
    ("language", "noun"): "language.n.01",
    ("match", "noun"): "match.n.02",
    ("network", "noun"): "network.n.01",
    ("online", "adjective"): "on-line.a.02",
    ("queen", "noun"): "queen.n.02",
    ("recording", "noun"): "recording.n.02",
    ("running", "noun"): "run.n.07",
    ("screen", "noun"): "screen.n.03",
    ("society", "noun"): "society.n.01",
    ("student", "noun"): "student.n.01",
    ("teacher", "noun"): "teacher.n.01",
    ("video", "noun"): "video_recording.n.01",
    ("village", "noun"): "village.n.02",
    ("web", "noun"): "world_wide_web.n.01",
    ("yoga", "noun"): "yoga.n.02",
}

_REVIEWED_GLOSSES: dict[tuple[str, str | None], str] = {
    ("album", "noun"): ("a collection of songs released together"),
    ("baseball", "noun"): ("a team game using a bat and ball"),
    ("basketball", "noun"): ("a team game using a ball and hoops"),
    ("browser", "noun"): ("a program used to open and view pages on the internet"),
    ("camera", "noun"): ("a device used to take photographs"),
    ("championship", "noun"): ("a competition that decides the champion"),
    ("choir", "noun"): ("a group of people who sing together"),
    ("coach", "noun"): ("a person who trains a player or team"),
    ("coach", "verb"): ("to train and guide a player or team"),
    ("competition", "noun"): ("an event where people or teams try to win"),
    ("concert", "noun"): ("a live performance of music for an audience"),
    ("disco", "noun"): ("dance music with a strong regular beat"),
    ("digital", "adjective"): ("using electronic signals or computer technology"),
    ("download", "verb"): ("to copy data from another computer or the internet"),
    ("empire", "noun"): ("a group of regions ruled by one leader or state"),
    ("fitness", "noun"): ("the condition of being physically healthy and strong"),
    ("file", "noun"): ("saved information stored together on a computer"),
    ("flute", "noun"): ("a musical instrument played by blowing across a hole"),
    ("football", "noun"): ("a team game played by kicking a ball"),
    ("guitar", "noun"): ("a six-stringed instrument played with the hands"),
    ("guitarist", "noun"): ("a person who plays the guitar"),
    ("historian", "noun"): ("a person who studies and writes about history"),
    ("historic", "adjective"): ("important or famous in history"),
    ("historical", "adjective"): ("connected with history or past events"),
    ("hardware", "noun"): ("the physical parts of a computer or electronic system"),
    ("instrument", "noun"): ("an object used to produce musical sounds"),
    ("jazz", "noun"): ("a music style with strong rhythm and improvisation"),
    ("judo", "noun"): ("a Japanese sport using controlled throws and holds"),
    ("language", "noun"): ("a system people use to communicate with others"),
    ("match", "noun"): ("a sports contest between players or teams"),
    ("message", "noun"): ("information sent from one person to another"),
    ("modem", "noun"): ("a device that connects a computer or network to the internet"),
    ("network", "noun"): ("a group of connected computers, devices, or people"),
    ("music", "noun"): ("organized sounds made by voices or instruments"),
    ("olympics", "noun"): ("international sports games held every four years"),
    ("online", "adjective"): ("connected to or available through the internet"),
    ("orchestra", "noun"): ("a large group of musicians who play instruments together"),
    ("pc", "noun"): ("a computer designed for one person to use"),
    ("phone", "noun"): ("a device used to call or message people"),
    ("piano", "noun"): ("an instrument played using black and white keys"),
    ("queen", "noun"): ("a female ruler of a kingdom"),
    ("referee", "noun"): ("the official who makes sure players follow the rules"),
    ("recording", "noun"): ("the process of saving sound or video"),
    ("robot", "noun"): ("a machine that can move or perform tasks automatically"),
    ("running", "noun"): ("the activity or sport of moving quickly on foot"),
    ("sportsmanship", "noun"): ("fair and respectful behavior while playing a sport"),
    ("telecommunications", "noun"): (
        "systems for sending information electronically over a distance"
    ),
    ("workout", "noun"): ("a period of physical exercise or training"),
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
    ("singing", "noun"): ("making musical sounds with your voice"),
    ("soccer", "noun"): ("a team game where players kick a ball"),
    ("stopwatch", "noun"): ("a watch used to measure exact periods of time"),
    ("stroke", "noun"): ("one complete movement used to hit a ball"),
    ("swimming", "noun"): ("moving through water using your arms and legs"),
    ("symphony", "noun"): ("a long musical work written for an orchestra"),
    ("tennis", "noun"): ("a racket game played over a net"),
    ("trumpet", "noun"): ("a brass instrument played by blowing through a mouthpiece"),
    ("violin", "noun"): ("a small stringed instrument played with a bow"),
    ("volleyball", "noun"): ("a team game played over a high net"),
}


def reviewed_wordnet_synset(word: str, part_of_speech: str | None) -> str | None:
    """Return an explicitly reviewed source sense for an exact word/POS pair."""

    return _REVIEWED_WORDNET_SENSES.get(
        (
            " ".join(word.casefold().split()),
            (part_of_speech or "").casefold().strip(),
        )
    )


def reviewed_learner_gloss(
    word: str,
    part_of_speech: str | None = None,
) -> str | None:
    normalized_word = " ".join(word.casefold().split())
    normalized_pos = part_of_speech.casefold().strip() if part_of_speech else None
    return _REVIEWED_GLOSSES.get(
        (normalized_word, normalized_pos)
    ) or _REVIEWED_GLOSSES.get((normalized_word, None))
