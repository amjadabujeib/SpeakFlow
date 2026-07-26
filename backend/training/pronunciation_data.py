"""Shared loader for prepared Arabic-L1 pronunciation training data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pronunciation_service import GOPT_FEATURE_DIM, GOPT_PHONE_TO_ID


DEFAULT_DATA_ROOT = Path.home() / "english_learning_app_data"
DEFAULT_ARABIC_DATASET = DEFAULT_DATA_ROOT / "l2_arctic_arabic"
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


def _read_feature_vectors(path: Path) -> dict[str, np.ndarray]:
    """Read Kaldi's one-vector-per-phone text archive."""
    vectors: dict[str, list[tuple[int, np.ndarray]]] = {}
    pending_key: str | None = None
    pending_values: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if pending_key is None:
            if "[" not in line:
                continue
            pending_key, line = line.split("[", 1)
            pending_key = pending_key.strip()
            pending_values = []
        if "]" in line:
            before, _ = line.split("]", 1)
            pending_values.extend(before.split())
            values = np.asarray(
                [float(value) for value in pending_values], dtype=np.float32
            )
            if values.shape != (GOPT_FEATURE_DIM + 1,):
                raise ValueError(
                    f"{pending_key} has shape {values.shape}, expected (85,)"
                )
            utterance_id, phone_index_text = pending_key.rsplit(".", 1)
            vectors.setdefault(utterance_id, []).append(
                (int(phone_index_text), values)
            )
            pending_key = None
            pending_values = []
        else:
            pending_values.extend(line.split())

    if pending_key is not None:
        raise ValueError(f"unterminated Kaldi vector: {pending_key}")
    return {
        utterance_id: np.stack([value for _, value in sorted(items)])
        for utterance_id, items in vectors.items()
    }


def _phone_table(path: Path) -> dict[int, str]:
    return {
        int(phone_id): phone
        for phone, phone_id in (
            line.split() for line in path.read_text(encoding="utf-8").splitlines()
        )
    }


def load_examples(data_root: Path) -> list[Example]:
    """Load and strictly validate prepared annotations and Kaldi GOP rows."""
    feature_root = data_root / "kaldi_output"
    vectors = _read_feature_vectors(feature_root / "features.txt")
    phone_table = _phone_table(feature_root / "phones-pure.txt")
    examples: list[Example] = []

    with (data_root / "manifest.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            utterance_id = row["id"]
            matrix = vectors.pop(utterance_id, None)
            if matrix is None:
                raise ValueError(f"no GOP features for {utterance_id}")
            expected_phones = tuple(row["pure_phones"])
            if matrix.shape[0] != len(expected_phones):
                raise ValueError(
                    f"{utterance_id}: {matrix.shape[0]} vectors for "
                    f"{len(expected_phones)} phones"
                )
            aligned_phones = tuple(
                phone_table[int(round(value))] for value in matrix[:, 0]
            )
            if aligned_phones != expected_phones:
                raise ValueError(
                    f"{utterance_id}: aligned phones do not match annotations"
                )

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
                    features=matrix[:, 1:],
                    phone_ids=np.asarray(
                        [GOPT_PHONE_TO_ID[phone] for phone in expected_phones]
                    ),
                    phone_targets=np.asarray(row["phone_labels"], dtype=np.float32),
                    word_targets=np.asarray(word_targets, dtype=np.float32),
                    utterance_target=float(row["utterance_accuracy"]),
                )
            )
    if vectors:
        raise ValueError(f"features exist without annotations: {len(vectors)} utterances")
    return examples
