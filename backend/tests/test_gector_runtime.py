from __future__ import annotations

import tempfile
import unittest
import warnings
from unittest.mock import patch

import torch
from gector.configuration import GECToRConfig

from speakflow.runtime import grammar_model as gector_runtime


TINY_ROBERTA_ARCHITECTURE = {
    "attention_probs_dropout_prob": 0.0,
    "bos_token_id": 0,
    "eos_token_id": 2,
    "hidden_dropout_prob": 0.0,
    "hidden_size": 8,
    "intermediate_size": 16,
    "max_position_embeddings": 16,
    "num_attention_heads": 2,
    "num_hidden_layers": 1,
    "pad_token_id": 1,
    "type_vocab_size": 1,
    "vocab_size": 20,
}


class SelfContainedGectorTests(unittest.TestCase):
    def test_checkpoint_load_ignores_external_base_model_path(self):
        labels = {
            "<OOV>": 0,
            "$KEEP": 1,
            "$DELETE": 2,
            "<PAD>": 3,
        }
        config = GECToRConfig(
            model_id="/definitely/missing/roberta-base",
            label2id=labels,
            id2label={value: key for key, value in labels.items()},
            max_length=8,
            has_add_pooling_layer=True,
        )
        with (
            patch.dict(
                gector_runtime.ROBERTA_BASE_ARCHITECTURE,
                TINY_ROBERTA_ARCHITECTURE,
                clear=True,
            ),
            tempfile.TemporaryDirectory() as directory,
        ):
            source = gector_runtime.SelfContainedGECToR(config)
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Some non-default generation parameters",
                )
                source.save_pretrained(directory)
            with (
                patch(
                    "gector.modeling.AutoModel.from_pretrained",
                    side_effect=AssertionError("external model access"),
                ),
                patch(
                    "gector.modeling.AutoTokenizer.from_pretrained",
                    side_effect=AssertionError("external tokenizer access"),
                ),
            ):
                loaded = gector_runtime.load_self_contained_gector(directory)

        self.assertEqual(
            loaded.config.model_id,
            "embedded-in-gector-checkpoint",
        )
        self.assertEqual(
            loaded.bert.embeddings.word_embeddings.num_embeddings,
            21,
        )
        output = loaded(
            input_ids=torch.tensor([[0, 4, 2]]),
            attention_mask=torch.ones((1, 3), dtype=torch.long),
        )
        self.assertEqual(tuple(output.logits_labels.shape), (1, 3, 3))
        self.assertEqual(tuple(output.logits_d.shape), (1, 3, 2))


if __name__ == "__main__":
    unittest.main()
