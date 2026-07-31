from __future__ import annotations

from typing import Protocol

from speakflow.shared import JsonObject


class NewsProvider(Protocol):
    def articles(self, category: str, level: str, page: int) -> JsonObject: ...
