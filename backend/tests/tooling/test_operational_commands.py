from __future__ import annotations

import importlib
import unittest


class OperationalCommandImportTests(unittest.TestCase):
    def test_documented_learning_plan_commands_import_cleanly(self) -> None:
        modules = {
            "audit_curriculum": "main",
            "audit_generation": "main",
            "audit_weekly": "main",
            "curriculum_snapshot": "read_snapshot",
            "external_curriculum_ingest": "main",
            "ingest": "main",
        }
        prefix = "speakflow.features.learning_plan.engine"
        for name, callable_name in modules.items():
            with self.subTest(command=name):
                module = importlib.import_module(f"{prefix}.{name}")
                self.assertTrue(callable(getattr(module, callable_name, None)))


if __name__ == "__main__":
    unittest.main()
