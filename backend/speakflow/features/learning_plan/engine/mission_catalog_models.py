"""Reviewed, deterministic foundations for the weekly mission planner.

This module deliberately contains no lesson prose, answer keys, persistence,
retrieval, or model calls.  It answers the smaller planning question: given a
learner's selected goals and interests, which reviewed scenario archetype and
CEFR realization envelope should frame a week?

The records are immutable so a planner can safely include their identifiers in
an immutable ``WeeklyBrief``.  Selection is pure and stable across processes;
Python's randomized ``hash()`` is never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

CEFRLevel = Literal["A1", "A2", "B1", "B2"]
CEFR_LEVELS: tuple[CEFRLevel, ...] = ("A1", "A2", "B1", "B2")

ContextFamily = Literal[
    "everyday",
    "travel",
    "work",
    "study",
    "technology",
    "entertainment",
    "sports",
    "culture",
    "science",
]
CONTEXT_FAMILIES: tuple[ContextFamily, ...] = (
    "everyday",
    "travel",
    "work",
    "study",
    "technology",
    "entertainment",
    "sports",
    "culture",
    "science",
)


class CatalogValidationError(ValueError):
    """Raised when reviewed catalog data violates its internal contract."""


class CatalogSelectionError(ValueError):
    """Raised when profile data cannot select a valid catalog record."""


def normalize_cefr_level(value: str) -> CEFRLevel:
    if not isinstance(value, str):
        raise CatalogSelectionError("CEFR level must be a string")
    normalized = value.strip().upper()
    if normalized not in CEFR_LEVELS:
        raise CatalogSelectionError(f"unsupported CEFR level: {value!r}")
    return normalized  # type: ignore[return-value]


class LessonRole(StrEnum):
    INPUT_NOTICING = "input_noticing"
    LANGUAGE_TOOLS = "language_tools"
    GUIDED_INTERACTION = "guided_interaction"
    INDEPENDENT_TRANSFER = "independent_transfer"
    CHECKPOINT = "checkpoint"


class FactPolicy(StrEnum):
    """Content boundary inherited by every eventual scenario realization."""

    REAL_WORLD_WITH_SUPPLIED_EVIDENCE = "real_world_with_supplied_evidence"


@dataclass(frozen=True, slots=True)
class GoalCluster:
    id: str
    label: str
    aliases: tuple[str, ...]
    communicative_functions: tuple[str, ...]
    preferred_context_families: tuple[ContextFamily, ...]
    planning_rationale: str


@dataclass(frozen=True, slots=True)
class InterestTag:
    id: str
    label: str
    aliases: tuple[str, ...]
    context_families: tuple[ContextFamily, ...]


@dataclass(frozen=True, slots=True)
class LessonRoleSpec:
    role: LessonRole
    day_number: int
    prerequisite_roles: tuple[LessonRole, ...]
    purpose: str
    support_policy: str
    independently_scored: bool


@dataclass(frozen=True, slots=True)
class CEFRRealizationConstraint:
    level: CEFRLevel
    input_word_range: tuple[int, int]
    maximum_sentence_words: int
    maximum_dialogue_turns: int
    maximum_new_lexical_items: int
    maximum_explicit_language_targets: int
    scaffold_policy: str
    learner_output_expectation: str
    linguistic_range: str
    discourse_expectation: str
    writer_guardrails: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LevelOutcome:
    level: CEFRLevel
    can_do: str
    mission_product: str
    permitted_support: str


@dataclass(frozen=True, slots=True)
class ScenarioArchetype:
    id: str
    title: str
    context_family: ContextFamily
    premise: str
    learner_role: str
    partner_roles: tuple[str, ...]
    setting_slots: tuple[str, ...]
    text_types: tuple[str, ...]
    compatible_goal_ids: tuple[str, ...]
    compatible_interest_ids: tuple[str, ...]
    outcomes: tuple[LevelOutcome, ...]
    fact_policy: FactPolicy = FactPolicy.REAL_WORLD_WITH_SUPPLIED_EVIDENCE
    active: bool = True

    def outcome_for(self, level: CEFRLevel) -> LevelOutcome:
        """Return this scenario's reviewed outcome for ``level``."""

        normalized_level = normalize_cefr_level(level)
        for outcome in self.outcomes:
            if outcome.level == normalized_level:
                return outcome
        # Import-time validation makes this unreachable for catalog records.
        raise CatalogSelectionError(
            f"scenario {self.id!r} has no {normalized_level} outcome"
        )


@dataclass(frozen=True, slots=True)
class ProfileRotation:
    """The one goal and one interest selected to frame a numbered week."""

    week_number: int
    goal_id: str
    interest_id: str


@dataclass(frozen=True, slots=True)
class WeeklyMissionSelection:
    """A reviewed scenario choice ready to be copied into a WeeklyBrief."""

    week_number: int
    cefr_level: CEFRLevel
    goal: GoalCluster
    interest: InterestTag
    archetype: ScenarioArchetype
    outcome: LevelOutcome
    realization_constraints: CEFRRealizationConstraint


GOAL_CLUSTERS: tuple[GoalCluster, ...] = (
    GoalCluster(
        id="confident_conversation",
        label="Speak confidently",
        aliases=("speaking confidence", "conversation", "speak english confidently"),
        communicative_functions=(
            "start_and_sustain_exchange",
            "clarify_and_confirm",
            "express_preference",
        ),
        preferred_context_families=("everyday", "entertainment", "sports", "culture"),
        planning_rationale="Prioritize useful interaction moves and intelligible, increasingly independent responses.",
    ),
    GoalCluster(
        id="travel_independence",
        label="Travel independently",
        aliases=("travel", "english for travel", "independent travel"),
        communicative_functions=(
            "request_information",
            "compare_options",
            "resolve_practical_problem",
        ),
        preferred_context_families=("travel", "everyday", "culture"),
        planning_rationale="Prioritize practical choices, service exchanges, and recovery from routine travel problems.",
    ),
    GoalCluster(
        id="workplace_communication",
        label="Communicate at work",
        aliases=("work", "business english", "english for work", "career"),
        communicative_functions=(
            "coordinate_task",
            "report_progress_or_problem",
            "propose_and_justify",
        ),
        preferred_context_families=("work", "technology", "everyday"),
        planning_rationale="Prioritize clear coordination, professional problem reports, and proportionate recommendations.",
    ),
    GoalCluster(
        id="academic_study",
        label="Study in English",
        aliases=("study", "academic english", "education", "university"),
        communicative_functions=(
            "follow_instructions",
            "summarize_information",
            "participate_in_group_work",
        ),
        preferred_context_families=("study", "science", "technology"),
        planning_rationale="Prioritize understanding tasks, organizing information, and contributing to collaborative study.",
    ),
    GoalCluster(
        id="exam_preparation",
        label="Prepare for exams",
        aliases=("exam", "exams", "test preparation", "english exam"),
        communicative_functions=(
            "identify_main_and_supporting_information",
            "produce_controlled_response",
            "organize_extended_response",
        ),
        preferred_context_families=("study", "science", "culture", "everyday"),
        planning_rationale="Prioritize transferable comprehension and response organization without teaching to invented exam facts.",
    ),
)


INTEREST_TAGS: tuple[InterestTag, ...] = (
    InterestTag(
        "technology", "Technology", ("tech", "computers", "gadgets"), ("technology",)
    ),
    InterestTag(
        "travel", "Travel", ("travelling", "tourism", "journeys"), ("travel", "culture")
    ),
    InterestTag(
        "business", "Business", ("work", "career", "entrepreneurship"), ("work",)
    ),
    InterestTag(
        "education", "Education", ("learning", "study", "university"), ("study",)
    ),
    InterestTag(
        "culture",
        "Culture",
        ("arts", "museums", "heritage"),
        ("culture", "entertainment"),
    ),
    InterestTag("science", "Science", ("research", "nature", "space"), ("science",)),
    InterestTag(
        "sports", "Sports", ("sport", "fitness", "football", "soccer"), ("sports",)
    ),
    InterestTag(
        "daily_life",
        "Daily life",
        ("everyday", "everyday life", "daily routine"),
        ("everyday",),
    ),
    InterestTag(
        "entertainment",
        "Entertainment",
        ("movies", "films", "games", "gaming"),
        ("entertainment",),
    ),
    InterestTag(
        "music",
        "Music",
        ("songs", "concerts", "musicians"),
        ("entertainment", "culture"),
    ),
    InterestTag(
        "history", "History", ("historical topics", "the past"), ("culture", "study")
    ),
)


LESSON_ROLE_SPECS: tuple[LessonRoleSpec, ...] = (
    LessonRoleSpec(
        LessonRole.INPUT_NOTICING,
        1,
        (),
        "Understand a short mission input, notice useful language, and retrieve one due item when available.",
        "Models, glosses, replay, and explicit noticing prompts are allowed.",
        False,
    ),
    LessonRoleSpec(
        LessonRole.LANGUAGE_TOOLS,
        2,
        (),
        "Build the small set of language forms and interaction moves needed for the mission.",
        "Concise explanations, worked examples, and contrastive L1 hints are allowed.",
        False,
    ),
    LessonRoleSpec(
        LessonRole.GUIDED_INTERACTION,
        3,
        (LessonRole.INPUT_NOTICING, LessonRole.LANGUAGE_TOOLS),
        "Combine both preparation strands in scaffolded recognition, completion, and construction.",
        "Prompts, constrained choices, and fading cues are allowed.",
        True,
    ),
    LessonRoleSpec(
        LessonRole.INDEPENDENT_TRANSFER,
        4,
        (LessonRole.GUIDED_INTERACTION,),
        "Transfer the same can-do skill to a changed situation with materially less support.",
        "No answer-revealing model may appear before the independent response.",
        True,
    ),
    LessonRoleSpec(
        LessonRole.CHECKPOINT,
        5,
        (LessonRole.INDEPENDENT_TRANSFER,),
        "Demonstrate the weekly mission in a fresh equivalent context and retrieve one due earlier skill.",
        "Only task instructions and accessibility support are allowed before submission.",
        True,
    ),
)


CEFR_REALIZATION_CONSTRAINTS: tuple[CEFRRealizationConstraint, ...] = (
    CEFRRealizationConstraint(
        level="A1",
        input_word_range=(35, 80),
        maximum_sentence_words=10,
        maximum_dialogue_turns=6,
        maximum_new_lexical_items=6,
        maximum_explicit_language_targets=2,
        scaffold_policy="Use visible models, concrete choices, repetition, and one-step instructions.",
        learner_output_expectation="Produce words, fixed expressions, and one or two short linked sentences for an immediate need.",
        linguistic_range="Very frequent concrete language, present/simple forms, basic questions, and transparent cognate-safe wording.",
        discourse_expectation="Use basic sequencing or coordination such as and, but, then, and because only when modelled.",
        writer_guardrails=(
            "Prefer recognizable real-world subjects and use only stable facts stated in the supplied input.",
            "Label prices, schedules, availability, and service details as practice-scenario data unless a source supplies them.",
            "Make referents explicit and avoid idioms, sarcasm, and dense noun phrases.",
        ),
    ),
    CEFRRealizationConstraint(
        level="A2",
        input_word_range=(70, 140),
        maximum_sentence_words=14,
        maximum_dialogue_turns=8,
        maximum_new_lexical_items=8,
        maximum_explicit_language_targets=3,
        scaffold_policy="Use short models, optional phrase banks, clear paragraphing, and two-step instructions.",
        learner_output_expectation="Produce a short connected message or exchange that handles a familiar routine situation.",
        linguistic_range="Frequent everyday language with simple past/future reference, modals, comparison, and routine requests.",
        discourse_expectation="Link a short sequence with common time, reason, contrast, and result markers.",
        writer_guardrails=(
            "Use real places, works, activities, or tools while keeping every assessed fact in the supplied input.",
            "Do not make cultural trivia, live travel rules, or current product knowledge necessary for success.",
            "Prefer explicit implications over trick questions or subtle irony.",
        ),
    ),
    CEFRRealizationConstraint(
        level="B1",
        input_word_range=(120, 220),
        maximum_sentence_words=18,
        maximum_dialogue_turns=10,
        maximum_new_lexical_items=10,
        maximum_explicit_language_targets=4,
        scaffold_policy="Provide a concise task frame and optional functional-language bank, then fade support for transfer.",
        learner_output_expectation="Produce connected language that explains a problem, compares options, and gives a supported next step.",
        linguistic_range="Familiar standard language with controlled complex sentences, modals, conditionals, and reported information.",
        discourse_expectation="Organize main points and supporting reasons with clear reference, contrast, sequence, and consequence.",
        writer_guardrails=(
            "Prefer real organizations, events, works, and tools only when the needed facts are supplied or durably established.",
            "Mark volatile operational details as simulated and avoid specialist background knowledge.",
            "Make every inference recoverable from the supplied input.",
        ),
    ),
    CEFRRealizationConstraint(
        level="B2",
        input_word_range=(180, 320),
        maximum_sentence_words=24,
        maximum_dialogue_turns=12,
        maximum_new_lexical_items=12,
        maximum_explicit_language_targets=5,
        scaffold_policy="Give outcome criteria and optional planning support; withhold model answers until after independent work.",
        learner_output_expectation="Produce a clear, detailed response that weighs alternatives, qualifies a position, and responds to another perspective.",
        linguistic_range="Broad standard language with varied complex clauses, stance, hedging, reformulation, and precise functional expressions.",
        discourse_expectation="Develop an argument or solution coherently, signal stance and qualification, and manage counterpoints.",
        writer_guardrails=(
            "Real organizations, claims, statistics, events, and product features require explicit supplied evidence.",
            "Do not reward background knowledge, topical familiarity, or one cultural viewpoint.",
            "Keep ambiguity authentic but ensure the required outcome is fully supported by the scenario input.",
        ),
    ),
)
