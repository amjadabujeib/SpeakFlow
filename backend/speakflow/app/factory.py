from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute, APIWebSocketRoute

from speakflow.features.auth.application.errors import (
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from plp.identity import bind_user
from speakflow.features.auth.infrastructure.service import auth_service


_PUBLIC_API_PATHS = {
    "/api/tts",
    "/api/news/image",
    "/api/v1/tts",
    "/api/v1/news/image",
}


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
        version="2.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in routers:
        application.include_router(router)

    @application.middleware("http")
    async def authenticated_user_context(request: Request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path.startswith("/api/auth/")
            or path.startswith("/api/v1/auth/")
            or path in _PUBLIC_API_PATHS
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


def mount_versioned_aliases(application: FastAPI) -> None:
    """Expose current feature contracts under ``/api/v1`` during migration.

    Existing unversioned endpoints remain available until the Flutter client
    completes its coordinated migration. Calling this function is idempotent.
    """

    routes = tuple(application.routes)
    existing_paths = {route.path for route in routes}
    existing_http_routes = {
        (route.path, frozenset(route.methods or ()))
        for route in routes
        if isinstance(route, APIRoute)
    }
    http_routes = tuple(route for route in routes if isinstance(route, APIRoute))
    for route in routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            alias = f"/api/v1/{route.path.removeprefix('/api/')}"
            route_key = (alias, frozenset(route.methods or ()))
            if route_key in existing_http_routes:
                continue
            _clone_http_route(application, route, alias, f"v1_{route.name}")
            existing_paths.add(alias)
            existing_http_routes.add(route_key)
        elif isinstance(route, APIWebSocketRoute) and route.path == "/ws/chat":
            alias = "/api/v1/chat/ws"
            if alias not in existing_paths:
                application.add_api_websocket_route(
                    alias,
                    route.endpoint,
                    name="v1_chat_websocket",
                )
                existing_paths.add(alias)

    canonical_paths = [
        ("/api/learners/local/profile", "/api/v1/me/profile"),
        ("/api/learners/local", "/api/v1/me/learning-data"),
        (
            "/api/onboarding/options",
            "/api/v1/learning-plan/onboarding-options",
        ),
    ]
    canonical_paths.extend(
        (
            route.path,
            f"/api/v1/learning-plan/{route.path.removeprefix('/api/plp/')}",
        )
        for route in http_routes
        if route.path.startswith("/api/plp/")
    )
    for source, alias in canonical_paths:
        for route in (item for item in http_routes if item.path == source):
            route_key = (alias, frozenset(route.methods or ()))
            if route_key in existing_http_routes:
                continue
            name = alias.removeprefix("/api/v1/").replace("/", "_")
            _clone_http_route(application, route, alias, f"v1_{name}_{route.name}")
            existing_paths.add(alias)
            existing_http_routes.add(route_key)


def _clone_http_route(
    application: FastAPI,
    route: APIRoute,
    path: str,
    name: str,
) -> None:
    methods = set(route.methods or ()) - {"HEAD", "OPTIONS"}
    application.add_api_route(
        path,
        route.endpoint,
        methods=methods,
        response_model=route.response_model,
        status_code=route.status_code,
        tags=route.tags,
        summary=route.summary,
        description=route.description,
        response_description=route.response_description,
        responses=route.responses,
        deprecated=route.deprecated,
        name=name,
    )
