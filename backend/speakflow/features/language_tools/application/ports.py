from __future__ import annotations

from pathlib import Path
from typing import Protocol

from speakflow.shared import JsonObject


class GrammarCorrector(Protocol):
    def correct(self, text: str) -> JsonObject: ...


class VocabularyProvider(Protocol):
    def lookup(self, word: str) -> JsonObject: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str) -> Path: ...
