"""Reviewed scenario archetypes used by the deterministic mission catalog."""

from .mission_archetypes_core import CORE_SCENARIO_ARCHETYPES
from .mission_archetypes_extended import EXTENDED_SCENARIO_ARCHETYPES

SCENARIO_ARCHETYPES = CORE_SCENARIO_ARCHETYPES + EXTENDED_SCENARIO_ARCHETYPES

# Several IDs retain ``fictional`` for compatibility with persisted plan
# metadata. Their user-facing contracts now require real-world subjects.
