from __future__ import annotations

from dataclasses import dataclass

DOMAIN_ORDER = (
    "vocabulary",
    "grammar",
    "listening",
    "speaking",
    "reading",
    "pronunciation",
    "discourse",
)

FIXED_DAYS_PER_WEEK = 5
FIXED_MINUTES_PER_DAY = 20
TEACHING_DAYS_PER_WEEK = 4
CHECKPOINT_SCORE = 75


@dataclass(frozen=True)
class PlanningSkill:
    """Backward-compatible projection of one reviewed planner skill."""

    id: str
    domain: str
    level: str
    title: str
    description: str
    outcomes: list[str]
