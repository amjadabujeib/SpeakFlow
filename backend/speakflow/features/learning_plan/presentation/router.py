from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from speakflow.features.learning_plan.application import (
    learning_plan_lifecycle,
    learning_plan_service,
)
from speakflow.features.learning_plan.engine.schemas import (
    ActivityAttemptInput,
    ActivityAttemptResult,
    AdaptationProposalView,
    GenerationAccepted,
    GenerationCreateInput,
    GenerationView,
    LearnerProfileInput,
    LearnerProfileView,
    LocalLearnerResetResult,
    PlpDocument,
)
from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
)

router = APIRouter(prefix="/api", tags=["personalized-learning-plan"])


@router.get("/plp/health")
def plp_health() -> JSONResponse:
    state = learning_plan_lifecycle.health()
    ready = (
        state.get("database") == "ready"
        and state.get("curriculum") == "ready"
        and state.get("worker") is True
    )
    if ready:
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "degraded"})


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
    return _call(learning_plan_service.save_profile, payload)


@router.get("/learners/local/profile", response_model=LearnerProfileView)
def get_local_profile() -> LearnerProfileView:
    return _call(learning_plan_service.get_profile)


@router.delete("/learners/local", response_model=LocalLearnerResetResult)
def reset_local_learner() -> LocalLearnerResetResult:
    return _call(learning_plan_service.reset_learner)


@router.post(
    "/plp/generations",
    response_model=GenerationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_plan(payload: GenerationCreateInput | None = None) -> GenerationAccepted:
    return _call(
        learning_plan_service.create_generation,
        bool(payload and payload.regenerate),
    )


@router.get("/plp/generations/latest", response_model=GenerationView)
def latest_generation_status() -> GenerationView:
    return _call(learning_plan_service.latest_generation)


@router.get("/plp/generations/{job_id}", response_model=GenerationView)
def generation_status(job_id: UUID) -> GenerationView:
    return _call(learning_plan_service.generation, job_id)


@router.post("/plp/generations/{job_id}/retry", response_model=GenerationView)
def retry_generation(job_id: UUID) -> GenerationView:
    return _call(learning_plan_service.retry_generation, job_id)


@router.get("/plp/active", response_model=PlpDocument)
def active_plan() -> PlpDocument:
    return _call(learning_plan_service.active_document)


@router.post(
    "/plp/activities/{activity_id}/attempts",
    response_model=ActivityAttemptResult,
)
def submit_activity_attempt(
    activity_id: str, payload: ActivityAttemptInput
) -> ActivityAttemptResult:
    return _call(learning_plan_service.record_attempt, activity_id, payload)


@router.get(
    "/plp/adaptation-proposals", response_model=list[AdaptationProposalView]
)
def adaptation_proposals() -> list[AdaptationProposalView]:
    return _call(learning_plan_service.adaptation_proposals)


@router.post(
    "/plp/adaptation-proposals",
    response_model=AdaptationProposalView,
    status_code=status.HTTP_201_CREATED,
)
def create_adaptation_proposal() -> AdaptationProposalView:
    return _call(learning_plan_service.create_adaptation_proposal)


@router.post("/plp/adaptation-proposals/{proposal_id}/approve")
def approve_adaptation(proposal_id: UUID) -> dict:
    return _call(learning_plan_service.decide_adaptation, proposal_id, True)


@router.post("/plp/adaptation-proposals/{proposal_id}/reject")
def reject_adaptation(proposal_id: UUID) -> dict:
    return _call(learning_plan_service.decide_adaptation, proposal_id, False)


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
