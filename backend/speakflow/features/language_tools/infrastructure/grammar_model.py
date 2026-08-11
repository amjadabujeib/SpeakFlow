"""Load the bundled GECToR checkpoint without a second RoBERTa model."""

from __future__ import annotations

from pathlib import Path

import torch.nn as nn
from gector import GECToR
from gector.configuration import GECToRConfig
from torch.nn import CrossEntropyLoss
from transformers import PreTrainedModel, RobertaConfig, RobertaModel

# Architecture of roberta-base. The fine-tuned GECToR checkpoint already
# contains every encoder and correction-head tensor; only this shape metadata
# is needed to construct the modules before Transformers loads those tensors.
ROBERTA_BASE_ARCHITECTURE = {
    "attention_probs_dropout_prob": 0.1,
    "bos_token_id": 0,
    "eos_token_id": 2,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-5,
    "max_position_embeddings": 514,
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 1,
    "type_vocab_size": 1,
    "vocab_size": 50265,
}


class SelfContainedGECToR(GECToR):
    """GECToR variant that never resolves ``config.model_id``."""

    def __init__(self, config: GECToRConfig):
        # GECToR.__init__ downloads or opens config.model_id before loading the
        # fine-tuned state. Initialize its PreTrainedModel parent directly.
        PreTrainedModel.__init__(self, config)
        self.config = config
        self.tokenizer = None
        roberta_config = RobertaConfig(**ROBERTA_BASE_ARCHITECTURE)
        self.bert = RobertaModel(roberta_config, add_pooling_layer=False)
        self.bert.resize_token_embeddings(
            roberta_config.vocab_size + 1,
            mean_resizing=False,
        )
        self.label_proj_layer = nn.Linear(
            roberta_config.hidden_size,
            self.config.num_labels - 1,
        )
        self.d_proj_layer = nn.Linear(
            roberta_config.hidden_size,
            self.config.d_num_labels - 1,
        )
        self.dropout = nn.Dropout(self.config.p_dropout)
        self.loss_fn = CrossEntropyLoss(
            label_smoothing=self.config.label_smoothing
        )
        self.post_init()
        self.tune_bert(False)


def load_self_contained_gector(
    checkpoint: str | Path,
) -> SelfContainedGECToR:
    """Load a complete local checkpoint while ignoring its legacy model path."""
    local_checkpoint = str(Path(checkpoint).resolve())
    config = GECToRConfig.from_pretrained(
        local_checkpoint,
        local_files_only=True,
    )
    config.model_id = "embedded-in-gector-checkpoint"
    return SelfContainedGECToR.from_pretrained(
        local_checkpoint,
        config=config,
        local_files_only=True,
    )
