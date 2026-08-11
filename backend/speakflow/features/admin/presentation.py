"""Thin HTTP adapter for administrator reporting and commands."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request

from speakflow.features.admin.infrastructure.reporting import (
    AdminDataUnavailableError,
    AdminUserNotFoundError,
    get_dashboard_data,
    get_error_feed,
    get_learning_data,
    get_roleplay_data,
    list_audit_events,
    list_users,
    revoke_user_sessions,
)
from speakflow.features.admin.schemas import (
    AdminAuditEventPage,
    AdminDashboardView,
    AdminErrorFeedView,
    AdminLearningView,
    AdminRoleplayView,
    AdminUserPage,
    RevokeSessionsInput,
    RevokeSessionsResult,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except AdminUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AdminDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


router.add_api_route(
    "/dashboard", lambda: _call(get_dashboard_data),
    methods=["GET"], response_model=AdminDashboardView,
)
router.add_api_route(
    "/learning", lambda: _call(get_learning_data),
    methods=["GET"], response_model=AdminLearningView,
)
router.add_api_route(
    "/roleplay", lambda: _call(get_roleplay_data),
    methods=["GET"], response_model=AdminRoleplayView,
)
router.add_api_route(
    "/errors", lambda: _call(get_error_feed),
    methods=["GET"], response_model=AdminErrorFeedView,
)


@router.get("/users", response_model=AdminUserPage)
def users(
    query: str | None = Query(default=None, max_length=320),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict:
    return _call(list_users, query, page, page_size)


@router.get("/audit-events", response_model=AdminAuditEventPage)
def audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict:
    return _call(list_audit_events, page, page_size)


@router.post("/users/{user_id}/revoke", response_model=RevokeSessionsResult)
def revoke(
    user_id: uuid.UUID,
    payload: RevokeSessionsInput,
    request: Request,
) -> dict:
    actor = request.state.authenticated_user
    return _call(
        revoke_user_sessions,
        user_id,
        payload.reason,
        actor.user_id,
    )
