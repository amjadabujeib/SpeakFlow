"""Shared loader for prepared Arabic-L1 CTC-GOP pronunciation data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ctc_gop import CTC_GOP_FEATURE_DIM
from pronunciation_core import GOPT_PHONE_TO_ID


DEFAULT_DATA_ROOT = Path.home() / "english_learning_app_data"
DEFAULT_ARABIC_DATASET = DEFAULT_DATA_ROOT / "l2_arctic_arabic_ctc"
DEFAULT_MANUAL_DATASET = DEFAULT_DATA_ROOT / "l2_arctic_manual"


@dataclass(frozen=True)
class Example:
    utterance_id: str
    split: str
    variant: str
    features: np.ndarray
    phone_ids: np.ndarray
    phone_targets: np.ndarray
    word_targets: np.ndarray
    utterance_target: float


def load_examples(
    data_root: Path,
    feature_root: Path | None = None,
) -> list[Example]:
    """Load and strictly validate prepared annotations and CTC-GOP rows."""
    feature_root = feature_root or (data_root / "ctc_gop_output")
    metadata_path = feature_root / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError(f"CTC-GOP extraction metadata is missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if int(metadata.get("feature_dim", -1)) != CTC_GOP_FEATURE_DIM:
        raise ValueError("CTC-GOP extraction feature dimension is incompatible")
    examples: list[Example] = []
    expected_feature_files: set[Path] = set()

    with (data_root / "manifest.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            utterance_id = row["id"]
            feature_path = feature_root / f"{utterance_id}.npy"
            expected_feature_files.add(feature_path)
            if not feature_path.is_file():
                raise ValueError(f"no CTC-GOP features for {utterance_id}")
            matrix = np.load(feature_path, allow_pickle=False)
            expected_phones = tuple(row["pure_phones"])
            expected_shape = (len(expected_phones), CTC_GOP_FEATURE_DIM)
            if matrix.shape != expected_shape:
                raise ValueError(
                    f"{utterance_id}: CTC-GOP shape {matrix.shape}, "
                    f"expected {expected_shape}"
                )
            if not np.isfinite(matrix).all():
                raise ValueError(f"{utterance_id}: CTC-GOP features are non-finite")

            word_targets: list[float] = []
            for phones, target in zip(row["word_phones"], row["word_labels"]):
                word_targets.extend([float(target)] * len(phones))
            if len(word_targets) != len(expected_phones):
                raise ValueError(
                    f"{utterance_id}: word labels do not cover every phone"
                )

            examples.append(
                Example(
                    utterance_id=utterance_id,
                    split=row["split"],
                    variant=row["variant"],
                    features=matrix.astype(np.float32, copy=False),
                    phone_ids=np.asarray(
                        [GOPT_PHONE_TO_ID[phone] for phone in expected_phones]
                    ),
                    phone_targets=np.asarray(row["phone_labels"], dtype=np.float32),
                    word_targets=np.asarray(word_targets, dtype=np.float32),
                    utterance_target=float(row["utterance_accuracy"]),
                )
            )
    extra = set(feature_root.glob("*.npy")) - expected_feature_files
    if extra:
        raise ValueError(f"CTC-GOP features exist without annotations: {len(extra)}")
    return examples
