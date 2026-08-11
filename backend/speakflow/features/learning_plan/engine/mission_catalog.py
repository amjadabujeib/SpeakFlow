"""Selection and validation operations for the reviewed mission catalog."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType

from .mission_archetypes import SCENARIO_ARCHETYPES
from .mission_catalog_models import (
    CEFR_LEVELS,
    CEFR_REALIZATION_CONSTRAINTS,
    CONTEXT_FAMILIES,
    GOAL_CLUSTERS,
    INTEREST_TAGS,
    LESSON_ROLE_SPECS,
    CatalogSelectionError,
    CatalogValidationError,
    CEFRLevel,
    CEFRRealizationConstraint,
    FactPolicy,
    GoalCluster,
    InterestTag,
    LessonRole,
    LessonRoleSpec,
    ProfileRotation,
    ScenarioArchetype,
    WeeklyMissionSelection,
    normalize_cefr_level,
)
from .mission_catalog_public import MISSION_CATALOG_EXPORTS


def _normalize_label(value: str) -> str:
    if not isinstance(value, str):
        raise CatalogSelectionError("catalog labels must be strings")
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _build_alias_index(records: Sequence[GoalCluster | InterestTag], *, kind: str) -> Mapping[str, str]:
    index: dict[str, str] = {}
    for record in records:
        values = (record.id, record.id.replace("_", " "), record.label, *record.aliases)
        for value in values:
            key = _normalize_label(value)
            if not key:
                raise CatalogValidationError(f"{kind} {record.id!r} has an empty alias")
            existing = index.get(key)
            if existing is not None and existing != record.id:
                raise CatalogValidationError(f"{kind} alias {value!r} is ambiguous between {existing!r} and {record.id!r}")
            index[key] = record.id
    return MappingProxyType(index)


GOAL_CLUSTER_BY_ID: Mapping[str, GoalCluster] = MappingProxyType({record.id: record for record in GOAL_CLUSTERS})
INTEREST_BY_ID: Mapping[str, InterestTag] = MappingProxyType({record.id: record for record in INTEREST_TAGS})
LESSON_ROLE_BY_ID: Mapping[LessonRole, LessonRoleSpec] = MappingProxyType({record.role: record for record in LESSON_ROLE_SPECS})
CEFR_CONSTRAINT_BY_LEVEL: Mapping[CEFRLevel, CEFRRealizationConstraint] = MappingProxyType({record.level: record for record in CEFR_REALIZATION_CONSTRAINTS})
SCENARIO_ARCHETYPE_BY_ID: Mapping[str, ScenarioArchetype] = MappingProxyType({record.id: record for record in SCENARIO_ARCHETYPES})

_GOAL_ALIAS_INDEX = _build_alias_index(GOAL_CLUSTERS, kind="goal")
_INTEREST_ALIAS_INDEX = _build_alias_index(INTEREST_TAGS, kind="interest")


def normalize_goal(value: str) -> str:
    """Map a supported onboarding label/alias to a stable goal-cluster ID."""

    key = _normalize_label(value)
    try:
        return _GOAL_ALIAS_INDEX[key]
    except KeyError as exc:
        raise CatalogSelectionError(f"unsupported learning goal: {value!r}") from exc


def normalize_interest(value: str) -> str:
    """Map a supported onboarding label/alias to a stable interest ID."""

    key = _normalize_label(value)
    try:
        return _INTEREST_ALIAS_INDEX[key]
    except KeyError as exc:
        raise CatalogSelectionError(f"unsupported learner interest: {value!r}") from exc


def normalize_goals(values: Iterable[str]) -> tuple[str, ...]:
    return _normalize_distinct(values, normalize_goal, kind="learning goal")


def normalize_interests(values: Iterable[str]) -> tuple[str, ...]:
    return _normalize_distinct(values, normalize_interest, kind="learner interest")


def _normalize_distinct(
    values: Iterable[str],
    normalizer,
    *,
    kind: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise CatalogSelectionError(f"{kind}s must be a sequence, not one string")
    result: list[str] = []
    for value in values:
        normalized = normalizer(value)
        if normalized not in result:
            result.append(normalized)
    if not result:
        raise CatalogSelectionError(f"at least one {kind} is required")
    return tuple(result)


def rotate_profile_dimensions(
    goals: Iterable[str],
    interests: Iterable[str],
    *,
    week_number: int,
    stable_seed: str = "",
) -> ProfileRotation:
    """Rotate both selected dimensions so secondary choices affect the plan.

    The stored selection order is respected.  With no seed, week one selects
    the first value, week two the second, and so on.  A stable learner/plan seed
    changes only the starting offset, never the rotation cadence.
    """

    week_number = _validate_week_number(week_number)
    normalized_goals = normalize_goals(goals)
    normalized_interests = normalize_interests(interests)
    goal_index = (_stable_offset(stable_seed, "goal", len(normalized_goals)) + week_number - 1) % len(normalized_goals)
    interest_index = (_stable_offset(stable_seed, "interest", len(normalized_interests)) + week_number - 1) % len(normalized_interests)
    return ProfileRotation(
        week_number=week_number,
        goal_id=normalized_goals[goal_index],
        interest_id=normalized_interests[interest_index],
    )


def select_scenario_archetype(
    *,
    goal: str,
    interest: str,
    week_number: int,
    used_archetype_ids: Iterable[str] = (),
    stable_seed: str = "",
) -> ScenarioArchetype:
    """Select a relevant active archetype without repeating a used one.

    A scenario whose context family directly matches the learner's interest
    ranks above one that can merely be themed with that interest. Goal and
    interest compatibility still combine before single-dimension fallbacks.
    This permits fresh transfer contexts without letting broad theme tags
    routinely displace a directly relevant scenario.
    """

    week_number = _validate_week_number(week_number)
    goal_id = normalize_goal(goal)
    interest_id = normalize_interest(interest)
    used = _validated_used_archetype_ids(used_archetype_ids)
    candidates = tuple(archetype for archetype in SCENARIO_ARCHETYPES if archetype.active and archetype.id not in used)
    if not candidates:
        raise CatalogSelectionError("no unused scenario archetype remains; start a new catalog cycle or add reviewed archetypes")

    goal_record = GOAL_CLUSTER_BY_ID[goal_id]
    interest_record = INTEREST_BY_ID[interest_id]

    def relevance(archetype: ScenarioArchetype) -> tuple[int, int]:
        goal_match = goal_id in archetype.compatible_goal_ids
        interest_match = interest_id in archetype.compatible_interest_ids
        family_match = archetype.context_family in interest_record.context_families
        preferred_for_goal = archetype.context_family in goal_record.preferred_context_families
        if goal_match and family_match:
            tier = 0
        elif goal_match and interest_match:
            tier = 1
        elif family_match:
            tier = 2
        elif interest_match:
            tier = 3
        elif goal_match and preferred_for_goal:
            tier = 4
        elif goal_match:
            tier = 5
        elif preferred_for_goal:
            tier = 6
        else:
            tier = 7
        # A stable digest avoids process-random hash ordering while allowing
        # different plans/weeks to select different equally relevant records.
        digest = _stable_digest_int(
            stable_seed,
            str(week_number),
            goal_id,
            interest_id,
            archetype.id,
        )
        return tier, digest

    return min(candidates, key=relevance)


def select_weekly_mission(
    *,
    cefr_level: str,
    goals: Iterable[str],
    interests: Iterable[str],
    week_number: int,
    used_archetype_ids: Iterable[str] = (),
    stable_seed: str = "",
) -> WeeklyMissionSelection:
    """Select the deterministic reviewed framing records for one week."""

    level = normalize_cefr_level(cefr_level)
    rotation = rotate_profile_dimensions(
        goals,
        interests,
        week_number=week_number,
        stable_seed=stable_seed,
    )
    archetype = select_scenario_archetype(
        goal=rotation.goal_id,
        interest=rotation.interest_id,
        week_number=rotation.week_number,
        used_archetype_ids=used_archetype_ids,
        stable_seed=stable_seed,
    )
    return WeeklyMissionSelection(
        week_number=rotation.week_number,
        cefr_level=level,
        goal=GOAL_CLUSTER_BY_ID[rotation.goal_id],
        interest=INTEREST_BY_ID[rotation.interest_id],
        archetype=archetype,
        outcome=archetype.outcome_for(level),
        realization_constraints=CEFR_CONSTRAINT_BY_LEVEL[level],
    )


def lesson_prerequisites(role: LessonRole | str) -> tuple[LessonRole, ...]:
    """Return the direct (not transitive) prerequisites for a lesson role."""

    try:
        normalized = role if isinstance(role, LessonRole) else LessonRole(role)
    except (TypeError, ValueError) as exc:
        raise CatalogSelectionError(f"unsupported lesson role: {role!r}") from exc
    return LESSON_ROLE_BY_ID[normalized].prerequisite_roles


def _validate_week_number(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CatalogSelectionError("week_number must be a positive integer")
    return value


def _stable_digest_int(*parts: str) -> int:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _stable_offset(seed: str, dimension: str, length: int) -> int:
    if not isinstance(seed, str):
        raise CatalogSelectionError("stable_seed must be a string")
    if not seed or length == 1:
        return 0
    return _stable_digest_int(seed, dimension) % length


def _validated_used_archetype_ids(values: Iterable[str]) -> frozenset[str]:
    if isinstance(values, (str, bytes)):
        raise CatalogSelectionError("used_archetype_ids must be a sequence")
    result: set[str] = set()
    for value in values:
        if not isinstance(value, str) or value not in SCENARIO_ARCHETYPE_BY_ID:
            raise CatalogSelectionError(f"unknown used scenario archetype: {value!r}")
        result.add(value)
    return frozenset(result)


def _validate_catalog() -> None:
    identifier = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)*$")

    def unique_ids(records, kind: str) -> None:
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise CatalogValidationError(f"duplicate {kind} IDs")
        for record_id in ids:
            if not identifier.fullmatch(record_id):
                raise CatalogValidationError(f"invalid {kind} ID: {record_id!r}")

    unique_ids(GOAL_CLUSTERS, "goal")
    unique_ids(INTEREST_TAGS, "interest")
    unique_ids(SCENARIO_ARCHETYPES, "scenario")
    if len(GOAL_CLUSTER_BY_ID) != len(GOAL_CLUSTERS):
        raise CatalogValidationError("goal index lost duplicate records")
    if len(INTEREST_BY_ID) != len(INTEREST_TAGS):
        raise CatalogValidationError("interest index lost duplicate records")
    if len(SCENARIO_ARCHETYPE_BY_ID) != len(SCENARIO_ARCHETYPES):
        raise CatalogValidationError("scenario index lost duplicate records")

    valid_families = set(CONTEXT_FAMILIES)
    for goal in GOAL_CLUSTERS:
        if not goal.label.strip() or not goal.communicative_functions or not goal.planning_rationale.strip():
            raise CatalogValidationError(f"goal {goal.id!r} is incomplete")
        if not goal.preferred_context_families or not set(goal.preferred_context_families) <= valid_families:
            raise CatalogValidationError(f"goal {goal.id!r} has invalid context families")
    for interest in INTEREST_TAGS:
        if not interest.label.strip() or not interest.context_families:
            raise CatalogValidationError(f"interest {interest.id!r} is incomplete")
        if not set(interest.context_families) <= valid_families:
            raise CatalogValidationError(f"interest {interest.id!r} has invalid context families")

    expected_roles = set(LessonRole)
    if set(LESSON_ROLE_BY_ID) != expected_roles:
        raise CatalogValidationError("lesson-role catalog must contain every role exactly once")
    if LESSON_ROLE_BY_ID[LessonRole.INPUT_NOTICING].prerequisite_roles:
        raise CatalogValidationError("input/noticing must be a root lesson")
    if LESSON_ROLE_BY_ID[LessonRole.LANGUAGE_TOOLS].prerequisite_roles:
        raise CatalogValidationError("language tools must be a root lesson")
    expected_dependencies = {
        LessonRole.GUIDED_INTERACTION: (
            LessonRole.INPUT_NOTICING,
            LessonRole.LANGUAGE_TOOLS,
        ),
        LessonRole.INDEPENDENT_TRANSFER: (LessonRole.GUIDED_INTERACTION,),
        LessonRole.CHECKPOINT: (LessonRole.INDEPENDENT_TRANSFER,),
    }
    for spec in LESSON_ROLE_SPECS:
        if spec.day_number < 1 or not spec.purpose.strip() or not spec.support_policy.strip():
            raise CatalogValidationError(f"lesson role {spec.role.value!r} is incomplete")
        if len(spec.prerequisite_roles) != len(set(spec.prerequisite_roles)):
            raise CatalogValidationError(f"lesson role {spec.role.value!r} repeats a prerequisite")
        if spec.role in spec.prerequisite_roles:
            raise CatalogValidationError(f"lesson role {spec.role.value!r} depends on itself")
    for role, prerequisites in expected_dependencies.items():
        if LESSON_ROLE_BY_ID[role].prerequisite_roles != prerequisites:
            raise CatalogValidationError(f"lesson role {role.value!r} has an invalid DAG edge")
    # A small generic cycle check protects future edits to the expected DAG.
    visiting: set[LessonRole] = set()
    visited: set[LessonRole] = set()

    def visit(role: LessonRole) -> None:
        if role in visiting:
            raise CatalogValidationError("lesson-role prerequisites contain a cycle")
        if role in visited:
            return
        visiting.add(role)
        for prerequisite in LESSON_ROLE_BY_ID[role].prerequisite_roles:
            visit(prerequisite)
        visiting.remove(role)
        visited.add(role)

    for lesson_role in LessonRole:
        visit(lesson_role)

    if set(CEFR_CONSTRAINT_BY_LEVEL) != set(CEFR_LEVELS):
        raise CatalogValidationError("CEFR constraint catalog must contain A1, A2, B1, and B2")
    previous: CEFRRealizationConstraint | None = None
    for level in CEFR_LEVELS:
        constraint = CEFR_CONSTRAINT_BY_LEVEL[level]
        low, high = constraint.input_word_range
        if low < 1 or high < low:
            raise CatalogValidationError(f"invalid input range for {level}")
        numeric_limits = (
            constraint.maximum_sentence_words,
            constraint.maximum_dialogue_turns,
            constraint.maximum_new_lexical_items,
            constraint.maximum_explicit_language_targets,
        )
        if any(value < 1 for value in numeric_limits):
            raise CatalogValidationError(f"invalid realization limit for {level}")
        if not all(
            (
                constraint.scaffold_policy,
                constraint.learner_output_expectation,
                constraint.linguistic_range,
                constraint.discourse_expectation,
            )
        ):
            raise CatalogValidationError(f"incomplete realization language for {level}")
        if len(constraint.writer_guardrails) < 3:
            raise CatalogValidationError(f"{level} needs at least three writer guardrails")
        if previous is not None:
            if low < previous.input_word_range[0] or high < previous.input_word_range[1]:
                raise CatalogValidationError("CEFR input ranges must increase monotonically")
            if constraint.maximum_sentence_words < previous.maximum_sentence_words:
                raise CatalogValidationError("CEFR sentence limit must increase monotonically")
        previous = constraint

    covered_families: set[str] = set()
    goal_coverage = {goal.id: 0 for goal in GOAL_CLUSTERS}
    interest_coverage = {interest.id: 0 for interest in INTEREST_TAGS}
    for scenario in SCENARIO_ARCHETYPES:
        covered_families.add(scenario.context_family)
        if scenario.context_family not in valid_families:
            raise CatalogValidationError(f"scenario {scenario.id!r} has an invalid family")
        if scenario.fact_policy is not FactPolicy.REAL_WORLD_WITH_SUPPLIED_EVIDENCE:
            raise CatalogValidationError(f"scenario {scenario.id!r} lacks the real-world evidence policy")
        if not all(
            (
                scenario.title.strip(),
                scenario.premise.strip(),
                scenario.learner_role.strip(),
            )
        ):
            raise CatalogValidationError(f"scenario {scenario.id!r} is incomplete")
        tuple_fields = (
            scenario.partner_roles,
            scenario.setting_slots,
            scenario.text_types,
            scenario.compatible_goal_ids,
            scenario.compatible_interest_ids,
        )
        if any(not field for field in tuple_fields):
            raise CatalogValidationError(f"scenario {scenario.id!r} has an empty required tuple")
        if any(len(field) != len(set(field)) for field in tuple_fields):
            raise CatalogValidationError(f"scenario {scenario.id!r} repeats catalog values")
        unknown_goals = set(scenario.compatible_goal_ids) - set(GOAL_CLUSTER_BY_ID)
        unknown_interests = set(scenario.compatible_interest_ids) - set(INTEREST_BY_ID)
        if unknown_goals or unknown_interests:
            raise CatalogValidationError(f"scenario {scenario.id!r} has unknown compatibility IDs: goals={sorted(unknown_goals)}, interests={sorted(unknown_interests)}")
        outcome_levels = tuple(outcome.level for outcome in scenario.outcomes)
        if outcome_levels != CEFR_LEVELS:
            raise CatalogValidationError(f"scenario {scenario.id!r} must define ordered A1-B2 outcomes")
        for outcome in scenario.outcomes:
            if not outcome.can_do.startswith("Can "):
                raise CatalogValidationError(f"scenario {scenario.id!r} {outcome.level} outcome is not a can-do statement")
            if not outcome.mission_product.strip() or not outcome.permitted_support.strip():
                raise CatalogValidationError(f"scenario {scenario.id!r} {outcome.level} outcome is incomplete")
        for goal_id in scenario.compatible_goal_ids:
            goal_coverage[goal_id] += 1
        for interest_id in scenario.compatible_interest_ids:
            interest_coverage[interest_id] += 1

    required_broad_families = {
        "everyday",
        "travel",
        "work",
        "study",
        "technology",
        "entertainment",
        "sports",
    }
    if not required_broad_families <= covered_families:
        raise CatalogValidationError(f"scenario catalog lacks broad families: {sorted(required_broad_families - covered_families)}")
    if any(count < 2 for count in goal_coverage.values()):
        raise CatalogValidationError(f"every goal needs at least two scenario archetypes: {goal_coverage}")
    if any(count < 2 for count in interest_coverage.values()):
        raise CatalogValidationError(f"every interest needs at least two scenario archetypes: {interest_coverage}")


_validate_catalog()


__all__ = MISSION_CATALOG_EXPORTS
