"""Reviewed, deterministic foundations for the PLP v3 weekly mission planner.

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
from enum import Enum
import hashlib
import re
import unicodedata
from types import MappingProxyType
from typing import Iterable, Literal, Mapping, Sequence


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


class LessonRole(str, Enum):
    INPUT_NOTICING = "input_noticing"
    LANGUAGE_TOOLS = "language_tools"
    GUIDED_INTERACTION = "guided_interaction"
    INDEPENDENT_TRANSFER = "independent_transfer"
    CHECKPOINT = "checkpoint"


class FactPolicy(str, Enum):
    """Content boundary inherited by every eventual scenario realization."""

    FICTIONAL_OR_TIMELESS = "fictional_or_timeless"


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
    fact_policy: FactPolicy = FactPolicy.FICTIONAL_OR_TIMELESS
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
    InterestTag("technology", "Technology", ("tech", "computers", "gadgets"), ("technology",)),
    InterestTag("travel", "Travel", ("travelling", "tourism", "journeys"), ("travel", "culture")),
    InterestTag("business", "Business", ("work", "career", "entrepreneurship"), ("work",)),
    InterestTag("education", "Education", ("learning", "study", "university"), ("study",)),
    InterestTag("culture", "Culture", ("arts", "museums", "heritage"), ("culture", "entertainment")),
    InterestTag("science", "Science", ("research", "nature", "space"), ("science",)),
    InterestTag("sports", "Sports", ("sport", "fitness", "football", "soccer"), ("sports",)),
    InterestTag("daily_life", "Daily life", ("everyday", "everyday life", "daily routine"), ("everyday",)),
    InterestTag("entertainment", "Entertainment", ("movies", "films", "games", "gaming"), ("entertainment",)),
    InterestTag("music", "Music", ("songs", "concerts", "musicians"), ("entertainment", "culture")),
    InterestTag("history", "History", ("historical topics", "the past"), ("culture", "study")),
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
            "Keep names, organizations, prices, schedules, and product details fictional.",
            "Do not require outside knowledge or current events.",
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
            "Keep entities and situational details fictional or timeless.",
            "Do not make cultural trivia or current product knowledge necessary for success.",
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
            "Use fictional organizations, events, messages, and device features.",
            "Avoid facts whose truth changes with time and avoid specialist knowledge.",
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
            "All organizations, claims, statistics, events, and product features must be fictional or explicitly supplied.",
            "Do not reward background knowledge, topical familiarity, or one cultural viewpoint.",
            "Keep ambiguity authentic but ensure the required outcome is fully supported by the scenario input.",
        ),
    ),
)


def _outcomes(
    a1: tuple[str, str, str],
    a2: tuple[str, str, str],
    b1: tuple[str, str, str],
    b2: tuple[str, str, str],
) -> tuple[LevelOutcome, ...]:
    return tuple(
        LevelOutcome(level, can_do, product, support)
        for level, (can_do, product, support) in zip(CEFR_LEVELS, (a1, a2, b1, b2), strict=True)
    )


SCENARIO_ARCHETYPES: tuple[ScenarioArchetype, ...] = (
    ScenarioArchetype(
        id="everyday.make_shared_plan",
        title="Make a shared plan",
        context_family="everyday",
        premise="Two or more fictional people need to agree on the time, place, and practical details of a familiar activity.",
        learner_role="participant helping the group reach a workable plan",
        partner_roles=("friend", "neighbor", "club member"),
        setting_slots=("activity", "time options", "place options", "one practical constraint"),
        text_types=("message exchange", "short notice", "simple schedule"),
        compatible_goal_ids=("confident_conversation", "travel_independence", "workplace_communication", "academic_study"),
        compatible_interest_ids=("daily_life", "travel", "culture", "sports", "entertainment"),
        outcomes=_outcomes(
            ("Can choose a time and place for a familiar activity using short expressions.", "a short accepted plan", "visible time/place options and a phrase bank"),
            ("Can exchange simple suggestions and agree on practical arrangements.", "a brief message confirming arrangements", "a short model and optional useful phrases"),
            ("Can compare practical constraints and negotiate a workable shared plan.", "a connected proposal with a reason and confirmation", "a task frame with no model answer"),
            ("Can negotiate arrangements, qualify preferences, and resolve competing constraints.", "a clear agreement that acknowledges alternatives", "outcome criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="everyday.resolve_service_problem",
        title="Resolve an everyday service problem",
        context_family="everyday",
        premise="A fictional local service has made a clear, routine mistake that can be resolved from the supplied record.",
        learner_role="customer explaining the issue and requesting a proportionate solution",
        partner_roles=("service assistant", "receptionist", "support representative"),
        setting_slots=("service type", "expected result", "observed problem", "available remedies"),
        text_types=("receipt", "appointment note", "service dialogue"),
        compatible_goal_ids=("confident_conversation", "travel_independence", "workplace_communication", "exam_preparation"),
        compatible_interest_ids=("daily_life", "travel", "business", "technology"),
        outcomes=_outcomes(
            ("Can state a simple service problem and ask for help.", "a short help request", "a labelled record and fixed request frames"),
            ("Can explain a routine problem and request one clear remedy.", "a brief problem-and-request message", "a phrase bank and explicit remedy options"),
            ("Can describe what went wrong, refer to evidence, and agree on a practical remedy.", "a supported resolution request", "the service record and task criteria"),
            ("Can present a service complaint precisely, evaluate remedies, and negotiate a fair outcome.", "a proportionate negotiated resolution", "the evidence record and outcome criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="travel.compare_journey_options",
        title="Choose a journey option",
        context_family="travel",
        premise="A fictional journey offers several internally consistent options with different times, costs, and constraints.",
        learner_role="traveler choosing and explaining the most suitable option",
        partner_roles=("travel companion", "booking assistant", "host"),
        setting_slots=("fictional destination", "option table", "traveler priorities", "constraint"),
        text_types=("timetable", "booking summary", "travel dialogue"),
        compatible_goal_ids=("travel_independence", "confident_conversation", "exam_preparation"),
        compatible_interest_ids=("travel", "culture", "daily_life"),
        outcomes=_outcomes(
            ("Can identify a suitable journey time and price from a simple list.", "one selected option with a short reason", "icons, labels, and two options"),
            ("Can compare familiar journey options and state a preference.", "a short booking choice", "a clear table and comparison phrases"),
            ("Can evaluate journey options against stated priorities and recommend one.", "a recommendation supported by relevant details", "an option table and task criteria"),
            ("Can weigh competing journey constraints and justify a qualified recommendation.", "a reasoned choice that addresses a trade-off", "evidence table only"),
        ),
    ),
    ScenarioArchetype(
        id="travel.handle_changed_arrangement",
        title="Handle a changed travel arrangement",
        context_family="travel",
        premise="A fictional booking or meeting arrangement changes and the learner must understand the update and choose a next step.",
        learner_role="traveler responding constructively to the change",
        partner_roles=("travel assistant", "host", "travel companion"),
        setting_slots=("original arrangement", "change notice", "available alternatives", "priority"),
        text_types=("change notification", "announcement", "support exchange"),
        compatible_goal_ids=("travel_independence", "confident_conversation", "workplace_communication"),
        compatible_interest_ids=("travel", "culture", "daily_life"),
        outcomes=_outcomes(
            ("Can understand the new time or place and choose a stated alternative.", "a simple confirmed alternative", "highlighted before/after details"),
            ("Can understand a routine change and ask or answer a practical follow-up question.", "a short revised arrangement", "a clear notice and question frames"),
            ("Can explain the effect of a change and arrange a suitable alternative.", "a connected response with a practical next step", "the notice and available alternatives"),
            ("Can assess the consequences of a changed arrangement and negotiate an effective alternative.", "a qualified recovery plan", "source details and outcome criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="work.coordinate_shared_task",
        title="Coordinate a shared task",
        context_family="work",
        premise="A fictional team must divide a familiar task, confirm responsibilities, and meet an internal deadline.",
        learner_role="team member coordinating a clear part of the work",
        partner_roles=("colleague", "team lead", "project partner"),
        setting_slots=("task outcome", "available people", "responsibilities", "fictional deadline"),
        text_types=("team message", "task list", "brief meeting dialogue"),
        compatible_goal_ids=("workplace_communication", "academic_study", "confident_conversation"),
        compatible_interest_ids=("business", "technology", "education", "science"),
        outcomes=_outcomes(
            ("Can identify a simple task and say who does what.", "a short responsibility statement", "a labelled task list and fixed frames"),
            ("Can exchange simple task information and confirm a deadline.", "a brief coordination message", "a task table and useful phrases"),
            ("Can allocate work, explain a constraint, and confirm shared expectations.", "a clear coordination note", "the task brief and outcome checklist"),
            ("Can coordinate responsibilities, anticipate dependencies, and tactfully resolve a constraint.", "a precise team agreement with contingencies", "brief and success criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="work.report_and_solve_problem",
        title="Report a work problem and propose a next step",
        context_family="work",
        premise="A fictional routine task has a documented obstacle, and the learner must report it without inventing missing facts.",
        learner_role="team member giving a useful problem update",
        partner_roles=("colleague", "supervisor", "internal support person"),
        setting_slots=("task", "observed obstacle", "known impact", "possible next steps"),
        text_types=("status update", "internal email", "problem-solving dialogue"),
        compatible_goal_ids=("workplace_communication", "confident_conversation", "exam_preparation"),
        compatible_interest_ids=("business", "technology", "science", "daily_life"),
        outcomes=_outcomes(
            ("Can state that a familiar task has a problem and ask for help.", "a simple problem update", "labelled problem details and sentence frames"),
            ("Can describe a routine work problem and suggest one practical action.", "a short update and suggestion", "a model structure and supplied facts"),
            ("Can report a problem, explain its likely impact, and recommend a supported next step.", "a structured status update", "the evidence record and criteria"),
            ("Can give a precise problem analysis, qualify uncertainty, and compare proportionate responses.", "a concise decision-oriented update", "documented evidence and criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="study.clarify_assignment",
        title="Clarify a learning task",
        context_family="study",
        premise="A fictional course task contains requirements, resources, and one point that needs clarification.",
        learner_role="learner confirming what the task requires",
        partner_roles=("teacher", "classmate", "study adviser"),
        setting_slots=("task type", "requirements", "resource", "ambiguous detail"),
        text_types=("assignment brief", "course message", "clarification exchange"),
        compatible_goal_ids=("academic_study", "exam_preparation", "confident_conversation"),
        compatible_interest_ids=("education", "science", "technology", "culture", "history"),
        outcomes=_outcomes(
            ("Can identify what to do and ask one simple question about a task.", "a short clarification question", "highlighted instruction and a question frame"),
            ("Can understand routine task requirements and confirm a missing detail.", "a brief confirmation exchange", "a structured brief and useful phrases"),
            ("Can summarize task requirements and ask a precise clarification question.", "an accurate task summary and focused question", "the assignment brief and checklist"),
            ("Can interpret detailed requirements, identify ambiguity, and negotiate a clear understanding.", "a concise, justified clarification request", "the complete brief and criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="study.plan_group_project",
        title="Plan a group project",
        context_family="study",
        premise="A fictional study group must select a narrow topic, divide work, and agree on a simple process.",
        learner_role="group member contributing to a workable project plan",
        partner_roles=("classmate", "project partner", "course mentor"),
        setting_slots=("project outcome", "topic options", "roles", "fictional milestones"),
        text_types=("project brief", "planning notes", "group discussion"),
        compatible_goal_ids=("academic_study", "exam_preparation", "workplace_communication", "confident_conversation"),
        compatible_interest_ids=("education", "science", "technology", "culture", "business", "history"),
        outcomes=_outcomes(
            ("Can choose a simple project topic and say one assigned action.", "a basic topic-and-task plan", "two topic options and fixed planning phrases"),
            ("Can make simple project suggestions and agree on roles and dates.", "a short group plan", "a planning table and phrase bank"),
            ("Can compare project choices, divide responsibilities, and explain the sequence of work.", "a connected project proposal", "a brief and planning criteria"),
            ("Can shape a project plan, justify priorities, and respond constructively to competing proposals.", "a coherent negotiated plan with rationale", "project constraints and criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="technology.solve_familiar_issue",
        title="Solve a familiar technology issue",
        context_family="technology",
        premise="A fictional device or service has a small set of supplied symptoms and documented troubleshooting options.",
        learner_role="user explaining the issue and selecting the safest supported step",
        partner_roles=("support assistant", "colleague", "friend"),
        setting_slots=("fictional device", "symptoms", "support note", "possible steps"),
        text_types=("support article", "chat transcript", "status message"),
        compatible_goal_ids=("confident_conversation", "workplace_communication", "academic_study", "exam_preparation"),
        compatible_interest_ids=("technology", "business", "education", "daily_life"),
        outcomes=_outcomes(
            ("Can identify a simple device problem and follow one stated instruction.", "a short problem-and-action response", "pictures or labels and one-step options"),
            ("Can describe a familiar technology problem and choose a documented solution.", "a brief support exchange", "a short support note and phrase bank"),
            ("Can understand a clear problem update and recommend which supplied solution to try first.", "an evidence-based troubleshooting recommendation", "the support evidence and criteria"),
            ("Can evaluate competing explanations, qualify a recommendation, and respond to a counterargument.", "a reasoned troubleshooting plan", "complete fictional case evidence only"),
        ),
    ),
    ScenarioArchetype(
        id="technology.compare_fictional_tools",
        title="Compare fictional tools for a purpose",
        context_family="technology",
        premise="Several fictional tools have explicitly supplied features, limitations, and use conditions.",
        learner_role="user recommending the best fit for a stated need",
        partner_roles=("friend", "colleague", "study partner"),
        setting_slots=("fictional tools", "feature table", "user need", "trade-off"),
        text_types=("feature table", "short review", "recommendation exchange"),
        compatible_goal_ids=("workplace_communication", "academic_study", "confident_conversation", "exam_preparation"),
        compatible_interest_ids=("technology", "business", "education", "science"),
        outcomes=_outcomes(
            ("Can find a named feature and choose a tool for one simple need.", "one choice with a short reason", "two clearly labelled fictional options"),
            ("Can compare familiar features and state which fictional tool suits a clear need.", "a brief comparison and recommendation", "a small feature table and comparison frames"),
            ("Can compare supplied features and limitations to recommend an appropriate tool.", "a supported recommendation", "the feature evidence and outcome criteria"),
            ("Can weigh feature trade-offs, challenge assumptions, and qualify a recommendation for a specific user.", "a nuanced evidence-based recommendation", "the complete fictional specification only"),
        ),
    ),
    ScenarioArchetype(
        id="entertainment.choose_shared_experience",
        title="Choose an entertainment experience",
        context_family="entertainment",
        premise="A fictional set of films, games, performances, or music events offers contrasting genres and practical details.",
        learner_role="participant helping another person choose a suitable option",
        partner_roles=("friend", "club member", "visitor"),
        setting_slots=("fictional options", "preferences", "content descriptions", "practical constraint"),
        text_types=("programme", "fictional review snippets", "recommendation dialogue"),
        compatible_goal_ids=("confident_conversation", "travel_independence", "exam_preparation"),
        compatible_interest_ids=("entertainment", "culture", "travel", "daily_life", "music"),
        outcomes=_outcomes(
            ("Can identify a type of entertainment and say a simple preference.", "one choice and preference", "pictures or labels and fixed preference frames"),
            ("Can compare simple descriptions and suggest an entertainment option.", "a short suggestion with a reason", "three fictional options and phrase support"),
            ("Can summarize preferences and recommend a suitable fictional experience.", "a supported recommendation", "supplied descriptions and criteria"),
            ("Can evaluate contrasting fictional reviews and negotiate a choice that accommodates different tastes.", "a qualified joint recommendation", "the review evidence and outcome criteria only"),
        ),
    ),
    ScenarioArchetype(
        id="entertainment.discuss_fictional_story",
        title="Discuss a fictional story",
        context_family="entertainment",
        premise="A self-contained fictional story extract presents a character choice or interpretation supported entirely by the text.",
        learner_role="reader or viewer explaining an interpretation",
        partner_roles=("friend", "book-club member", "classmate"),
        setting_slots=("fictional extract", "character goal", "key event", "interpretive question"),
        text_types=("story synopsis", "dialogue extract", "discussion exchange"),
        compatible_goal_ids=("confident_conversation", "academic_study", "exam_preparation"),
        compatible_interest_ids=("entertainment", "culture", "education"),
        outcomes=_outcomes(
            ("Can identify a character, place, and main event in a very short fictional story.", "a short factual response", "a brief illustrated or labelled extract"),
            ("Can describe a main event and give a simple reaction to a fictional story.", "a short summary and opinion", "a short extract and response frames"),
            ("Can summarize a fictional story choice and support an interpretation with textual detail.", "an evidence-linked interpretation", "the extract and question criteria"),
            ("Can compare plausible interpretations and defend a nuanced reading with evidence from the fictional text.", "a qualified textual interpretation", "the self-contained extract only"),
        ),
    ),
    ScenarioArchetype(
        id="sports.organize_activity",
        title="Organize a sports or fitness activity",
        context_family="sports",
        premise="A fictional group must choose a suitable activity, assign simple roles, and account for stated access or safety needs.",
        learner_role="participant helping create an inclusive activity plan",
        partner_roles=("teammate", "club organizer", "friend"),
        setting_slots=("activity options", "participant needs", "venue details", "fictional schedule"),
        text_types=("club notice", "availability table", "planning dialogue"),
        compatible_goal_ids=("confident_conversation", "travel_independence", "workplace_communication"),
        compatible_interest_ids=("sports", "daily_life", "travel"),
        outcomes=_outcomes(
            ("Can choose an activity and state a time or simple need.", "a basic activity arrangement", "labelled options and fixed phrases"),
            ("Can discuss simple activity preferences and agree on familiar arrangements.", "a short inclusive plan", "a schedule and phrase bank"),
            ("Can compare participants' needs and organize a practical group activity.", "a supported activity plan", "supplied needs and outcome criteria"),
            ("Can negotiate an inclusive activity plan, balancing preferences, access, and practical constraints.", "a reasoned plan with accommodations", "all fictional case details only"),
        ),
    ),
    ScenarioArchetype(
        id="sports.recap_fictional_event",
        title="Explain a fictional sports event",
        context_family="sports",
        premise="A fictional event record supplies all actions, results, participant comments, and timing needed for a recap.",
        learner_role="participant or reporter explaining what happened and why it mattered",
        partner_roles=("friend", "club member", "fictional interviewer"),
        setting_slots=("fictional event", "event timeline", "result", "participant comments"),
        text_types=("event timeline", "fictional match report", "interview extract"),
        compatible_goal_ids=("confident_conversation", "academic_study", "exam_preparation"),
        compatible_interest_ids=("sports", "entertainment", "daily_life"),
        outcomes=_outcomes(
            ("Can identify who took part and the result of a short fictional event.", "a simple result statement", "a labelled event card"),
            ("Can give a short sequence of key events and a simple reaction.", "a brief ordered recap", "a clear timeline and sequencing phrases"),
            ("Can summarize a fictional event, connect cause and result, and report a participant view.", "a connected evidence-based recap", "the event record and criteria"),
            ("Can synthesize a fictional event record, distinguish report from interpretation, and qualify an evaluation.", "a balanced analytical recap", "the complete supplied record only"),
        ),
    ),
    ScenarioArchetype(
        id="culture.plan_fictional_visit",
        title="Plan a fictional cultural visit",
        context_family="culture",
        premise="A fictional venue or community programme supplies stable descriptions, opening slots, access information, and event options.",
        learner_role="visitor planning a suitable experience",
        partner_roles=("friend", "visitor assistant", "group member"),
        setting_slots=("fictional venue", "programme", "visitor priorities", "access constraint"),
        text_types=("visitor guide", "programme", "planning exchange"),
        compatible_goal_ids=("travel_independence", "confident_conversation", "academic_study", "exam_preparation"),
        compatible_interest_ids=("culture", "travel", "entertainment", "education", "music"),
        outcomes=_outcomes(
            ("Can find a time, place, and activity in a simple fictional visitor guide.", "a simple visit choice", "labels, icons, and two options"),
            ("Can use a short guide to suggest a suitable cultural activity.", "a brief visit suggestion", "a small programme and useful phrases"),
            ("Can compare programme details and recommend a visit that meets stated priorities.", "a supported itinerary recommendation", "the fictional guide and criteria"),
            ("Can synthesize programme and access information to negotiate a well-justified cultural itinerary.", "a qualified itinerary with trade-offs", "the complete fictional programme only"),
        ),
    ),
    ScenarioArchetype(
        id="science.explain_supplied_observation",
        title="Explain a supplied observation",
        context_family="science",
        premise="A fictional classroom or community investigation provides a complete observation record without requiring specialist knowledge.",
        learner_role="learner describing the pattern and its supported explanation",
        partner_roles=("study partner", "teacher", "project teammate"),
        setting_slots=("accessible topic", "fictional observation table", "comparison", "supported explanation options"),
        text_types=("observation log", "simple chart description", "discussion exchange"),
        compatible_goal_ids=("academic_study", "exam_preparation", "workplace_communication", "confident_conversation"),
        compatible_interest_ids=("science", "education", "technology", "daily_life"),
        outcomes=_outcomes(
            ("Can identify a simple change or difference in a supplied observation.", "a short observation statement", "labels, visuals, and fixed comparison frames"),
            ("Can describe a simple pattern and connect it to a supplied reason.", "a brief pattern-and-reason explanation", "a small observation table and phrase bank"),
            ("Can summarize a supplied pattern, distinguish observation from explanation, and support a conclusion.", "an evidence-linked explanation", "the complete accessible record and criteria"),
            ("Can evaluate the limits of a supplied observation and present a qualified evidence-based explanation.", "a cautious analytical explanation", "the self-contained record and outcome criteria only"),
        ),
    ),
)


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
                raise CatalogValidationError(
                    f"{kind} alias {value!r} is ambiguous between {existing!r} and {record.id!r}"
                )
            index[key] = record.id
    return MappingProxyType(index)


GOAL_CLUSTER_BY_ID: Mapping[str, GoalCluster] = MappingProxyType(
    {record.id: record for record in GOAL_CLUSTERS}
)
INTEREST_BY_ID: Mapping[str, InterestTag] = MappingProxyType(
    {record.id: record for record in INTEREST_TAGS}
)
LESSON_ROLE_BY_ID: Mapping[LessonRole, LessonRoleSpec] = MappingProxyType(
    {record.role: record for record in LESSON_ROLE_SPECS}
)
CEFR_CONSTRAINT_BY_LEVEL: Mapping[CEFRLevel, CEFRRealizationConstraint] = MappingProxyType(
    {record.level: record for record in CEFR_REALIZATION_CONSTRAINTS}
)
SCENARIO_ARCHETYPE_BY_ID: Mapping[str, ScenarioArchetype] = MappingProxyType(
    {record.id: record for record in SCENARIO_ARCHETYPES}
)

_GOAL_ALIAS_INDEX = _build_alias_index(GOAL_CLUSTERS, kind="goal")
_INTEREST_ALIAS_INDEX = _build_alias_index(INTEREST_TAGS, kind="interest")


def normalize_cefr_level(value: str) -> CEFRLevel:
    if not isinstance(value, str):
        raise CatalogSelectionError("CEFR level must be a string")
    normalized = value.strip().upper()
    if normalized not in CEFR_LEVELS:
        raise CatalogSelectionError(f"unsupported CEFR level: {value!r}")
    return normalized  # type: ignore[return-value]


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

    Exact goal+interest matches rank first, followed by interest matches, then
    goal-relevant neutral transfer and broader goal matches.  This deliberately
    permits occasional neutral/fresh contexts instead of repeating an exposed
    mission merely because the curriculum bank is still small.
    """

    week_number = _validate_week_number(week_number)
    goal_id = normalize_goal(goal)
    interest_id = normalize_interest(interest)
    used = _validated_used_archetype_ids(used_archetype_ids)
    candidates = tuple(
        archetype
        for archetype in SCENARIO_ARCHETYPES
        if archetype.active and archetype.id not in used
    )
    if not candidates:
        raise CatalogSelectionError(
            "no unused scenario archetype remains; start a new catalog cycle or add reviewed archetypes"
        )

    goal_record = GOAL_CLUSTER_BY_ID[goal_id]
    interest_record = INTEREST_BY_ID[interest_id]

    def relevance(archetype: ScenarioArchetype) -> tuple[int, int]:
        goal_match = goal_id in archetype.compatible_goal_ids
        interest_match = interest_id in archetype.compatible_interest_ids
        family_match = archetype.context_family in interest_record.context_families
        preferred_for_goal = archetype.context_family in goal_record.preferred_context_families
        if goal_match and (interest_match or family_match):
            tier = 0
        elif interest_match or family_match:
            tier = 1
        elif goal_match and preferred_for_goal:
            tier = 2
        elif goal_match:
            tier = 3
        elif preferred_for_goal:
            tier = 4
        else:
            tier = 5
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
        LessonRole.GUIDED_INTERACTION: (LessonRole.INPUT_NOTICING, LessonRole.LANGUAGE_TOOLS),
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
    # A small generic cycle check protects future edits beyond the expected v3 DAG.
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
        if not all((constraint.scaffold_policy, constraint.learner_output_expectation, constraint.linguistic_range, constraint.discourse_expectation)):
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
        if scenario.fact_policy is not FactPolicy.FICTIONAL_OR_TIMELESS:
            raise CatalogValidationError(f"scenario {scenario.id!r} permits unstable factual content")
        if not all((scenario.title.strip(), scenario.premise.strip(), scenario.learner_role.strip())):
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
            raise CatalogValidationError(
                f"scenario {scenario.id!r} has unknown compatibility IDs: "
                f"goals={sorted(unknown_goals)}, interests={sorted(unknown_interests)}"
            )
        outcome_levels = tuple(outcome.level for outcome in scenario.outcomes)
        if outcome_levels != CEFR_LEVELS:
            raise CatalogValidationError(
                f"scenario {scenario.id!r} must define ordered A1-B2 outcomes"
            )
        for outcome in scenario.outcomes:
            if not outcome.can_do.startswith("Can "):
                raise CatalogValidationError(
                    f"scenario {scenario.id!r} {outcome.level} outcome is not a can-do statement"
                )
            if not outcome.mission_product.strip() or not outcome.permitted_support.strip():
                raise CatalogValidationError(
                    f"scenario {scenario.id!r} {outcome.level} outcome is incomplete"
                )
        for goal_id in scenario.compatible_goal_ids:
            goal_coverage[goal_id] += 1
        for interest_id in scenario.compatible_interest_ids:
            interest_coverage[interest_id] += 1

    required_broad_families = {
        "everyday", "travel", "work", "study", "technology", "entertainment", "sports"
    }
    if not required_broad_families <= covered_families:
        raise CatalogValidationError(
            f"scenario catalog lacks broad families: {sorted(required_broad_families - covered_families)}"
        )
    if any(count < 2 for count in goal_coverage.values()):
        raise CatalogValidationError(f"every goal needs at least two scenario archetypes: {goal_coverage}")
    if any(count < 2 for count in interest_coverage.values()):
        raise CatalogValidationError(
            f"every interest needs at least two scenario archetypes: {interest_coverage}"
        )


_validate_catalog()


__all__ = (
    "CEFRLevel",
    "CEFR_LEVELS",
    "ContextFamily",
    "CONTEXT_FAMILIES",
    "CatalogValidationError",
    "CatalogSelectionError",
    "LessonRole",
    "FactPolicy",
    "GoalCluster",
    "InterestTag",
    "LessonRoleSpec",
    "CEFRRealizationConstraint",
    "LevelOutcome",
    "ScenarioArchetype",
    "ProfileRotation",
    "WeeklyMissionSelection",
    "GOAL_CLUSTERS",
    "INTEREST_TAGS",
    "LESSON_ROLE_SPECS",
    "CEFR_REALIZATION_CONSTRAINTS",
    "SCENARIO_ARCHETYPES",
    "GOAL_CLUSTER_BY_ID",
    "INTEREST_BY_ID",
    "LESSON_ROLE_BY_ID",
    "CEFR_CONSTRAINT_BY_LEVEL",
    "SCENARIO_ARCHETYPE_BY_ID",
    "normalize_cefr_level",
    "normalize_goal",
    "normalize_interest",
    "normalize_goals",
    "normalize_interests",
    "rotate_profile_dimensions",
    "select_scenario_archetype",
    "select_weekly_mission",
    "lesson_prerequisites",
)
