"""Public learning-plan service facade composed from cohesive behaviors."""

from .service_attempts import PlpAttemptsMixin
from .service_base import PlpServiceBaseMixin
from .service_document import PlpDocumentMixin
from .service_errors import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
)
from .service_generation import PlpGenerationMixin
from .service_generation_worker import PlpGenerationWorkerMixin
from .service_grading import (
    _decode_job_failure,
    _encode_job_failure,
    _grade_activity,
    _sanitize_content,
)
from .service_identity import _ensure_local_user
from .service_progress import (
    _activity_skill_ids,
    _eligible_pending_lesson_ids,
    _latest_lesson_score,
    _pronunciation_activity_complete,
    _verified_completed_activity_ids,
)
from .service_roleplay import PlpRoleplayMixin
from .service_worker import PlpWorkerMixin


class PlpService(
    PlpServiceBaseMixin,
    PlpRoleplayMixin,
    PlpGenerationMixin,
    PlpAttemptsMixin,
    PlpWorkerMixin,
    PlpGenerationWorkerMixin,
    PlpDocumentMixin,
):
    """Application facade coordinating the learning-plan bounded context."""


plp_service = PlpService()


__all__ = [
    "PlpConflictError",
    "PlpInvalidAttemptError",
    "PlpNotFoundError",
    "PlpService",
    "PlpUnavailableError",
    "plp_service",
]
