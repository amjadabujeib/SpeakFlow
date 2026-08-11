"""Private persistence engine composed from cohesive behaviors.

Production adapters use the explicit application services in the owning
features. This engine remains importable for focused method-level tests while
the persistence behaviors share one transactional context.
"""

from speakflow.features.roleplay.infrastructure.persistence import PlpRoleplayMixin

from .service_adaptation import PlpAdaptationMixin
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
from .service_pronunciation import PlpPronunciationMixin
from .service_worker import PlpWorkerMixin


class LearningPlanEngine(
    PlpServiceBaseMixin,
    PlpRoleplayMixin,
    PlpGenerationMixin,
    PlpAdaptationMixin,
    PlpPronunciationMixin,
    PlpAttemptsMixin,
    PlpWorkerMixin,
    PlpGenerationWorkerMixin,
    PlpDocumentMixin,
):
    """Internal transactional engine; not a presentation-layer dependency."""


learning_plan_engine = LearningPlanEngine()


__all__ = [
    "LearningPlanEngine",
    "learning_plan_engine",
    "PlpConflictError",
    "PlpInvalidAttemptError",
    "PlpNotFoundError",
    "PlpUnavailableError",
]
