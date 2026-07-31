from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from plp.schemas import (
    ArabicTranslationView,
    RoleplayFinalizeView,
    RoleplayScenarioDraftView,
)


def build_roleplay_runtime_router(
    *,
    generate_scenario_draft: Callable[..., Any],
    translate_arabic: Callable[..., Any],
    legacy_escape_route: Callable[..., Any],
    finalize_session: Callable[..., Any],
    websocket_endpoint: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(tags=["roleplay"])
    router.add_api_route(
        "/api/roleplay/scenarios/draft",
        generate_scenario_draft,
        methods=["POST"],
        response_model=RoleplayScenarioDraftView,
    )
    router.add_api_route(
        "/api/translation/arabic",
        translate_arabic,
        methods=["POST"],
        response_model=ArabicTranslationView,
    )
    router.add_api_route(
        "/api/roleplay/sessions/{client_session_id}/escape-route",
        legacy_escape_route,
        methods=["POST"],
        response_model=ArabicTranslationView,
        include_in_schema=False,
    )
    router.add_api_route(
        "/api/roleplay/sessions/{client_session_id}/finalize",
        finalize_session,
        methods=["POST"],
        response_model=RoleplayFinalizeView,
    )
    router.add_api_websocket_route("/ws/chat", websocket_endpoint)
    return router
