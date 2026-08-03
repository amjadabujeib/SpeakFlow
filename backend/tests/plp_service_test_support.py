import threading
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from plp.models import (
    GenerationJob,
    LearningPlan,
    PlanLesson,
    PlanRevision,
)
from plp.generator import GenerationError
from plp.retrieval import CurriculumRetriever, RetrievalError
from plp.schemas import GenerationView
from plp.service import (
    PlpConflictError,
    PlpService,
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
