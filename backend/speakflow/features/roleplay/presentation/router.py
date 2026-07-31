from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from plp.schemas import (
    RoleplayScenarioCreate,
    RoleplayScenarioView,
    RoleplaySessionStart,
    RoleplaySessionStartView,
    RoleplaySessionView,
    RoleplayTranscriptView,
)
from plp.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
    plp_service,
)


router = APIRouter(prefix="/api/roleplay", tags=["roleplay"])


@router.get("/scenarios", response_model=list[RoleplayScenarioView])
def roleplay_scenarios() -> list[RoleplayScenarioView]:
    return _call(plp_service.list_roleplay_scenarios)


@router.post(
    "/scenarios",
    response_model=RoleplayScenarioView,
    status_code=status.HTTP_201_CREATED,
)
def create_roleplay_scenario(
    payload: RoleplayScenarioCreate,
) -> RoleplayScenarioView:
    return _call(plp_service.create_roleplay_scenario, payload)


@router.post(
    "/sessions/start",
    response_model=RoleplaySessionStartView,
    status_code=status.HTTP_201_CREATED,
)
def start_roleplay_session(
    payload: RoleplaySessionStart,
) -> RoleplaySessionStartView:
    return _call(plp_service.start_roleplay_session, payload)


@router.get("/sessions", response_model=list[RoleplaySessionView])
def roleplay_sessions(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RoleplaySessionView]:
    return _call(plp_service.list_roleplay_sessions, limit)


@router.get(
    "/sessions/{client_session_id}/transcript",
    response_model=RoleplayTranscriptView,
)
def roleplay_transcript(client_session_id: str) -> RoleplayTranscriptView:
    return _call(plp_service.get_roleplay_transcript, client_session_id)


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
