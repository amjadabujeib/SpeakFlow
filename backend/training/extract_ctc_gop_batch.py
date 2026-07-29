"""Resumable XLSR-53 CTC-GOP extraction for prepared pronunciation data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from ctc_gop import (
    CTC_GOP_FEATURE_DIM,
    CTC_PHONE_TO_ID,
    CTC_SCHEMA_FILENAME,
    Wav2Vec2CtcGopExtractor,
)
from training.pronunciation_data import DEFAULT_ARABIC_DATASET


DEFAULT_MODEL = (
    Path(__file__).resolve().parents[1]
    / "pretrained_models"
    / "wav2vec2_xlsr53_cmu39_ctc"
)


def _atomic_save(path: Path, values: np.ndarray) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_ARABIC_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--device")
    parser.add_argument("--head", type=Path)
    parser.add_argument("--counterfactual-batch-size", type=int, default=128)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--speaker")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    schema_path = args.model / CTC_SCHEMA_FILENAME
    schema_bytes = schema_path.read_bytes()
    extractor = Wav2Vec2CtcGopExtractor(
        args.model,
        device=args.device,
        counterfactual_batch_size=args.counterfactual_batch_size,
        ctc_head_path=args.head,
    )
    rows = [
        json.loads(line)
        for line in (args.data / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if args.speaker is not None:
        rows = [row for row in rows if row["speaker"] == args.speaker]
    if args.limit is not None:
        rows = rows[: args.limit]

    output = args.output or (args.data / "ctc_gop_output")
    output.mkdir(parents=True, exist_ok=True)
    diagnosis_root = output / "diagnosis"
    diagnosis_root.mkdir(exist_ok=True)
    completed = 0
    for index, row in enumerate(rows, start=1):
        feature_path = output / f"{row['id']}.npy"
        diagnosis_path = diagnosis_root / f"{row['id']}.npz"
        expected_shape = (len(row["pure_phones"]), CTC_GOP_FEATURE_DIM)
        if (
            feature_path.is_file()
            and diagnosis_path.is_file()
            and not args.overwrite
        ):
            existing = np.load(feature_path, allow_pickle=False)
            with np.load(diagnosis_path, allow_pickle=False) as diagnosis:
                diagnosis_valid = (
                    diagnosis["likely_phone_ids"].shape
                    == (len(row["pure_phones"]),)
                    and diagnosis["likely_phone_probabilities"].shape
                    == (len(row["pure_phones"]),)
                    and diagnosis["deletion_probabilities"].shape
                    == (len(row["pure_phones"]),)
                )
            if (
                existing.shape == expected_shape
                and np.isfinite(existing).all()
                and diagnosis_valid
            ):
                completed += 1
                print(f"[{index}/{len(rows)}] cached {row['id']}", flush=True)
                continue
        result = extractor.extract(
            args.data / row["audio"],
            row["pure_phones"],
        )
        if result.features.shape != expected_shape:
            raise RuntimeError(
                f"{row['id']}: got {result.features.shape}, expected {expected_shape}"
            )
        _atomic_save(feature_path, result.features)
        likely_phone_ids = np.asarray(
            [
                0 if phone is None else CTC_PHONE_TO_ID[phone]
                for phone in result.likely_phones
            ],
            dtype=np.int16,
        )
        temporary_diagnosis = diagnosis_path.with_name(
            diagnosis_path.name + f".{os.getpid()}.tmp"
        )
        with temporary_diagnosis.open("wb") as handle:
            np.savez_compressed(
                handle,
                likely_phone_ids=likely_phone_ids,
                likely_phone_probabilities=result.likely_phone_probabilities,
                deletion_probabilities=result.deletion_probabilities,
            )
        temporary_diagnosis.replace(diagnosis_path)
        completed += 1
        print(f"[{index}/{len(rows)}] extracted {row['id']}", flush=True)

    adapted_head = (
        None
        if args.head is None
        else {
            "path": str(args.head.resolve()),
            "sha256": hashlib.sha256(args.head.read_bytes()).hexdigest(),
        }
    )
    metadata = {
        "version": 1,
        "feature_dim": CTC_GOP_FEATURE_DIM,
        "model_dir": str(args.model.resolve()),
        "model_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        "adapted_head": adapted_head,
        "speaker_filter": args.speaker,
        "utterances": completed,
    }
    metadata_path = output / "metadata.json"
    if args.speaker is not None and adapted_head is not None:
        heads_by_speaker = {}
        if metadata_path.is_file():
            previous = json.loads(metadata_path.read_text(encoding="utf-8"))
            heads_by_speaker.update(
                previous.get("adapted_heads_by_speaker", {})
            )
            previous_speaker = previous.get("speaker_filter")
            previous_head = previous.get("adapted_head")
            if previous_speaker is not None and previous_head is not None:
                heads_by_speaker[str(previous_speaker)] = previous_head
        heads_by_speaker[args.speaker] = adapted_head
        metadata["adapted_head"] = None
        metadata["speaker_filter"] = None
        metadata["adapted_heads_by_speaker"] = heads_by_speaker
        metadata["utterances"] = len(tuple(output.glob("*.npy")))
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
