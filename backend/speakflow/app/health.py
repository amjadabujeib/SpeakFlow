from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def build_health_router(health: Callable[..., Any]) -> APIRouter:
    router = APIRouter(tags=["health"])
    router.add_api_route("/health", health, methods=["GET"])
    return router
