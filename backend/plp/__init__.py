"""Personalized learning-plan backend.

The PLP package deliberately keeps curriculum planning, retrieval, generation,
and progress persistence out of the legacy application module.
"""

from .api import router
from .service import plp_service

__all__ = ["plp_service", "router"]
