from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from datetime import timezone
import os

from plp.database import session_scope, check_database
from speakflow.features.auth.infrastructure.models import User, AuthSession
from speakflow.features.roleplay.infrastructure.models import RoleplaySession
from speakflow.shared.orm import utc_now
from plp.service import plp_service
from plp.models import GenerationJob, PlanLesson
from speakflow.runtime import models as model_runtime
import uuid

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/dashboard")
def get_dashboard_data():
    now = utc_now()

    # 1. Check health
    postgres_status = "healthy"
    try:
        check_database()
    except Exception:
        postgres_status = "error"

    plp_health = plp_service.health()
    groq_quota = "ok" if os.environ.get("GROQ_API_KEY") else "missing"
    ollama_status = "healthy"

    health_status = "healthy"
    if postgres_status == "error":
        health_status = "error"

    # 2. Get User Stats
    try:
        with session_scope() as session:
            total_registered = session.query(func.count(User.id)).filter(User.kind == "registered").scalar() or 0
            total_guests = session.query(func.count(User.id)).filter(User.kind.in_(["guest", "local_guest"])).scalar() or 0

            active_sessions = session.query(func.count(AuthSession.id)).filter(
                AuthSession.expires_at > now,
                AuthSession.revoked_at.is_(None)
            ).scalar() or 0

            recent = session.query(User).order_by(User.created_at.desc()).limit(5).all()
            recent_registrations = [
                {"id": str(u.id), "email": u.email or "guest", "type": u.kind, "created_at": u.created_at.isoformat()}
                for u in recent
            ]

            active_jobs = session.query(func.count(GenerationJob.id)).filter(
                GenerationJob.status.in_(["queued", "generating_initial", "generating_next", "generating_week_one", "generating_future_weeks"])
            ).scalar() or 0

    except Exception as e:
        print(f"Error querying dashboard data: {e}")
        total_registered = 0
        total_guests = 0
        active_sessions = 0
        active_jobs = 0
        recent_registrations = []

    return {
        "health": {
            "status": health_status,
            "postgres": postgres_status,
            "ollama": ollama_status,
            "groq_quota": groq_quota,
            "plp_workers": 1 if plp_health.get("worker") else 0,
            "active_jobs": active_jobs,
            "models": {
                "whisperx": model_runtime.whisper_model is not None,
                "pronunciation": model_runtime.pronunciation_scorer is not None,
                "grammar": model_runtime.gector_model is not None,
                "tts": model_runtime.kokoro_pipeline is not None,
            }
        },
        "users": {
            "total_registered": total_registered,
            "total_guests": total_guests,
            "active_sessions": active_sessions,
            "recent_registrations": recent_registrations,
        }
    }


@router.get("/learning")
def get_learning_data():
    try:
        with session_scope() as session:
            total_lessons = session.query(func.count(PlanLesson.id)).scalar() or 0
            ready = session.query(func.count(PlanLesson.id)).filter(PlanLesson.content_status == "ready").scalar() or 0
            pending = session.query(func.count(PlanLesson.id)).filter(PlanLesson.content_status == "pending").scalar() or 0
            failed = session.query(func.count(PlanLesson.id)).filter(PlanLesson.content_status == "failed").scalar() or 0

            # Job breakdown by status
            job_rows = session.query(GenerationJob.status, func.count(GenerationJob.id)).group_by(GenerationJob.status).all()
            jobs_by_status = {row[0]: row[1] for row in job_rows}

            # Lesson type breakdown
            type_rows = session.query(PlanLesson.lesson_type, func.count(PlanLesson.id)).group_by(PlanLesson.lesson_type).all()
            lessons_by_type = {row[0]: row[1] for row in type_rows}

    except Exception as e:
        print(f"Error querying learning data: {e}")
        total_lessons = ready = pending = failed = 0
        jobs_by_status = {}
        lessons_by_type = {}

    return {
        "lessons": {
            "total": total_lessons,
            "ready": ready,
            "pending": pending,
            "failed": failed,
        },
        "jobs_by_status": jobs_by_status,
        "lessons_by_type": lessons_by_type,
    }


@router.get("/roleplay")
def get_roleplay_data():
    try:
        with session_scope() as session:
            now = utc_now()
            # now is timezone-aware (UTC); today_start must also be tz-aware
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

            total_sessions = session.query(func.count(RoleplaySession.id)).scalar() or 0
            sessions_today = session.query(func.count(RoleplaySession.id)).filter(
                RoleplaySession.created_at >= today_start
            ).scalar() or 0
            active_now = session.query(func.count(RoleplaySession.id)).filter(
                RoleplaySession.status == "active"
            ).scalar() or 0

            # Averages — only over sessions that have scores
            avg_fluency = session.query(func.avg(RoleplaySession.average_fluency)).filter(
                RoleplaySession.average_fluency.isnot(None)
            ).scalar()
            avg_prosody = session.query(func.avg(RoleplaySession.average_prosody)).filter(
                RoleplaySession.average_prosody.isnot(None)
            ).scalar()
            avg_confidence = session.query(func.avg(RoleplaySession.average_word_confidence)).filter(
                RoleplaySession.average_word_confidence.isnot(None)
            ).scalar()
            avg_alignment = session.query(func.avg(RoleplaySession.alignment_coverage)).filter(
                RoleplaySession.alignment_coverage.isnot(None)
            ).scalar()

            # Recent sessions
            recent_rows = session.query(RoleplaySession).order_by(RoleplaySession.created_at.desc()).limit(10).all()
            recent_sessions = [
                {
                    "id": str(s.id),
                    "scenario": s.scenario,
                    "cefr_level": s.cefr_level,
                    "status": s.status,
                    "message_count": s.message_count,
                    "average_fluency": s.average_fluency,
                    "created_at": s.created_at.isoformat(),
                }
                for s in recent_rows
            ]

    except Exception as e:
        print(f"Error querying roleplay data: {e}")
        total_sessions = sessions_today = active_now = 0
        avg_fluency = avg_prosody = avg_confidence = avg_alignment = None
        recent_sessions = []

    return {
        "total_sessions": total_sessions,
        "sessions_today": sessions_today,
        "active_now": active_now,
        "avg_fluency": round(avg_fluency, 1) if avg_fluency is not None else None,
        "avg_prosody": round(avg_prosody, 1) if avg_prosody is not None else None,
        "avg_word_confidence": round(avg_confidence, 1) if avg_confidence is not None else None,
        # alignment_coverage is 0.0–1.0; multiply to express as percentage
        "avg_alignment_coverage": round(avg_alignment * 100, 1) if avg_alignment is not None else None,
        "recent_sessions": recent_sessions,
    }


@router.get("/errors")
def get_error_feed():
    try:
        with session_scope() as session:
            failed_jobs = session.query(GenerationJob).filter(
                GenerationJob.status == "failed"
            ).order_by(GenerationJob.updated_at.desc()).limit(20).all()

            feed = [
                {
                    "job_id": str(j.id),
                    "error": j.error,
                    "attempts": j.attempts,
                    "updated_at": j.updated_at.isoformat(),
                }
                for j in failed_jobs
            ]
    except Exception as e:
        print(f"Error querying error feed: {e}")
        feed = []

    return {"errors": feed}


@router.post("/users/{user_id}/revoke")
def revoke_user_sessions(user_id: uuid.UUID):
    try:
        with session_scope() as session:
            sessions = session.query(AuthSession).filter(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None)
            ).all()
            revoked_count = len(sessions)
            for s in sessions:
                s.revoked_at = utc_now()
        return {"status": "success", "revoked_count": revoked_count}
    except Exception as e:
        print(f"Error revoking sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
