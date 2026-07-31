from __future__ import annotations

from pathlib import Path
from typing import Protocol

from speakflow.shared import JsonObject


class SpeechRecognizer(Protocol):
    def transcribe(self, audio_path: Path) -> JsonObject: ...


class PronunciationScorer(Protocol):
    def score(self, audio_path: Path, target_text: str) -> JsonObject: ...
