from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import setup_backend as backend_setup


class CurriculumSetupTests(unittest.TestCase):
    def test_curriculum_setup_ingests_core_then_restores_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            backend_root = Path(directory)
            snapshot = (
                backend_root
                / ".models"
                / "curriculum"
                / "rag-curriculum-v1.zip"
            )
            snapshot.parent.mkdir(parents=True)
            snapshot.touch()
            with (
                patch.object(backend_setup, "BACKEND_ROOT", backend_root),
                patch.object(backend_setup.subprocess, "run") as run,
            ):
                backend_setup._ingest_curriculum()

        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[0].args[0],
            [backend_setup.sys.executable, "-m", "speakflow.features.learning_plan.engine.ingest"],
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                backend_setup.sys.executable,
                "-m",
                "speakflow.features.learning_plan.engine.curriculum_snapshot",
                "import",
                "--snapshot",
                str(snapshot),
            ],
        )
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["cwd"], backend_root)
            self.assertTrue(call.kwargs["check"])
            self.assertIn(str(backend_root), call.kwargs["env"]["PYTHONPATH"])

    def test_curriculum_setup_fails_before_ingestion_without_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    backend_setup,
                    "BACKEND_ROOT",
                    Path(directory),
                ),
                patch.object(backend_setup.subprocess, "run") as run,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "missing its RAG curriculum snapshot",
                ):
                    backend_setup._ingest_curriculum()

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
