"""Learner identity mapping and safe infrastructure-error translation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .identity import current_user_id as _user_id
from .models import LearnerProfile, User
from .schemas import LearnerProfileInput, LearnerProfileView
from .service_errors import PlpUnavailableError


def _profile_input(profile: LearnerProfile) -> LearnerProfileInput:
    return LearnerProfileInput.model_validate(
        {
            "cefr_level": profile.cefr_level,
            "native_language": profile.native_language,
            "learning_goals": profile.learning_goals,
            "interests": profile.interests,
            "timezone_offset_minutes": profile.timezone_offset_minutes,
        }
    )


def _ensure_local_user(session: Session) -> None:
    if session.get(User, _user_id()) is None:
        session.add(User(id=_user_id(), kind="local_guest"))
        # These mappings deliberately avoid ORM relationships, so force the
        # parent row to exist before inserting its foreign-key-dependent
        # profile in the same transaction.
        session.flush()


def _profile_view(profile: LearnerProfile) -> LearnerProfileView:
    return LearnerProfileView(
        user_id=profile.user_id,
        revision=profile.revision,
        updated_at=profile.updated_at,
        **_profile_input(profile).model_dump(),
    )


def _learner_snapshot(profile: LearnerProfile) -> dict:
    return {
        "native_language": profile.native_language,
        "support_language": profile.support_language,
        "learning_goals": profile.learning_goals,
        "interests": profile.interests,
        "preferred_contexts": profile.preferred_contexts,
        "accent_preference": profile.accent_preference,
        "pronunciation_priorities": profile.pronunciation_priorities,
        "timezone_offset_minutes": profile.timezone_offset_minutes,
    }


def _database_error(exc: Exception) -> PlpUnavailableError:
    return PlpUnavailableError(
        "PLP PostgreSQL is unavailable. Check the backend logs and database migrations."
    )


def _unexpected_worker_error(exc: Exception) -> str:
    return (
        f"Unexpected PLP worker failure ({type(exc).__name__}). "
        "Check the backend log for details."
    )

