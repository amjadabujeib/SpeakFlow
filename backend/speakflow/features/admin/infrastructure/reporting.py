from __future__ import annotations

import logging
import uuid
from datetime import UTC

from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from speakflow.features.admin.infrastructure.health import ollama_status
from speakflow.features.admin.infrastructure.models import AdminAuditEvent
from speakflow.features.auth.infrastructure.models import AuthSession, User
from speakflow.features.learning_plan.application import learning_plan_lifecycle
from speakflow.features.learning_plan.engine.database import (
    check_database,
    session_scope,
)
from speakflow.features.learning_plan.engine.models import GenerationJob, PlanLesson
from speakflow.features.learning_plan.engine.service_grading import _decode_job_failure
from speakflow.features.roleplay.infrastructure.models import RoleplaySession
from speakflow.runtime import models as model_runtime
from speakflow.shared.groq_keys import configured_groq_api_keys
from speakflow.shared.orm import utc_now

logger = logging.getLogger(__name__)

_ACTIVE_JOB_STATUSES = (
    "queued",
    "generating_initial",
    "generating_next",
    "generating_week_one",
    "generating_future_weeks",
)
_SAFE_FAILURE_MESSAGES = {
    "rate_limited": "The generation provider rate-limited this job.",
    "provider_validation": "Provider output did not pass validation.",
    "retrieval": "Curriculum retrieval could not prepare grounded content.",
    "content_validation": "Generated content did not pass validation.",
    "internal": "The job failed because of an internal error.",
}


class AdminDataUnavailableError(RuntimeError):
    """Administrative reporting storage is unavailable."""


class AdminUserNotFoundError(LookupError):
    """The requested administrative user target does not exist."""


def _database_failure(operation: str, exc: Exception) -> AdminDataUnavailableError:
    logger.exception("Admin %s database query failed", operation, exc_info=exc)
    return AdminDataUnavailableError(
        "administrative data is temporarily unavailable"
    )


def get_dashboard_data() -> dict:
    try:
        check_database()
        now = utc_now()
        with session_scope() as session:
            total_registered = session.query(func.count(User.id)).filter(
                User.kind == "registered"
            ).scalar() or 0
            total_guests = session.query(func.count(User.id)).filter(
                User.kind.in_(("guest", "local_guest"))
            ).scalar() or 0
            active_sessions = session.query(func.count(AuthSession.id)).filter(
                AuthSession.expires_at > now,
                AuthSession.revoked_at.is_(None),
            ).scalar() or 0
            recent = session.query(User).order_by(User.created_at.desc()).limit(5).all()
            recent_registrations = [
                {
                    "id": user.id,
                    "email": user.email or "guest",
                    "type": user.kind,
                    "created_at": user.created_at,
                }
                for user in recent
            ]
            active_jobs = session.query(func.count(GenerationJob.id)).filter(
                GenerationJob.status.in_(_ACTIVE_JOB_STATUSES)
            ).scalar() or 0
    except Exception as exc:
        raise _database_failure("dashboard", exc) from exc

    plp_health = learning_plan_lifecycle.health()
    ollama = ollama_status()
    groq = "configured" if configured_groq_api_keys() else "missing"
    worker_count = 1 if plp_health.get("worker") else 0
    model_state = model_runtime.runtime_model_state()
    overall = "healthy"
    curriculum = plp_health.get("curriculum", "unknown")
    if (
        ollama == "error"
        or groq == "missing"
        or worker_count == 0
        or curriculum != "ready"
        or not all(model_state.values())
    ):
        overall = "warning"
    return {
        "health": {
            "status": overall,
            "postgres": "healthy",
            "ollama": ollama,
            "groq": groq,
            "curriculum": curriculum,
            "plp_workers": worker_count,
            "active_jobs": active_jobs,
            "models": model_state,
        },
        "users": {
            "total_registered": total_registered,
            "total_guests": total_guests,
            "active_sessions": active_sessions,
            "recent_registrations": recent_registrations,
        },
    }


def list_users(
    query: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    try:
        now = utc_now()
        with session_scope() as session:
            users_query = session.query(User)
            normalized = " ".join((query or "").split()).strip()
            if normalized:
                escaped = (
                    normalized.casefold()
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                pattern = f"%{escaped}%"
                conditions = [
                    func.lower(func.coalesce(User.email, "")).like(
                        pattern, escape="\\"
                    ),
                    func.lower(func.coalesce(User.display_name, "")).like(
                        pattern, escape="\\"
                    ),
                ]
                try:
                    conditions.append(User.id == uuid.UUID(normalized))
                except ValueError:
                    pass
                users_query = users_query.filter(or_(*conditions))

            total = users_query.with_entities(func.count(User.id)).scalar() or 0
            users = (
                users_query.order_by(User.created_at.desc(), User.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            user_ids = [user.id for user in users]
            active_counts = {}
            if user_ids:
                active_counts = dict(
                    session.query(AuthSession.user_id, func.count(AuthSession.id))
                    .filter(
                        AuthSession.user_id.in_(user_ids),
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > now,
                    )
                    .group_by(AuthSession.user_id)
                    .all()
                )
            items = [
                {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.display_name or "Learner",
                    "kind": user.kind,
                    "is_admin": user.is_admin,
                    "active_sessions": active_counts.get(user.id, 0),
                    "created_at": user.created_at,
                }
                for user in users
            ]
    except SQLAlchemyError as exc:
        raise _database_failure("user directory", exc) from exc
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def list_audit_events(
    page: int = 1,
    page_size: int = 50,
) -> dict:
    try:
        with session_scope() as session:
            events_query = session.query(AdminAuditEvent)
            total = (
                events_query.with_entities(func.count(AdminAuditEvent.id)).scalar()
                or 0
            )
            events = (
                events_query.order_by(
                    AdminAuditEvent.created_at.desc(),
                    AdminAuditEvent.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [
                {
                    "id": event.id,
                    "actor_user_id": event.actor_user_id,
                    "target_user_id": event.target_user_id,
                    "action": event.action,
                    "detail": event.detail,
                    "created_at": event.created_at,
                }
                for event in events
            ]
    except SQLAlchemyError as exc:
        raise _database_failure("audit history", exc) from exc
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def get_learning_data() -> dict:
    try:
        with session_scope() as session:
            total_lessons = session.query(func.count(PlanLesson.id)).scalar() or 0
            ready = session.query(func.count(PlanLesson.id)).filter(
                PlanLesson.content_status == "ready"
            ).scalar() or 0
            pending = session.query(func.count(PlanLesson.id)).filter(
                PlanLesson.content_status == "pending"
            ).scalar() or 0
            failed = session.query(func.count(PlanLesson.id)).filter(
                PlanLesson.content_status == "failed"
            ).scalar() or 0
            job_rows = session.query(
                GenerationJob.status, func.count(GenerationJob.id)
            ).group_by(GenerationJob.status).all()
            type_rows = session.query(
                PlanLesson.lesson_type, func.count(PlanLesson.id)
            ).group_by(PlanLesson.lesson_type).all()
    except SQLAlchemyError as exc:
        raise _database_failure("learning", exc) from exc
    return {
        "lessons": {
            "total": total_lessons,
            "ready": ready,
            "pending": pending,
            "failed": failed,
        },
        "jobs_by_status": dict(job_rows),
        "lessons_by_type": dict(type_rows),
    }


def get_roleplay_data() -> dict:
    try:
        with session_scope() as session:
            now = utc_now()
            today_start = now.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC
            )
            total_sessions = session.query(func.count(RoleplaySession.id)).scalar() or 0
            sessions_today = session.query(func.count(RoleplaySession.id)).filter(
                RoleplaySession.created_at >= today_start
            ).scalar() or 0
            active_now = session.query(func.count(RoleplaySession.id)).filter(
                RoleplaySession.status == "active"
            ).scalar() or 0
            avg_fluency = session.query(
                func.avg(RoleplaySession.average_fluency)
            ).filter(RoleplaySession.average_fluency.isnot(None)).scalar()
            avg_prosody = session.query(
                func.avg(RoleplaySession.average_prosody)
            ).filter(RoleplaySession.average_prosody.isnot(None)).scalar()
            avg_confidence = session.query(
                func.avg(RoleplaySession.average_word_confidence)
            ).filter(RoleplaySession.average_word_confidence.isnot(None)).scalar()
            avg_alignment = session.query(
                func.avg(RoleplaySession.alignment_coverage)
            ).filter(RoleplaySession.alignment_coverage.isnot(None)).scalar()
            recent_rows = session.query(RoleplaySession).order_by(
                RoleplaySession.created_at.desc()
            ).limit(10).all()
            recent_sessions = [
                {
                    "id": item.id,
                    "scenario": item.scenario,
                    "cefr_level": item.cefr_level,
                    "status": item.status,
                    "message_count": item.message_count,
                    "average_fluency": item.average_fluency,
                    "created_at": item.created_at,
                }
                for item in recent_rows
            ]
    except SQLAlchemyError as exc:
        raise _database_failure("roleplay", exc) from exc
    return {
        "total_sessions": total_sessions,
        "sessions_today": sessions_today,
        "active_now": active_now,
        "avg_fluency": round(float(avg_fluency), 1) if avg_fluency is not None else None,
        "avg_prosody": round(float(avg_prosody), 1) if avg_prosody is not None else None,
        "avg_word_confidence": (
            round(float(avg_confidence), 1) if avg_confidence is not None else None
        ),
        "avg_alignment_coverage": (
            round(float(avg_alignment) * 100, 1) if avg_alignment is not None else None
        ),
        "recent_sessions": recent_sessions,
    }


def get_error_feed() -> dict:
    try:
        with session_scope() as session:
            failed_jobs = session.query(GenerationJob).filter(
                GenerationJob.status == "failed"
            ).order_by(GenerationJob.updated_at.desc()).limit(20).all()
            feed = []
            for job in failed_jobs:
                decoded = _decode_job_failure(job.error) or {}
                failure_kind = str(decoded.get("failure_kind") or "internal")
                feed.append(
                    {
                        "job_id": job.id,
                        "failure_kind": failure_kind,
                        "message": _SAFE_FAILURE_MESSAGES.get(
                            failure_kind, _SAFE_FAILURE_MESSAGES["internal"]
                        ),
                        "attempts": job.attempts,
                        "updated_at": job.updated_at,
                    }
                )
    except SQLAlchemyError as exc:
        raise _database_failure("error feed", exc) from exc
    return {"errors": feed}


def revoke_user_sessions(
    user_id: uuid.UUID,
    reason: str,
    actor_user_id: uuid.UUID,
) -> dict:
    try:
        with session_scope() as session:
            target = session.get(User, user_id)
            if target is None:
                raise AdminUserNotFoundError("user was not found")
            now = utc_now()
            sessions = session.query(AuthSession).filter(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            ).all()
            for auth_session in sessions:
                auth_session.revoked_at = now
            audit_event = AdminAuditEvent(
                actor_user_id=actor_user_id,
                target_user_id=user_id,
                action="user_sessions_revoked",
                detail={"reason": reason, "revoked_count": len(sessions)},
            )
            session.add(audit_event)
            session.flush()
            result = {
                "status": "success",
                "revoked_count": len(sessions),
                "audit_event_id": audit_event.id,
            }
    except AdminUserNotFoundError:
        raise
    except SQLAlchemyError as exc:
        raise _database_failure("session revocation", exc) from exc
    return result
