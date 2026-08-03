from __future__ import annotations

import unittest
from unittest.mock import patch

from speakflow.runtime import models as model_runtime


class LocalModelLoadingTests(unittest.TestCase):
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
