from __future__ import annotations

import ast
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


class VersionedApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.routes = {
            (route.path, method)
            for route in main.app.routes
            for method in (getattr(route, "methods", None) or {"WEBSOCKET"})
        }

    def test_canonical_authenticated_user_routes_are_exposed(self):
        self.assertIn(("/api/v1/me/profile", "GET"), self.routes)
        self.assertIn(("/api/v1/me/profile", "PUT"), self.routes)
        self.assertIn(("/api/v1/me/learning-data", "DELETE"), self.routes)

    def test_canonical_learning_plan_routes_are_exposed(self):
        self.assertIn(("/api/v1/learning-plan/active", "GET"), self.routes)
        self.assertIn(("/api/v1/learning-plan/generations", "POST"), self.routes)

    def test_static_generation_route_precedes_dynamic_job_route(self):
        import main

        paths = [route.path for route in main.app.routes]
        self.assertLess(
            paths.index("/api/v1/learning-plan/generations/latest"),
            paths.index("/api/v1/learning-plan/generations/{job_id}"),
        )

    def test_versioned_chat_websocket_is_exposed(self):
        self.assertIn(("/api/v1/chat/ws", "WEBSOCKET"), self.routes)


if __name__ == "__main__":
    unittest.main()
