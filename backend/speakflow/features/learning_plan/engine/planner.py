"""Build deterministic four-week mission outlines."""

from __future__ import annotations

from .mission_catalog import LESSON_ROLE_SPECS, LessonRole, select_weekly_mission
from .planner_models import (
    FIXED_DAYS_PER_WEEK,
    FIXED_MINUTES_PER_DAY,
    TEACHING_DAYS_PER_WEEK,
    PlanningSkill,
)
from .planner_support import (
    _assign_skills_to_roles,
    _cefr_rank,
    _checkpoint_lesson,
    _distinct_strings,
    _eligible_skills,
    _mission_metadata,
    _ordered_skills,
    _select_review_skill,
    _take_distinct_skills,
    _teaching_lesson,
    _validated_prerequisites,
    _validated_priority_ids,
)
from .schemas import LearnerProfileInput, next_level
from .standard import PLP_ARCHITECTURE


def build_outline(
    profile: LearnerProfileInput,
    skills: list[PlanningSkill],
    *,
    priority_skill_ids: list[str] | None = None,
    prerequisites_by_skill: dict[str, list[str]] | None = None,
    mastered_skill_ids: set[str] | None = None,
    variation_seed: str = "",
) -> dict:
    """Build a deterministic four-week weekly-mission outline.

    The reviewed catalog selects one non-repeating scenario and one rotated
    goal/interest per week.  Skill records remain distinct even when several
    share a domain.  Existing domain/activity generation remains possible
    because each teaching lesson retains its selected skill's ``domain`` as
    the stored lesson ``type`` and specification ``domain``.
    """

    eligible = _eligible_skills(profile, skills)
    ordered = _ordered_skills(profile, eligible)
    priority_ids = _validated_priority_ids(priority_skill_ids or [], eligible)
    priority = [skill for skill in ordered if skill.id in priority_ids]
    # Repeating priority records in the deterministic cycle increases their
    # future share without discarding the balanced reviewed catalog.
    skill_cycle = [*priority, *ordered]
    prerequisite_graph = _validated_prerequisites(prerequisites_by_skill or {}, skills)
    current_level_rank = _cefr_rank(profile.cefr_level)
    planned_mastery = {
        skill.id for skill in skills if _cefr_rank(skill.level) < current_level_rank
    }
    planned_mastery.update(mastered_skill_ids or set())

    previous_checkpoint: str | None = None
    cycle_cursor = 0
    prior_skill_ids: list[str] = []
    used_archetype_ids: list[str] = []
    weeks: list[dict] = []

    for week_number in range(1, 5):
        mission = select_weekly_mission(
            cefr_level=profile.cefr_level,
            goals=profile.learning_goals,
            interests=profile.interests,
            week_number=week_number,
            used_archetype_ids=used_archetype_ids,
            stable_seed=variation_seed,
        )
        used_archetype_ids.append(mission.archetype.id)

        ready_ids = {
            skill.id
            for skill in eligible
            if set(prerequisite_graph.get(skill.id, ())).issubset(planned_mastery)
        }
        selected_skills, cycle_cursor = _take_distinct_skills(
            skill_cycle,
            cursor=cycle_cursor,
            count=TEACHING_DAYS_PER_WEEK,
            allowed_ids=ready_ids,
        )
        role_skills = _assign_skills_to_roles(selected_skills)
        lessons: list[dict] = []
        teaching_keys: dict[LessonRole, str] = {}

        for role_spec in LESSON_ROLE_SPECS:
            if role_spec.role is LessonRole.CHECKPOINT:
                continue
            role = role_spec.role
            skill = role_skills[role]
            lesson_key = f"w{week_number:02d}_l{role_spec.day_number:02d}_{role.value}"
            teaching_keys[role] = lesson_key
            if role in (LessonRole.INPUT_NOTICING, LessonRole.LANGUAGE_TOOLS):
                prerequisites = [previous_checkpoint] if previous_checkpoint else []
            else:
                prerequisites = [
                    teaching_keys[item] for item in role_spec.prerequisite_roles
                ]
            lessons.append(
                _teaching_lesson(
                    profile=profile,
                    mission=mission,
                    skill=skill,
                    lesson_key=lesson_key,
                    role=role,
                    day_number=role_spec.day_number,
                    prerequisites=prerequisites,
                    role_purpose=role_spec.purpose,
                    skill_prerequisite_ids=prerequisite_graph.get(skill.id, []),
                )
            )

        current_skill_ids = [
            role_skills[role].id
            for role in (
                LessonRole.INPUT_NOTICING,
                LessonRole.LANGUAGE_TOOLS,
                LessonRole.GUIDED_INTERACTION,
                LessonRole.INDEPENDENT_TRANSFER,
            )
        ]
        review_skill_ids = _select_review_skill(
            prior_skill_ids,
            current_skill_ids,
            week_number=week_number,
        )
        assessed_skill_ids = [*current_skill_ids, *review_skill_ids]
        checkpoint_spec = next(
            item for item in LESSON_ROLE_SPECS if item.role is LessonRole.CHECKPOINT
        )
        # Keep the checkpoint key stable when adaptation preserves a started
        # week and rebuilds later weeks; the next prerequisite remains valid.
        checkpoint_key = (
            f"w{week_number:02d}_l{checkpoint_spec.day_number:02d}_assessment"
        )
        lessons.append(
            _checkpoint_lesson(
                profile=profile,
                mission=mission,
                lesson_key=checkpoint_key,
                skill_ids=assessed_skill_ids,
                review_skill_ids=review_skill_ids,
                # Keep all four direct edges explicit for persistence, client
                # lock-state rendering, and auditing even though the earlier
                # lessons are also transitively required by transfer.
                prerequisites=[
                    teaching_keys[LessonRole.INPUT_NOTICING],
                    teaching_keys[LessonRole.LANGUAGE_TOOLS],
                    teaching_keys[LessonRole.GUIDED_INTERACTION],
                    teaching_keys[LessonRole.INDEPENDENT_TRANSFER],
                ],
            )
        )
        for lesson in lessons:
            lesson["specification"]["variation_seed"] = variation_seed or "default"
        previous_checkpoint = checkpoint_key
        for skill_id in current_skill_ids:
            if skill_id not in prior_skill_ids:
                prior_skill_ids.append(skill_id)
        planned_mastery.update(current_skill_ids)

        week_objectives = _distinct_strings(
            [mission.outcome.can_do]
            + [role_skills[role].outcomes[0] for role in role_skills]
        )
        weeks.append(
            {
                "id": f"week_{week_number:02d}",
                "sequence": week_number,
                "title": f"Week {week_number} · {mission.archetype.title}",
                "description": (
                    f"{mission.outcome.can_do} Five focused lessons move from "
                    "understanding and language support to practice and a fresh check."
                ),
                "objectives": week_objectives,
                "mission": _mission_metadata(mission),
                "units": [
                    {
                        "id": f"unit_{week_number:02d}_01",
                        "sequence": 1,
                        "title": mission.archetype.title,
                        "description": (
                            "Input/noticing and language tools are parallel preparation. "
                            "They unlock guided interaction, transfer, and the checkpoint."
                        ),
                        "objectives": week_objectives,
                        "lessons": lessons,
                    }
                ],
            }
        )

    return {
        "architecture": PLP_ARCHITECTURE,
        "variation_seed": variation_seed or "default",
        "title": f"Your {profile.cefr_level} English missions",
        "description": (
            "A four-week path of coherent, level-adjusted missions selected from "
            "reviewed curriculum and rotated across your goals and interests."
        ),
        "level": {
            "current": profile.cefr_level,
            "target": next_level(profile.cefr_level),
            "label": (
                "Working toward the next stage"
                if profile.cefr_level != "B2"
                else "Strengthening B2 independence"
            ),
        },
        "schedule": {
            "duration_weeks": 4,
            "days_per_week": FIXED_DAYS_PER_WEEK,
            "minutes_per_day": FIXED_MINUTES_PER_DAY,
        },
        "focus_areas": [skill.title for skill in ordered[:4]],
        "weeks": weeks,
    }
