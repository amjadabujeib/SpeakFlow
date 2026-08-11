from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from speakflow.features.learning_plan.engine.schemas import (
    RoleplayScenarioCreate,
    RoleplayScenarioUpdate,
    RoleplayScenarioView,
    RoleplaySessionStart,
    RoleplaySessionStartView,
    RoleplaySessionView,
    RoleplayTranscriptView,
)
from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
    PlpUnavailableError,
)
from speakflow.features.roleplay.application.service import roleplay_service

router = APIRouter(prefix="/api/roleplay", tags=["roleplay"])


@router.get("/scenarios", response_model=list[RoleplayScenarioView])
def roleplay_scenarios() -> list[RoleplayScenarioView]:
    return _call(roleplay_service.list_scenarios)


@router.post(
    "/scenarios",
    response_model=RoleplayScenarioView,
    status_code=status.HTTP_201_CREATED,
)
def create_roleplay_scenario(
    payload: RoleplayScenarioCreate,
) -> RoleplayScenarioView:
    return _call(roleplay_service.create_scenario, payload)


@router.put(
    "/scenarios/{scenario_id}",
    response_model=RoleplayScenarioView,
)
def update_roleplay_scenario(
    scenario_id: Annotated[
        str,
        Path(pattern=r"^[a-z0-9_\-]{2,100}$"),
    ],
    payload: RoleplayScenarioUpdate,
) -> RoleplayScenarioView:
    return _call(roleplay_service.update_scenario, scenario_id, payload)


@router.delete(
    "/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_roleplay_scenario(
    scenario_id: Annotated[
        str,
        Path(pattern=r"^[a-z0-9_\-]{2,100}$"),
    ],
) -> None:
    return _call(roleplay_service.delete_scenario, scenario_id)


@router.post(
    "/sessions/start",
    response_model=RoleplaySessionStartView,
    status_code=status.HTTP_201_CREATED,
)
def start_roleplay_session(
    payload: RoleplaySessionStart,
) -> RoleplaySessionStartView:
    return _call(roleplay_service.start_session, payload)


@router.get("/sessions", response_model=list[RoleplaySessionView])
def roleplay_sessions(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RoleplaySessionView]:
    return _call(roleplay_service.list_sessions, limit)


@router.get(
    "/sessions/{client_session_id}/transcript",
    response_model=RoleplayTranscriptView,
)
def roleplay_transcript(
    client_session_id: Annotated[
        str,
        Path(pattern=r"^[a-zA-Z0-9_\-]{8,80}$"),
    ],
) -> RoleplayTranscriptView:
    return _call(roleplay_service.transcript, client_session_id)


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
