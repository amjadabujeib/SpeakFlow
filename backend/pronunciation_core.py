"""Shared pronunciation types, canonicalization, and score aggregation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np
from g2p_en import G2p
from g2p_en.expand import normalize_numbers
from nltk import pos_tag


MAX_GOPT_PHONES = 50
MAX_TARGET_PHONES = 200
OVERALL_SCORE_WEIGHTS = {
    "accuracy": 0.45,
    "fluency": 0.20,
    "prosody": 0.15,
    "completeness": 0.20,
}
WORD_OVERALL_SCORE_WEIGHTS = {
    "accuracy": 0.80,
    "prosody": 0.20,
}

# Exact first-occurrence ordering produced by GOPT's official
# gen_seq_data_phn.py on the SpeechOcean762 training split.
GOPT_PHONE_TO_ID = {
    phone: index
    for index, phone in enumerate(
        (
            "W", "IY", "K", "AO", "L", "IH", "T", "B", "EH", "R",
            "Z", "OW", "TH", "F", "AY", "V", "AH", "N", "UW", "S",
            "G", "AA", "M", "P", "NG", "HH", "EY", "SH", "AE", "D",
            "UH", "AW", "DH", "ER", "Y", "JH", "CH", "OY", "ZH",
        )
    )
}

ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "F": "f", "G": "ɡ",
    "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ",
    "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


class PronunciationScoringError(RuntimeError):
    """A production scorer error that is safe to expose to the API client."""

    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class CanonicalPronunciation:
    text: str
    words: tuple[str, ...]
    word_phones: tuple[tuple[str, ...], ...]

    @property
    def phones(self) -> tuple[str, ...]:
        return tuple(phone for word in self.word_phones for phone in word)

    @property
    def pure_phones(self) -> tuple[str, ...]:
        return tuple(_pure_phone(phone) for phone in self.phones)

    @property
    def ipa_phones(self) -> tuple[str, ...]:
        return tuple(arpabet_to_ipa(phone) for phone in self.phones)


def _pure_phone(phone: str) -> str:
    return re.sub(r"[012]$", "", phone.upper())


def arpabet_to_ipa(phone: str) -> str:
    phone = phone.upper()
    match = re.fullmatch(r"([A-Z]+)([012])?", phone)
    if not match:
        raise PronunciationScoringError(f"Unsupported canonical phone: {phone}", 422)
    base, stress = match.groups()
    if base not in ARPABET_TO_IPA:
        raise PronunciationScoringError(f"Unsupported canonical phone: {phone}", 422)

    ipa = ARPABET_TO_IPA[base]
    if base == "AH" and stress == "0":
        ipa = "ə"
    elif base == "ER" and stress == "0":
        ipa = "ɚ"
    if stress == "1":
        ipa = "ˈ" + ipa
    elif stress == "2":
        ipa = "ˌ" + ipa
    return ipa


def _normalized_english_tokens(text: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFD", str(text)).replace("’", "'")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"\bi\.e\.", "that is", value, flags=re.IGNORECASE)
    value = re.sub(r"\be\.g\.", "for example", value, flags=re.IGNORECASE)
    value = normalize_numbers(value)
    return tuple(
        match.group(0)
        for match in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", value)
    )


def normalized_english_words(text: str) -> tuple[str, ...]:
    """Normalize written English exactly once for G2P and ASR comparison."""
    return tuple(token.lower() for token in _normalized_english_tokens(text))


def calculate_overall_score(scores: dict) -> int:
    """Combine the four user-facing aspects into the displayed score."""
    weighted = sum(
        float(scores[name]) * weight
        for name, weight in OVERALL_SCORE_WEIGHTS.items()
    )
    return int(np.clip(round(weighted), 0, 100))


def calculate_word_overall_score(scores: dict) -> int:
    """Weight isolated words by pronunciation rather than sentence fluency."""
    weighted = sum(
        float(scores[name]) * weight
        for name, weight in WORD_OVERALL_SCORE_WEIGHTS.items()
    )
    return int(np.clip(round(weighted), 0, 100))


class LocalG2pCanonicalizer:
    def __init__(self):
        # g2p-en uses CMUdict where a word is known and its local neural model
        # for unseen words. It is the single canonical pronunciation source.
        self._g2p = G2p()

    def canonicalize(self, text: str) -> CanonicalPronunciation:
        written_tokens = _normalized_english_tokens(text)
        words = tuple(token.lower() for token in written_tokens)
        if not words:
            raise PronunciationScoringError(
                "Enter an English word or sentence containing letters.", 400
            )

        word_phones: list[tuple[str, ...]] = []
        missing: list[str] = []
        tagged_words = pos_tag(list(words))
        for written, word, (_, part_of_speech) in zip(
            written_tokens, words, tagged_words
        ):
            if written.isupper() and len(written) > 1 and word not in self._g2p.cmu:
                generated = [
                    phone
                    for letter in written.lower()
                    for phone in self._g2p.cmu[letter][0]
                ]
            elif word in self._g2p.homograph2features:
                first, second, first_pos = self._g2p.homograph2features[word]
                generated = (
                    first if part_of_speech.startswith(first_pos) else second
                )
            elif word in self._g2p.cmu:
                generated = self._g2p.cmu[word][0]
            else:
                generated = self._g2p.predict(word.replace("'", ""))
            phones = tuple(str(phone).upper() for phone in generated)
            if not phones or any(
                _pure_phone(phone) not in GOPT_PHONE_TO_ID for phone in phones
            ):
                missing.append(word)
                continue
            if len(phones) > MAX_GOPT_PHONES:
                raise PronunciationScoringError(
                    f'The target word "{word}" has {len(phones)} phones; '
                    f"a single word supports at most {MAX_GOPT_PHONES}.",
                    422,
                )
            word_phones.append(phones)

        if missing:
            unknown = ", ".join(sorted(set(missing)))
            raise PronunciationScoringError(
                f"The local English G2P model could not pronounce: {unknown}.",
                422,
            )

        pronunciation = CanonicalPronunciation(
            text=" ".join(word.upper() for word in words),
            words=tuple(word.upper() for word in words),
            word_phones=tuple(word_phones),
        )
        if len(pronunciation.phones) > MAX_TARGET_PHONES:
            raise PronunciationScoringError(
                f"The target has {len(pronunciation.phones)} phones; "
                f"this scorer supports at most {MAX_TARGET_PHONES}.",
                422,
            )
        return pronunciation


CmuCanonicalizer = LocalG2pCanonicalizer
