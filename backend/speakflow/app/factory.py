from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from speakflow import APP_RELEASE
from speakflow.features.auth.application.errors import (
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from plp.identity import bind_user
from speakflow.features.auth.infrastructure.service import auth_service
from .rate_limit import ProcessSharedRateLimiter as _RateLimiter


_PUBLIC_API_PATHS = {
    "/api/tts",
    "/api/news/image",
}
_UPLOAD_BODY_LIMIT = 16 * 1024 * 1024


class _RequestBodyTooLarge(Exception):
    pass


class _BodyLimitMiddleware:
    """Reject oversized streamed bodies before multipart parsing completes."""

    def __init__(self, app: Any, *, maximum_bytes: int) -> None:
        self.app = app
        self.maximum_bytes = maximum_bytes

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if path not in {"/api/pronunciation", "/api/speaking/transcribe"}:
            await self.app(scope, receive, send)
            return

        response_started = False
        received = 0

        async def limited_receive() -> dict:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.maximum_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: dict) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            response = JSONResponse(
                status_code=413,
                content={"detail": "request body is too large"},
            )
            await response(scope, receive, send)


_rate_limiter = _RateLimiter()


def _rate_limit_rule(method: str, path: str) -> tuple[int, int] | None:
    if path == "/api/auth/signin":
        return 10, 60
    if path in {"/api/auth/signup", "/api/auth/guest"}:
        return 6, 60
    if path == "/api/tts":
        return (30, 60) if method == "GET" else (60, 60)
    if path == "/api/news/image":
        return 30, 60
    if path in {"/api/pronunciation", "/api/speaking/transcribe"}:
        return 20, 60
    return None


def create_application(
    *,
    routers: Iterable[APIRouter] = (),
    lifespan: Any = None,
) -> FastAPI:
    """Build the HTTP application and wire cross-cutting adapters.

    Feature modules own routes and use cases. Authentication context, CORS and
    router composition belong here so the executable entrypoint stays small.
    """

    application = FastAPI(
        title="SpeakFlow Backend",
        version=APP_RELEASE,
        lifespan=lifespan,
    )
    configured_origin_text = os.environ.get("CORS_ORIGINS")
    configured_origins = [
        value.strip()
        for value in (configured_origin_text or "").split(",")
        if value.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured_origins,
        allow_origin_regex=(
            None
            if configured_origin_text is not None
            else r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
        ),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_middleware(
        _BodyLimitMiddleware,
        maximum_bytes=_UPLOAD_BODY_LIMIT,
    )

    for router in routers:
        application.include_router(router)

    @application.middleware("http")
    async def authenticated_user_context(request: Request, call_next):
        path = request.url.path
        if path in {"/api/pronunciation", "/api/speaking/transcribe"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "invalid Content-Length header"},
                    )
                if declared_size < 0:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "invalid Content-Length header"},
                    )
                if declared_size > _UPLOAD_BODY_LIMIT:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "request body is too large"},
                    )
        rule = _rate_limit_rule(request.method, path)
        if rule is not None:
            client_host = request.client.host if request.client else "unknown"
            retry_after = _rate_limiter.retry_after(
                f"{client_host}:{request.method}:{path}",
                limit=rule[0],
                window=rule[1],
            )
            if retry_after:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "too many requests; try again shortly"},
                    headers={"Retry-After": str(retry_after)},
                )
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path.startswith("/api/auth/")
            or (request.method == "GET" and path in _PUBLIC_API_PATHS)
        ):
            return await call_next(request)

        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            return JSONResponse(
                status_code=401,
                content={"detail": "a bearer token is required"},
            )
        try:
            user = await asyncio.to_thread(auth_service.authenticate, token.strip())
        except AuthInvalidCredentialsError as exc:
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        except AuthUnavailableError as exc:
            return JSONResponse(status_code=503, content={"detail": str(exc)})

        with bind_user(user.user_id):
            return await call_next(request)

    return application
