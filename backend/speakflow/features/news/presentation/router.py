from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def build_news_router(
    *,
    list_news: Callable[..., Any],
    proxy_image: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/news", tags=["news"])
    router.add_api_route("", list_news, methods=["GET"])
    router.add_api_route("/image", proxy_image, methods=["GET"])
    return router
