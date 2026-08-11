import threading
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from speakflow.features.learning_plan.engine.generator import GenerationError
from speakflow.features.learning_plan.engine.models import (
    GenerationJob,
    LearningPlan,
    PlanLesson,
    PlanRevision,
)
from speakflow.features.learning_plan.engine.retrieval import (
    CurriculumRetriever,
    RetrievalError,
)
from speakflow.features.learning_plan.engine.schemas import GenerationView
from speakflow.features.learning_plan.engine.service import (
    LearningPlanEngine,
    PlpConflictError,
)
from speakflow.features.learning_plan.engine.service_grading import (
    _decode_job_failure,
    _encode_job_failure,
)


def _context_for(session):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    return context


def _scalar_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


__all__ = [name for name in globals() if not name.startswith("__")]
