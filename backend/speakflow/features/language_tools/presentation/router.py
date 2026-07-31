from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def build_language_tools_router(
    *,
    check_grammar: Callable[..., Any],
    lookup_word: Callable[..., Any],
    get_tts_audio: Callable[..., Any],
    pronunciation_guide: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["language-tools"])
    router.add_api_route("/grammar/check", check_grammar, methods=["POST"])
    router.add_api_route("/vocabulary/lookup", lookup_word, methods=["POST"])
    router.add_api_route("/tts", get_tts_audio, methods=["GET"])
    router.add_api_route(
        "/pronunciation/guide",
        pronunciation_guide,
        methods=["GET"],
    )
    return router
