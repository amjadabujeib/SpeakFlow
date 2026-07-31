from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from plp.schemas import (
    ActivityAttemptInput,
    ActivityAttemptResult,
    AdaptationProposalView,
    GenerationAccepted,
    GenerationView,
    LearnerProfileInput,
    LearnerProfileView,
    LocalLearnerResetResult,
    PlpDocumentV2,
)
from plp.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
    plp_service,
)


router = APIRouter(prefix="/api", tags=["personalized-learning-plan"])


@router.get("/plp/health")
def plp_health() -> dict:
    return plp_service.health()


@router.get("/onboarding/options")
def onboarding_options() -> dict:
    return {
        "cefr_levels": ["A1", "A2", "B1", "B2"],
        "native_languages": ["Arabic", "Kurdish", "Turkish", "French", "Spanish"],
        "learning_goals": [
            "Speak confidently",
            "Travel independently",
            "Communicate at work",
            "Study in English",
            "Prepare for exams",
        ],
        "interests": [
            "Technology",
            "Travel",
            "Business",
            "Education",
            "Culture",
            "Science",
            "Sports",
            "Daily life",
            "Entertainment",
            "Music",
            "History",
        ],
        "schedule": {"days_per_week": 5, "minutes_per_day": 20},
        "personalization_note": (
            "Pronunciation focus is inferred from native language; accent and "
            "learning-context questionnaires are not used."
        ),
    }


@router.put("/learners/local/profile", response_model=LearnerProfileView)
def save_local_profile(payload: LearnerProfileInput) -> LearnerProfileView:
    return _call(plp_service.save_profile, payload)


@router.get("/learners/local/profile", response_model=LearnerProfileView)
def get_local_profile() -> LearnerProfileView:
    return _call(plp_service.get_profile)


@router.delete("/learners/local", response_model=LocalLearnerResetResult)
def reset_local_learner() -> LocalLearnerResetResult:
    return _call(plp_service.reset_local_learner)


@router.post(
    "/plp/generations",
    response_model=GenerationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_plan() -> GenerationAccepted:
    return _call(plp_service.create_generation)


@router.get("/plp/generations/latest", response_model=GenerationView)
def latest_generation_status() -> GenerationView:
    return _call(plp_service.get_latest_generation)


@router.get("/plp/generations/{job_id}", response_model=GenerationView)
def generation_status(job_id: UUID) -> GenerationView:
    return _call(plp_service.get_generation, job_id)


@router.post("/plp/generations/{job_id}/retry", response_model=GenerationView)
def retry_generation(job_id: UUID) -> GenerationView:
    return _call(plp_service.retry_generation, job_id)


@router.get("/plp/active", response_model=PlpDocumentV2)
def active_plan() -> PlpDocumentV2:
    return _call(plp_service.get_active_document)


@router.post(
    "/plp/activities/{activity_id}/attempts",
    response_model=ActivityAttemptResult,
)
def submit_activity_attempt(
    activity_id: str, payload: ActivityAttemptInput
) -> ActivityAttemptResult:
    return _call(plp_service.record_attempt, activity_id, payload)


@router.get(
    "/plp/adaptation-proposals", response_model=list[AdaptationProposalView]
)
def adaptation_proposals() -> list[AdaptationProposalView]:
    return _call(plp_service.list_adaptation_proposals)


@router.post(
    "/plp/adaptation-proposals",
    response_model=AdaptationProposalView,
    status_code=status.HTTP_201_CREATED,
)
def create_adaptation_proposal() -> AdaptationProposalView:
    return _call(plp_service.create_adaptation_proposal)


@router.post("/plp/adaptation-proposals/{proposal_id}/approve")
def approve_adaptation(proposal_id: UUID) -> dict:
    return _call(plp_service.decide_adaptation, proposal_id, True)


@router.post("/plp/adaptation-proposals/{proposal_id}/reject")
def reject_adaptation(proposal_id: UUID) -> dict:
    return _call(plp_service.decide_adaptation, proposal_id, False)


def _call(function, *args):
    try:
        return function(*args)
    except PlpNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlpConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlpInvalidAttemptError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlpUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
