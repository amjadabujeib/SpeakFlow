"""Language policy for learner-authored roleplay turns."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import cmudict

ROLEPLAY_ENGLISH_TURN_MESSAGE = (
    "Please write your roleplay turn in English. "
    "Use Language Help to translate Arabic first."
)

ROLEPLAY_UNCLEAR_TURN_REPLY = (
    "I'm sorry, I didn't understand that. Could you say it another way?"
)
ROLEPLAY_OFF_TOPIC_TURN_REPLY = (
    "I didn't understand how that relates to our situation. "
    "Could you respond to the roleplay?"
)

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?")
_FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "ours",
    "she",
    "so",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "they",
    "this",
    "those",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
}
_CONVENTIONAL_SHORT_TURNS = {
    "all",
    "alright",
    "bye",
    "cool",
    "done",
    "fine",
    "good",
    "goodbye",
    "great",
    "hello",
    "hey",
    "hi",
    "later",
    "maybe",
    "no",
    "nope",
    "ok",
    "okay",
    "perfect",
    "please",
    "right",
    "see",
    "sorry",
    "sure",
    "thank",
    "thanks",
    "welcome",
    "yeah",
    "yep",
    "yes",
}
_KEYBOARD_RUNS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


@lru_cache(maxsize=1)
def _english_lexicon() -> frozenset[str]:
    return frozenset(_ascii_word(item) for item in cmudict.words())


def _ascii_word(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold().replace("’", "'"))
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _obviously_malformed_unknown_word(value: str) -> bool:
    word = _ascii_word(value).replace("'", "")
    if len(word) < 3:
        return False
    if (
        (len(word) >= 4 and not re.search(r"[aeiouy]", word))
        or re.search(r"(.)\1\1", word)
        or re.search(r"[^aeiouy]{5,}", word)
    ):
        return True
    return any(word in row or word in row[::-1] for row in _KEYBOARD_RUNS)


def roleplay_turn_is_obviously_unclear(value: str) -> bool:
    """Reject only locally provable nonsense; contextual ambiguity stays with the model."""

    words = _WORD.findall(value)
    if not words:
        return True
    normalized = [_ascii_word(word) for word in words]
    if any(word in _CONVENTIONAL_SHORT_TURNS for word in normalized):
        return False
    if all(word in _FUNCTION_WORDS for word in normalized):
        return True
    lexicon = _english_lexicon()
    return any(
        word not in lexicon
        and not raw.isupper()
        and _obviously_malformed_unknown_word(word)
        for word, raw in zip(normalized, words, strict=True)
        if word not in _FUNCTION_WORDS
    )


def typed_roleplay_turn_error(value: str) -> str | None:
    """Reject clearly non-English scripts without guessing lexical validity."""

    letters = [character for character in value.strip() if character.isalpha()]
    if not letters or any(
        "LATIN" not in unicodedata.name(character, "") for character in letters
    ):
        return ROLEPLAY_ENGLISH_TURN_MESSAGE
    return None


def ensure_typed_roleplay_turn_is_english(value: str) -> None:
    error = typed_roleplay_turn_error(value)
    if error is not None:
        raise ValueError(error)
