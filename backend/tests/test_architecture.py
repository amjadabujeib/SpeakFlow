from __future__ import annotations

import ast
import asyncio
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
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
        allowed = {"main.py", "setup.py"}
        loose_modules = {
            path.name for path in BACKEND_ROOT.glob("*.py")
        }
        self.assertEqual(loose_modules, allowed)

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
        from plp.models import AuthSession, Base, RoleplaySession, User

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

    def test_public_news_image_proxy_is_rate_limited(self):
        from speakflow.app.factory import _rate_limit_rule

        self.assertEqual(_rate_limit_rule("GET", "/api/news/image"), (30, 60))

    def test_oversized_audio_request_is_rejected_before_endpoint_parsing(self):
        from fastapi.testclient import TestClient
        import main

        with TestClient(main.app) as client:
            response = client.post(
                "/api/pronunciation",
                headers={"Content-Length": str(16 * 1024 * 1024 + 1)},
            )
        self.assertEqual(response.status_code, 413)

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
