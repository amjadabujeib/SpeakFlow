"""HTTP handlers for roleplay scenario drafting and Arabic translation."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import HTTPException, Path

from speakflow.features.learning_plan.application import learning_plan_service
from speakflow.features.learning_plan.engine.schemas import (
    ArabicTranslationInput,
    ArabicTranslationView,
    RoleplayScenarioDraftInput,
    RoleplayScenarioDraftView,
)
from speakflow.features.learning_plan.engine.service import PlpNotFoundError
from speakflow.features.roleplay.application.roleplay_scenario import (
    _roleplay_scenario_draft,
)

from .evaluation import _arabic_translation_options


async def generate_roleplay_scenario_draft(
    payload: RoleplayScenarioDraftInput,
) -> RoleplayScenarioDraftView:
    try:
        profile = await asyncio.to_thread(learning_plan_service.get_profile)
        level = profile.cefr_level
    except PlpNotFoundError:
        level = "B1"
    return await asyncio.to_thread(_roleplay_scenario_draft, payload, level)


async def translate_arabic(
    payload: ArabicTranslationInput,
) -> ArabicTranslationView:
    try:
        return await asyncio.to_thread(_arabic_translation_options, payload.text)
    except Exception as exc:
        print(f"Arabic translation generation failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Could not create English options right now. Please try again.",
        ) from exc


async def legacy_roleplay_escape_route(
    client_session_id: Annotated[
        str,
        Path(pattern=r"^[a-zA-Z0-9_\-]{8,80}$"),
    ],
    payload: ArabicTranslationInput,
) -> ArabicTranslationView:
    del client_session_id
    return await translate_arabic(payload)
