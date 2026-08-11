from __future__ import annotations

import unittest
from unittest.mock import patch

from speakflow.runtime import models as model_runtime


class LocalModelLoadingTests(unittest.TestCase):
    def test_eager_warmup_loads_every_local_model_family(self):
        with (
            patch.object(model_runtime, "_load_whisper_models", return_value=True),
            patch.object(model_runtime, "_load_gector_model", return_value=True),
            patch.object(model_runtime, "_load_kokoro_pipeline", return_value=True),
            patch.object(
                model_runtime,
                "_load_pronunciation_scorer",
                return_value=False,
            ),
        ):
            report = model_runtime.eager_load_runtime_models()

        self.assertEqual(
            report.models,
            {
                "whisperx": True,
                "grammar": True,
                "tts": True,
                "pronunciation": False,
            },
        )
        self.assertFalse(report.ready)
        self.assertEqual(report.unavailable, ("pronunciation",))

    def test_eager_is_default_and_lazy_remains_an_explicit_opt_out(self):
        with patch.dict(model_runtime.os.environ, {}, clear=True):
            self.assertEqual(model_runtime.model_loading_mode(), "eager")
        with patch.dict(
            model_runtime.os.environ,
            {"SPEAKFLOW_MODEL_LOADING": "lazy"},
            clear=True,
        ):
            self.assertEqual(model_runtime.model_loading_mode(), "lazy")

    def test_english_only_whisper_checkpoint_pins_language(self):
        loaded_whisper = object()
        loaded_aligner = object()
        metadata = {"language": "en"}
        with (
            patch.object(model_runtime, "WHISPER_AVAILABLE", True),
            patch.object(model_runtime, "whisper_model", None),
            patch.object(model_runtime, "align_model", None),
            patch.object(model_runtime, "align_metadata", None),
            patch.object(model_runtime, "_failed_model_loads", set()),
            patch.object(
                model_runtime.whisperx,
                "load_model",
                return_value=loaded_whisper,
            ) as load_model,
            patch.object(
                model_runtime.whisperx,
                "load_align_model",
                return_value=(loaded_aligner, metadata),
            ),
        ):
            self.assertTrue(model_runtime._load_whisper_models())

        self.assertEqual(load_model.call_args.kwargs["language"], "en")
        self.assertTrue(load_model.call_args.kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
