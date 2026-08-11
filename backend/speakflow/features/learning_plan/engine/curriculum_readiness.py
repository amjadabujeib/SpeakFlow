"""Cheap database-level readiness checks for the reviewed PLP catalog."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .config import SUPPORTED_LEVELS
from .planner_models import TEACHING_DAYS_PER_WEEK
from .seed import reviewed_seed_checksum


class ActiveSkill(Protocol):
    id: str
    cefr_level: str


@dataclass(frozen=True)
class CurriculumReadiness:
    """Identify levels that cannot safely generate a complete plan."""

    unavailable_levels: tuple[str, ...]
    reviewed_source_current: bool = True

    @property
    def ready(self) -> bool:
        return self.reviewed_source_current and not self.unavailable_levels

    def supports(self, cefr_level: str) -> bool:
        return (
            self.reviewed_source_current and cefr_level not in self.unavailable_levels
        )


def reviewed_source_is_current(stored_checksum: str | None) -> bool:
    return bool(stored_checksum) and stored_checksum == reviewed_seed_checksum()


def assess_curriculum(
    active_skills: Iterable[ActiveSkill],
    reviewed_chunk_metadata: Iterable[dict],
    *,
    reviewed_source_current: bool = True,
) -> CurriculumReadiness:
    """Check catalog coverage without embedding queries or model loading."""

    skills_by_level: dict[str, list[ActiveSkill]] = {
        level: [] for level in SUPPORTED_LEVELS
    }
    for skill in active_skills:
        if skill.cefr_level in skills_by_level:
            skills_by_level[skill.cefr_level].append(skill)

    covered_by_level: dict[str, set[str]] = {level: set() for level in SUPPORTED_LEVELS}
    for value in reviewed_chunk_metadata:
        metadata = value if isinstance(value, dict) else {}
        levels = metadata.get("cefr", [])
        skill_ids = metadata.get("skill_ids", [])
        if not isinstance(levels, list) or not isinstance(skill_ids, list):
            continue
        for level in levels:
            if level in covered_by_level:
                covered_by_level[level].update(
                    skill_id for skill_id in skill_ids if isinstance(skill_id, str)
                )

    unavailable: list[str] = []
    for level in SUPPORTED_LEVELS:
        level_skills = skills_by_level[level]
        if len(level_skills) < TEACHING_DAYS_PER_WEEK or any(
            skill.id not in covered_by_level[level] for skill in level_skills
        ):
            unavailable.append(level)
    return CurriculumReadiness(
        unavailable_levels=tuple(unavailable),
        reviewed_source_current=reviewed_source_current,
    )
