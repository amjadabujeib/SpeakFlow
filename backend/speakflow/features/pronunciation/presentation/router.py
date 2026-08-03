from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def build_pronunciation_router(
    *,
    score_pronunciation: Callable[..., Any],
    transcribe_speaking: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["pronunciation"])
    router.add_api_route("/pronunciation", score_pronunciation, methods=["POST"])
    router.add_api_route(
        "/speaking/transcribe",
        transcribe_speaking,
        methods=["POST"],
    )
    return router
