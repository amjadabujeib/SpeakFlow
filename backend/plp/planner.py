from __future__ import annotations

from dataclasses import dataclass

from .mission_catalog import (
    LESSON_ROLE_SPECS,
    LessonRole,
    WeeklyMissionSelection,
    select_weekly_mission,
)
from .schemas import LearnerProfileInput, next_level


DOMAIN_ORDER = (
    "vocabulary", "grammar", "listening", "speaking", "reading",
    "pronunciation", "discourse",
)

FIXED_DAYS_PER_WEEK = 5
FIXED_MINUTES_PER_DAY = 20
TEACHING_DAYS_PER_WEEK = 4
CHECKPOINT_SCORE = 75
PLANNER_ARCHITECTURE = "mission_v3"


@dataclass(frozen=True)
class PlanningSkill:
    """Backward-compatible projection of one reviewed planner skill."""

    id: str
    domain: str
    level: str
    title: str
    description: str
    outcomes: list[str]


def prioritized_domains(profile: LearnerProfileInput) -> list[str]:
    """Return a stable domain preference used only to order eligible skills.

    A domain is no longer a skill identity.  ``build_outline`` keeps every
    distinct skill record, including multiple skills that share this ordering
    tag; this helper remains public for compatibility with v2 callers.
    """

    text = " ".join(profile.learning_goals).casefold()
    boosts: dict[str, int] = {domain: 0 for domain in DOMAIN_ORDER}
    for word, domains in {
        "speak": ("speaking", "listening", "pronunciation"),
        "conversation": ("speaking", "listening", "discourse"),
        "travel": ("vocabulary", "listening", "speaking"),
        "work": ("speaking", "vocabulary", "reading"),
        "study": ("reading", "grammar", "discourse"),
        "exam": ("grammar", "reading", "listening"),
        "pronunciation": ("pronunciation",),
    }.items():
        if word in text:
            for domain in domains:
                boosts[domain] += 1
    if profile.native_language.casefold() == "arabic":
        # Arabic-L1 focus is inferred rather than asking a novice learner to
        # diagnose their own phonological priorities.
        boosts["pronunciation"] += 1
    return sorted(
        DOMAIN_ORDER,
        key=lambda item: (-boosts[item], DOMAIN_ORDER.index(item)),
    )


def pronunciation_focus_for_native_language(native_language: str) -> list[str]:
    language = native_language.casefold()
    if language == "arabic":
        return [
            "/p/–/b/ and /f/–/v/ contrasts",
            "English /θ/ and /ð/",
            "final consonant clusters",
            "word stress and sentence prominence",
        ]
    return [
        "clear English consonant and vowel contrasts",
        "word stress and sentence prominence",
        "intelligible rhythm",
    ]


def build_outline(
    profile: LearnerProfileInput,
    skills: list[PlanningSkill],
    *,
    priority_skill_ids: list[str] | None = None,
    prerequisites_by_skill: dict[str, list[str]] | None = None,
    mastered_skill_ids: set[str] | None = None,
    variation_seed: str = "",
) -> dict:
    """Build a deterministic four-week mission-v3 outline.

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
    prerequisite_graph = _validated_prerequisites(
        prerequisites_by_skill or {}, skills
    )
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
                prerequisites = [teaching_keys[item] for item in role_spec.prerequisite_roles]
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
        # Keep the v2 checkpoint key stable. Adaptation may preserve a started
        # v2 week verbatim while rebuilding later weeks with this v3 planner;
        # the stable boundary key keeps the next week's prerequisite valid.
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
        "architecture": PLANNER_ARCHITECTURE,
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


def _eligible_skills(
    profile: LearnerProfileInput,
    skills: list[PlanningSkill],
) -> list[PlanningSkill]:
    eligible = [skill for skill in skills if skill.level == profile.cefr_level]
    ids = [skill.id for skill in eligible]
    if len(ids) != len(set(ids)):
        raise ValueError(f"reviewed skill catalog has duplicate IDs for {profile.cefr_level}")
    if len(eligible) < TEACHING_DAYS_PER_WEEK:
        raise ValueError(
            f"reviewed skill catalog needs at least {TEACHING_DAYS_PER_WEEK} "
            f"distinct skills for {profile.cefr_level}; found {len(eligible)}"
        )
    invalid_domains = sorted({skill.domain for skill in eligible} - set(DOMAIN_ORDER))
    if invalid_domains:
        raise ValueError(f"reviewed skill catalog has unsupported domains: {invalid_domains}")
    for skill in eligible:
        if not skill.outcomes or not skill.outcomes[0].strip():
            raise ValueError(f"reviewed skill {skill.id!r} needs at least one outcome")
    return eligible


def _ordered_skills(
    profile: LearnerProfileInput,
    skills: list[PlanningSkill],
) -> list[PlanningSkill]:
    domain_order = prioritized_domains(profile)
    domain_rank = {domain: index for index, domain in enumerate(domain_order)}
    # The ID tie-breaker retains every same-domain micro-skill deterministically
    # instead of the old lossy ``{domain: skill}`` projection.
    return sorted(skills, key=lambda item: (domain_rank[item.domain], item.id))


def _validated_priority_ids(
    values: list[str],
    eligible: list[PlanningSkill],
) -> set[str]:
    eligible_ids = {skill.id for skill in eligible}
    return {value for value in values if value in eligible_ids}


def _take_distinct_skills(
    cycle: list[PlanningSkill],
    *,
    cursor: int,
    count: int,
    allowed_ids: set[str] | None = None,
) -> tuple[list[PlanningSkill], int]:
    chosen: list[PlanningSkill] = []
    chosen_ids: set[str] = set()
    probes = 0
    maximum_probes = len(cycle) * (count + 1)
    while len(chosen) < count and probes < maximum_probes:
        skill = cycle[cursor % len(cycle)]
        cursor += 1
        probes += 1
        if allowed_ids is not None and skill.id not in allowed_ids:
            continue
        if skill.id in chosen_ids:
            continue
        chosen.append(skill)
        chosen_ids.add(skill.id)
    if len(chosen) != count:
        raise ValueError(
            "curriculum graph cannot provide four prerequisite-ready weekly skills"
        )
    return chosen, cursor


def _validated_prerequisites(
    values: dict[str, list[str]],
    skills: list[PlanningSkill],
) -> dict[str, list[str]]:
    known_ids = {skill.id for skill in skills}
    graph: dict[str, list[str]] = {}
    for skill_id, prerequisites in values.items():
        if skill_id not in known_ids:
            raise ValueError(f"prerequisite graph has unknown skill {skill_id}")
        distinct = list(dict.fromkeys(prerequisites))
        unknown = [item for item in distinct if item not in known_ids]
        if unknown:
            raise ValueError(
                f"prerequisite graph for {skill_id} has unknown prerequisites {unknown}"
            )
        if skill_id in distinct:
            raise ValueError(f"skill {skill_id} cannot require itself")
        graph[skill_id] = distinct

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(skill_id: str) -> None:
        if skill_id in visiting:
            raise ValueError(f"skill prerequisite cycle at {skill_id}")
        if skill_id in visited:
            return
        visiting.add(skill_id)
        for prerequisite in graph.get(skill_id, []):
            visit(prerequisite)
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in known_ids:
        visit(skill_id)
    return graph


def _cefr_rank(level: str) -> int:
    order = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
    try:
        return order[level]
    except KeyError as exc:
        raise ValueError(f"unsupported curriculum CEFR level {level!r}") from exc


_ROLE_DOMAIN_PREFERENCES: dict[LessonRole, tuple[str, ...]] = {
    LessonRole.INPUT_NOTICING: (
        "listening", "reading", "vocabulary", "discourse",
        "speaking", "grammar", "pronunciation",
    ),
    LessonRole.LANGUAGE_TOOLS: (
        "grammar", "pronunciation", "vocabulary", "discourse",
        "speaking", "reading", "listening",
    ),
    LessonRole.GUIDED_INTERACTION: (
        "speaking", "listening", "discourse", "grammar",
        "vocabulary", "pronunciation", "reading",
    ),
    LessonRole.INDEPENDENT_TRANSFER: DOMAIN_ORDER,
}


def _assign_skills_to_roles(
    skills: list[PlanningSkill],
) -> dict[LessonRole, PlanningSkill]:
    remaining = list(skills)
    result: dict[LessonRole, PlanningSkill] = {}
    roles = (
        LessonRole.INPUT_NOTICING,
        LessonRole.LANGUAGE_TOOLS,
        LessonRole.GUIDED_INTERACTION,
        LessonRole.INDEPENDENT_TRANSFER,
    )
    for role in roles:
        preferences = _ROLE_DOMAIN_PREFERENCES[role]
        rank = {domain: index for index, domain in enumerate(preferences)}
        selected_index = min(
            range(len(remaining)),
            key=lambda index: (rank[remaining[index].domain], index),
        )
        result[role] = remaining.pop(selected_index)
    return result


def _select_review_skill(
    prior_skill_ids: list[str],
    current_skill_ids: list[str],
    *,
    week_number: int,
) -> list[str]:
    candidates = [
        skill_id for skill_id in prior_skill_ids if skill_id not in current_skill_ids
    ]
    if not candidates:
        return []
    return [candidates[(week_number - 2) % len(candidates)]]


def _teaching_lesson(
    *,
    profile: LearnerProfileInput,
    mission: WeeklyMissionSelection,
    skill: PlanningSkill,
    lesson_key: str,
    role: LessonRole,
    day_number: int,
    prerequisites: list[str | None],
    role_purpose: str,
    skill_prerequisite_ids: list[str],
) -> dict:
    clean_prerequisites = [item for item in prerequisites if item is not None]
    mission_metadata = _mission_metadata(mission)
    return {
        "lesson_key": lesson_key,
        "sequence": day_number,
        "type": skill.domain,
        "estimated_minutes": FIXED_MINUTES_PER_DAY,
        "xp": 20,
        "skill_ids": [skill.id],
        "required_lesson_keys": clean_prerequisites,
        "specification": {
            "architecture": PLANNER_ARCHITECTURE,
            "lesson_role": role.value,
            **mission_metadata,
            "title": _lesson_title(role, mission),
            "description": f"{role_purpose} Focus skill: {skill.description}",
            "objectives": _distinct_strings([mission.outcome.can_do, *skill.outcomes]),
            "domain": skill.domain,
            "cefr_level": profile.cefr_level,
            "topics": [mission.interest.label],
            "contexts": [mission.archetype.context_family],
            "skill_ids": [skill.id],
            "skill_prerequisite_ids": list(skill_prerequisite_ids),
            "review_skill_ids": [],
            "day_number": day_number,
            "learning_stage": role.value,
            "pronunciation_focus": (
                pronunciation_focus_for_native_language(profile.native_language)
                if skill.domain == "pronunciation"
                else []
            ),
            "personalization_reason": (
                f"This week's {mission.goal.label.lower()} goal uses a "
                f"{mission.interest.label.lower()} setting while keeping the "
                f"reviewed {skill.title.lower()} outcome."
            ),
            "selection_reason": (
                "Selected from the prerequisite-ready curriculum frontier; "
                "lower-level prerequisites are covered by placement and same-level "
                "prerequisites by earlier planned or mastered work."
            ),
            "completion_policy": {
                "mode": "required_activities",
                "minimum_score": None,
            },
        },
    }


def _checkpoint_lesson(
    *,
    profile: LearnerProfileInput,
    mission: WeeklyMissionSelection,
    lesson_key: str,
    skill_ids: list[str],
    review_skill_ids: list[str],
    prerequisites: list[str],
) -> dict:
    return {
        "lesson_key": lesson_key,
        "sequence": FIXED_DAYS_PER_WEEK,
        "type": "assessment",
        "estimated_minutes": FIXED_MINUTES_PER_DAY,
        "xp": 35,
        "skill_ids": skill_ids,
        "required_lesson_keys": prerequisites,
        "specification": {
            "architecture": PLANNER_ARCHITECTURE,
            "lesson_role": LessonRole.CHECKPOINT.value,
            **_mission_metadata(mission),
            "title": f"Week {mission.week_number} mission checkpoint",
            "description": (
                "Demonstrate the mission in a fresh equivalent situation without "
                "answer-revealing teaching prompts, plus one prior skill when available."
            ),
            "objectives": [mission.outcome.can_do],
            "domain": "assessment",
            "cefr_level": profile.cefr_level,
            "topics": [mission.interest.label],
            "contexts": [mission.archetype.context_family],
            "skill_ids": skill_ids,
            "review_skill_ids": review_skill_ids,
            "day_number": FIXED_DAYS_PER_WEEK,
            "learning_stage": LessonRole.CHECKPOINT.value,
            "pronunciation_focus": [],
            "personalization_reason": (
                "This checkpoint uses a fresh parallel realization of the weekly "
                "mission and retrieves an earlier skill when one is available."
            ),
            "completion_policy": {
                "mode": "minimum_score",
                "minimum_score": CHECKPOINT_SCORE,
            },
        },
    }


def _mission_metadata(mission: WeeklyMissionSelection) -> dict:
    constraint = mission.realization_constraints
    return {
        "mission": {
            "title": mission.archetype.title,
            "premise": mission.archetype.premise,
            "product": mission.outcome.mission_product,
            "permitted_support": mission.outcome.permitted_support,
        },
        "can_do": mission.outcome.can_do,
        "goal": {
            "id": mission.goal.id,
            "label": mission.goal.label,
        },
        "interest": {
            "id": mission.interest.id,
            "label": mission.interest.label,
        },
        "scenario": {
            "id": mission.archetype.id,
            "title": mission.archetype.title,
            "context_family": mission.archetype.context_family,
            "learner_role": mission.archetype.learner_role,
            "partner_roles": list(mission.archetype.partner_roles),
            "setting_slots": list(mission.archetype.setting_slots),
            "text_types": list(mission.archetype.text_types),
            "fact_policy": mission.archetype.fact_policy.value,
        },
        "cefr_realization": {
            "level": constraint.level,
            "input_word_range": list(constraint.input_word_range),
            "maximum_sentence_words": constraint.maximum_sentence_words,
            "maximum_dialogue_turns": constraint.maximum_dialogue_turns,
            "maximum_new_lexical_items": constraint.maximum_new_lexical_items,
            "maximum_explicit_language_targets": (
                constraint.maximum_explicit_language_targets
            ),
            "scaffold_policy": constraint.scaffold_policy,
            "learner_output_expectation": constraint.learner_output_expectation,
            "linguistic_range": constraint.linguistic_range,
            "discourse_expectation": constraint.discourse_expectation,
            "writer_guardrails": list(constraint.writer_guardrails),
        },
    }


def _lesson_title(role: LessonRole, mission: WeeklyMissionSelection) -> str:
    prefix = {
        LessonRole.INPUT_NOTICING: "Input and noticing",
        LessonRole.LANGUAGE_TOOLS: "Language tools",
        LessonRole.GUIDED_INTERACTION: "Guided interaction",
        LessonRole.INDEPENDENT_TRANSFER: "Independent transfer",
    }[role]
    return f"{prefix}: {mission.archetype.title}"


def _distinct_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
