"""Compatibility router for the migrated learning-plan and roleplay APIs."""

from fastapi import APIRouter

from speakflow.features.learning_plan.presentation import (
    router as learning_plan_router,
)
from speakflow.features.roleplay.presentation import router as roleplay_router


router = APIRouter()
router.include_router(learning_plan_router)
router.include_router(roleplay_router)

__all__ = ["router"]
