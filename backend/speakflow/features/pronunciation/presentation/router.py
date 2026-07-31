from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def build_pronunciation_router(
    *,
    score_pronunciation: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/pronunciation", tags=["pronunciation"])
    router.add_api_route("", score_pronunciation, methods=["POST"])
    return router
