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

from plp.audit_generation import audit_generation
from plp.database import get_engine, session_scope
from plp.curated_lessons import get_curated_template
from plp.generator import GenerationError, LessonGenerator, _lesson_json_schema
from plp.ingest import _validate_skill_graph
from plp.lesson_quality import (
    ACTIVITY_BLUEPRINTS,
    _validate_choice,
    _validate_fill_blank,
    _validate_pronunciation,
)
from plp.planner import PlanningSkill, build_outline
from plp.models import GenerationJob, PlanLesson, utc_now
from plp.retrieval import CurriculumRetriever, RetrievedChunk
from plp.schemas import Activity, LearnerProfileInput, PublicLessonContent
from plp.seed import seed_records
from plp.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpService,
    _activity_skill_ids,
    _ensure_local_user,
    _grade_activity,
    _latest_lesson_score,
    _pronunciation_activity_complete,
    _sanitize_content,
    _verified_completed_activity_ids,
)
from plp.schemas import ActivityAttemptInput


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

