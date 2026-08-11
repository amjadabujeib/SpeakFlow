from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from speakflow.features.auth.application.errors import (
    AuthEmailConflictError,
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from speakflow.features.auth.infrastructure.service import auth_service
from speakflow.features.auth.presentation.schemas import (
    AuthSessionView,
    AuthUserView,
    GuestSessionInput,
    SignInInput,
    SignUpInput,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/signup",
    response_model=AuthSessionView,
    status_code=status.HTTP_201_CREATED,
)
def sign_up(payload: SignUpInput) -> AuthSessionView:
    return _call(auth_service.sign_up, payload)


@router.post("/signin", response_model=AuthSessionView)
def sign_in(payload: SignInInput) -> AuthSessionView:
    return _call(auth_service.sign_in, payload)


@router.post(
    "/guest",
    response_model=AuthSessionView,
    status_code=status.HTTP_201_CREATED,
)
def create_guest(payload: GuestSessionInput) -> AuthSessionView:
    return _call(auth_service.create_guest, payload)


@router.get("/me", response_model=AuthUserView)
def me(authorization: str | None = Header(default=None)) -> AuthUserView:
    return _call(auth_service.authenticate, _bearer_token(authorization))


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(authorization: str | None = Header(default=None)) -> None:
    _call(auth_service.sign_out, _bearer_token(authorization))


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="a bearer token is required")
    return token.strip()


def _call(function, *args):
    try:
        return function(*args)
    except AuthInvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AuthEmailConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
