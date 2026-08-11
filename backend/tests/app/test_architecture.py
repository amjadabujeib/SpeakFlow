from __future__ import annotations

import ast
import asyncio
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi import Request

BACKEND_ROOT = Path(__file__).resolve().parents[2]
FEATURE_ROOT = BACKEND_ROOT / "speakflow" / "features"
FORBIDDEN_APPLICATION_IMPORTS = {
    "fastapi",
    "sqlalchemy",
    "openai",
    "ollama",
    "pydantic",
    "requests",
    "torch",
    "transformers",
    "plp",
    "main",
}


class CleanArchitectureDependencyTests(unittest.TestCase):
    def test_backend_root_contains_only_executable_python_entrypoints(self):
        allowed = {"main.py"}
        loose_modules = {
            path.name for path in BACKEND_ROOT.glob("*.py")
        }
        self.assertEqual(loose_modules, allowed)

    def test_legacy_packages_and_runtime_adapters_do_not_regrow(self):
        self.assertFalse((BACKEND_ROOT / "plp").exists())
        runtime_modules = {
            path.name
            for path in (BACKEND_ROOT / "speakflow" / "runtime").glob("*.py")
        }
        self.assertEqual(runtime_modules, {"__init__.py", "models.py"})

    def test_tests_use_explicit_fixture_imports(self):
        violations = []
        for path in (BACKEND_ROOT / "tests").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(
                    alias.name == "*" for alias in node.names
                ):
                    violations.append(str(path.relative_to(BACKEND_ROOT)))
        self.assertEqual(violations, [])

    def test_hand_written_python_files_stay_at_or_below_500_lines(self):
        violations = []
        for path in BACKEND_ROOT.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            if line_count > 500:
                violations.append(f"{path.relative_to(BACKEND_ROOT)}: {line_count}")
        self.assertEqual(
            violations,
            [],
            "Split oversized Python files into cohesive feature modules.",
        )

    def test_application_layer_does_not_depend_on_frameworks_or_adapters(self):
        violations: list[str] = []
        for path in FEATURE_ROOT.glob("*/application/*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.partition(".")[0]
                        if root in FORBIDDEN_APPLICATION_IMPORTS:
                            violations.append(f"{path.name}: {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                if module and module.partition(".")[0] in FORBIDDEN_APPLICATION_IMPORTS:
                    violations.append(f"{path.name}: {module}")
        self.assertEqual(violations, [])

    def test_presentation_adapters_never_import_the_executable_entrypoint(self):
        violations: list[str] = []
        for path in FEATURE_ROOT.glob("*/presentation/*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name == "main" for alias in node.names):
                        violations.append(str(path))
                elif isinstance(node, ast.ImportFrom) and node.module == "main":
                    violations.append(str(path))
        self.assertEqual(violations, [])

    def test_feature_owned_orm_models_share_one_monolith_metadata_registry(self):
        from speakflow.features.auth.infrastructure.models import AuthSession, User
        from speakflow.features.roleplay.infrastructure.models import RoleplaySession
        from speakflow.shared.orm import Base

        self.assertEqual(User.__module__, "speakflow.features.auth.infrastructure.models")
        self.assertEqual(
            AuthSession.__module__,
            "speakflow.features.auth.infrastructure.models",
        )
        self.assertEqual(
            RoleplaySession.__module__,
            "speakflow.features.roleplay.infrastructure.models",
        )
        self.assertIs(User.metadata, Base.metadata)
        self.assertIs(RoleplaySession.metadata, Base.metadata)


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        main.app.state.runtime_model_loading = "lazy"
        cls.routes = {
            (route.path, method)
            for route in main.app.routes
            for method in (getattr(route, "methods", None) or {"WEBSOCKET"})
        }

    def test_authenticated_user_routes_are_exposed(self):
        self.assertIn(("/api/learners/local/profile", "GET"), self.routes)
        self.assertIn(("/api/learners/local/profile", "PUT"), self.routes)
        self.assertIn(("/api/learners/local", "DELETE"), self.routes)

    def test_learning_plan_routes_are_exposed(self):
        self.assertIn(("/api/plp/active", "GET"), self.routes)
        self.assertIn(("/api/plp/generations", "POST"), self.routes)

    def test_no_versioned_api_aliases_are_exposed(self):
        self.assertFalse(
            any(path.startswith("/api/v1") for path, _method in self.routes)
        )

    def test_static_generation_route_precedes_dynamic_job_route(self):
        import main

        paths = [route.path for route in main.app.routes]
        self.assertLess(
            paths.index("/api/plp/generations/latest"),
            paths.index("/api/plp/generations/{job_id}"),
        )

    def test_chat_websocket_is_exposed(self):
        self.assertIn(("/ws/chat", "WEBSOCKET"), self.routes)

    def test_custom_roleplay_scenario_lifecycle_is_exposed(self):
        path = "/api/roleplay/scenarios/{scenario_id}"
        self.assertIn((path, "PUT"), self.routes)
        self.assertIn((path, "DELETE"), self.routes)

    def test_tts_is_protected_post_only(self):
        self.assertIn(("/api/tts", "POST"), self.routes)
        self.assertNotIn(("/api/tts", "GET"), self.routes)

        from fastapi.testclient import TestClient

        import main

        with TestClient(main.app) as client:
            response = client.post("/api/tts", json={"text": "Hello"})
        self.assertEqual(response.status_code, 401)

    def test_public_news_image_proxy_is_rate_limited(self):
        from speakflow.app.factory import _rate_limit_rule

        self.assertEqual(_rate_limit_rule("GET", "/api/news/image"), (30, 60))

    def test_provider_backed_routes_are_rate_limited(self):
        from speakflow.app.factory import _rate_limit_rule

        self.assertEqual(_rate_limit_rule("GET", "/api/news"), (12, 60))
        for path in (
            "/api/grammar/check",
            "/api/vocabulary/lookup",
            "/api/translation/arabic",
        ):
            self.assertEqual(_rate_limit_rule("POST", path), (30, 60))
        self.assertEqual(
            _rate_limit_rule("POST", "/api/roleplay/scenarios/draft"),
            (10, 60),
        )
        self.assertEqual(
            _rate_limit_rule(
                "POST",
                "/api/roleplay/sessions/session-123/escape-route",
            ),
            (30, 60),
        )
        self.assertEqual(
            _rate_limit_rule("POST", "/api/plp/generations"),
            (10, 60),
        )

    def test_android_release_denies_cleartext_but_debug_allows_it(self):
        project_root = BACKEND_ROOT.parent
        release_manifest = (
            project_root / "frontend/android/app/src/main/AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        debug_manifest = (
            project_root / "frontend/android/app/src/debug/AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        self.assertIn('android:usesCleartextTraffic="false"', release_manifest)
        self.assertIn('android:usesCleartextTraffic="true"', debug_manifest)

    def test_public_health_exposes_readiness_only(self):
        from fastapi.testclient import TestClient

        import main

        with patch.object(
            main.learning_plan_lifecycle,
            "health",
            return_value={
                "database": "ready",
                "curriculum": "ready",
                "worker": True,
            },
        ):
            with TestClient(main.app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_public_health_is_unavailable_when_curriculum_is_missing(self):
        from fastapi.testclient import TestClient

        import main

        with patch.object(
            main.learning_plan_lifecycle,
            "health",
            return_value={
                "database": "ready",
                "curriculum": "unavailable",
                "worker": True,
            },
        ):
            with TestClient(main.app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "degraded"})

    def test_generation_reports_catalog_unavailability_as_503(self):
        from fastapi.testclient import TestClient

        import main
        plp_router = importlib.import_module(
            "speakflow.features.learning_plan.presentation.router"
        )
        from speakflow.features.auth.domain import AuthenticatedUser
        from speakflow.features.auth.infrastructure.service import auth_service
        from speakflow.features.learning_plan.engine.service import PlpUnavailableError

        user = AuthenticatedUser(
            user_id=UUID("00000000-0000-0000-0000-000000000201"),
            kind="registered",
            email="learner@example.test",
            display_name="Learner",
        )
        message = "learning-plan curriculum is not ready"
        with (
            patch.object(auth_service, "authenticate", return_value=user),
            patch.object(
                plp_router.learning_plan_service,
                "create_generation",
                side_effect=PlpUnavailableError(message),
            ),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/plp/generations",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": message})

    def test_generation_endpoint_distinguishes_manual_regeneration(self):
        from fastapi.testclient import TestClient

        import main
        plp_router = importlib.import_module(
            "speakflow.features.learning_plan.presentation.router"
        )
        from speakflow.features.auth.domain import AuthenticatedUser
        from speakflow.features.auth.infrastructure.service import auth_service

        user = AuthenticatedUser(
            user_id=UUID("00000000-0000-0000-0000-000000000202"),
            kind="registered",
            email="regenerate@example.test",
            display_name="Learner",
        )
        accepted = {
            "job_id": "00000000-0000-0000-0000-000000000302",
            "plan_id": "00000000-0000-0000-0000-000000000402",
            "status": "queued",
        }
        with (
            patch.object(auth_service, "authenticate", return_value=user),
            patch.object(
                plp_router.learning_plan_service,
                "create_generation",
                return_value=accepted,
            ) as create_generation,
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/plp/generations",
                headers={"Authorization": "Bearer test-token"},
                json={"regenerate": True},
            )

        self.assertEqual(response.status_code, 202)
        create_generation.assert_called_once_with(True)

    def test_admin_routes_require_an_authenticated_administrator(self):
        from fastapi import APIRouter
        from fastapi.testclient import TestClient

        from speakflow.app.factory import create_application
        from speakflow.features.auth.domain import AuthenticatedUser
        from speakflow.features.auth.infrastructure.service import auth_service

        router = APIRouter()

        @router.get("/admin/probe")
        def probe(request: Request):
            return {"user_id": str(request.state.authenticated_user.user_id)}

        application = create_application(routers=(router,))
        regular_user = AuthenticatedUser(
            user_id=UUID("00000000-0000-0000-0000-000000000101"),
            kind="registered",
            email="learner@example.test",
            display_name="Learner",
        )
        administrator = AuthenticatedUser(
            user_id=UUID("00000000-0000-0000-0000-000000000102"),
            kind="registered",
            email="admin@example.test",
            display_name="Administrator",
            is_admin=True,
        )
        with TestClient(application) as client:
            self.assertEqual(client.get("/admin/probe").status_code, 401)
            with patch.object(auth_service, "authenticate", return_value=regular_user):
                self.assertEqual(
                    client.get(
                        "/admin/probe",
                        headers={"Authorization": "Bearer regular-token"},
                    ).status_code,
                    403,
                )
            with patch.object(auth_service, "authenticate", return_value=administrator):
                response = client.get(
                    "/admin/probe",
                    headers={"Authorization": "Bearer admin-token"},
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], str(administrator.user_id))

    def test_admin_session_revocation_is_rate_limited(self):
        from speakflow.app.factory import _rate_limit_rule

        self.assertEqual(
            _rate_limit_rule(
                "POST",
                "/admin/users/00000000-0000-0000-0000-000000000001/revoke",
            ),
            (10, 60),
        )

    def test_oversized_audio_request_is_rejected_before_endpoint_parsing(self):
        from fastapi.testclient import TestClient

        import main

        with TestClient(main.app) as client:
            response = client.post(
                "/api/pronunciation",
                headers={"Content-Length": str(16 * 1024 * 1024 + 1)},
            )
        self.assertEqual(response.status_code, 413)

    def test_pronunciation_form_metadata_is_validated_before_audio_scoring(self):
        from fastapi.testclient import TestClient

        import main
        from speakflow.features.auth.domain import AuthenticatedUser
        from speakflow.features.auth.infrastructure.service import auth_service

        user = AuthenticatedUser(
            user_id=UUID("00000000-0000-0000-0000-000000000202"),
            kind="registered",
            email="learner@example.test",
            display_name="Learner",
        )
        with (
            patch.object(auth_service, "authenticate", return_value=user),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/pronunciation",
                headers={"Authorization": "Bearer test-token"},
                data={
                    "target_word": "paper",
                    "activity_id": "activity-1",
                    "attempt_session_id": "too-short",
                    "timezone_offset_minutes": "5000",
                },
                files={"file": ("sample.wav", b"not-a-wave", "audio/wav")},
            )
        self.assertEqual(response.status_code, 422)

    def test_chunked_audio_body_is_capped_while_streaming(self):
        from speakflow.app.factory import _BodyLimitMiddleware

        messages = iter(
            [
                {"type": "http.request", "body": b"1234", "more_body": True},
                {"type": "http.request", "body": b"5678", "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def consume_body(_scope, body_receive, body_send):
            while True:
                message = await body_receive()
                if not message.get("more_body"):
                    break
            await body_send({"type": "http.response.start", "status": 204})
            await body_send({"type": "http.response.body", "body": b""})

        middleware = _BodyLimitMiddleware(consume_body, maximum_bytes=5)
        asyncio.run(
            middleware(
                {"type": "http", "path": "/api/pronunciation"},
                receive,
                send,
            )
        )
        start = next(item for item in sent if item["type"] == "http.response.start")
        self.assertEqual(start["status"], 413)

    def test_rate_limits_are_shared_between_worker_instances(self):
        from speakflow.app.rate_limit import ProcessSharedRateLimiter

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "limits.sqlite3"
            first = ProcessSharedRateLimiter(path)
            second = ProcessSharedRateLimiter(path)
            self.assertEqual(first.retry_after("client", limit=1, window=60), 0)
            self.assertGreaterEqual(
                second.retry_after("client", limit=1, window=60),
                1,
            )


if __name__ == "__main__":
    unittest.main()
