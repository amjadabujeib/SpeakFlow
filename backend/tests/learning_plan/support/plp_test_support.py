import json
import unittest
import uuid
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import httpx
from openai import RateLimitError
from pydantic import ValidationError

from speakflow.features.learning_plan.engine.audit_generation import audit_generation
from speakflow.features.learning_plan.engine.curated_lessons import get_curated_template
from speakflow.features.learning_plan.engine.database import get_engine, session_scope
from speakflow.features.learning_plan.engine.generator import (
    GenerationError,
    LessonGenerator,
    _lesson_json_schema,
)
from speakflow.features.learning_plan.engine.ingest import _validate_skill_graph
from speakflow.features.learning_plan.engine.lesson_quality import (
    ACTIVITY_BLUEPRINTS,
    _validate_choice,
    _validate_fill_blank,
    _validate_pronunciation,
)
from speakflow.features.learning_plan.engine.models import (
    GenerationJob,
    PlanLesson,
    utc_now,
)
from speakflow.features.learning_plan.engine.planner import PlanningSkill, build_outline
from speakflow.features.learning_plan.engine.retrieval import (
    CurriculumRetriever,
    RetrievedChunk,
)
from speakflow.features.learning_plan.engine.schemas import (
    Activity,
    ActivityAttemptInput,
    LearnerProfileInput,
    PublicLessonContent,
)
from speakflow.features.learning_plan.engine.seed import seed_records
from speakflow.features.learning_plan.engine.service import (
    LearningPlanEngine,
    PlpConflictError,
    PlpInvalidAttemptError,
)
from speakflow.features.learning_plan.engine.service_grading import (
    _grade_activity,
    _sanitize_content,
)
from speakflow.features.learning_plan.engine.service_identity import _ensure_local_user
from speakflow.features.learning_plan.engine.service_progress import (
    _activity_skill_ids,
    _latest_lesson_score,
    _pronunciation_activity_complete,
    _verified_completed_activity_ids,
)


def profile(level="B1"):
    return LearnerProfileInput(
        cefr_level=level,
        native_language="Arabic",
        learning_goals=["Speak confidently", "Communicate at work"],
        interests=["Technology", "Travel"],
    )


def planning_skills():
    _, skills, _ = seed_records()
    return [
        PlanningSkill(
            id=item["id"],
            domain=item["domain"],
            level=item["cefr_level"],
            title=item["title"],
            description=item["description"],
            outcomes=item["outcomes"],
        )
        for item in skills
    ]


__all__ = [name for name in globals() if not name.startswith("__")]
