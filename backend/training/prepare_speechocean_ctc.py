"""Prepare Hugging Face SpeechOcean762 parquet files for CTC-GOPT training."""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf

from pronunciation_core import GOPT_PHONE_TO_ID


DEFAULT_SOURCE = (
    Path.home()
    / "english_learning_app_data"
    / "speechocean762_hf"
    / "data"
)
DEFAULT_OUTPUT = (
    Path.home()
    / "english_learning_app_data"
    / "speechocean762_ctc"
)


def _pure(phone: str) -> str:
    return re.sub(r"[012]$", "", str(phone).upper())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    parquet_files = {
        "train": args.source / "train-00000-of-00001.parquet",
        "test": args.source / "test-00000-of-00001.parquet",
    }
    if not all(path.is_file() for path in parquet_files.values()):
        raise FileNotFoundError(
            f"SpeechOcean762 train/test parquet files are missing under {args.source}"
        )
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(
            f"output already contains files; choose an empty directory: {args.output}"
        )
    (args.output / "audio").mkdir(parents=True)

    manifest_path = args.output / "manifest.jsonl"
    example_count = 0
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for split, parquet_path in parquet_files.items():
            parquet = pq.ParquetFile(parquet_path)
            for batch in parquet.iter_batches(batch_size=32):
                for row in batch.to_pylist():
                    words = row["words"]
                    phones = tuple(
                        str(phone).upper()
                        for word in words
                        for phone in word["phones"]
                    )
                    pure_phones = tuple(_pure(phone) for phone in phones)
                    if (
                        not phones
                        or len(phones) > 50
                        or any(phone not in GOPT_PHONE_TO_ID for phone in pure_phones)
                    ):
                        raise ValueError(
                            f"unsupported phone sequence in {row['audio']['path']}"
                        )
                    audio, sample_rate = sf.read(
                        io.BytesIO(row["audio"]["bytes"]),
                        dtype="float32",
                        always_2d=False,
                    )
                    if sample_rate != 16_000:
                        raise ValueError(
                            f"unexpected sample rate {sample_rate} in {row['audio']['path']}"
                        )
                    if audio.ndim == 2:
                        audio = audio.mean(axis=1)
                    utterance_id = Path(row["audio"]["path"]).stem
                    relative_audio = (
                        Path("audio") / split / f"{utterance_id}.wav"
                    )
                    destination = args.output / relative_audio
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    sf.write(destination, audio, 16_000, subtype="PCM_16")
                    item = {
                        "id": utterance_id,
                        "split": split,
                        "speaker": str(row["speaker"]),
                        "audio": relative_audio.as_posix(),
                        "text": row["text"],
                        "phones": list(phones),
                        "pure_phones": list(pure_phones),
                        "phone_labels": [
                            float(score)
                            for word in words
                            for score in word["phones-accuracy"]
                        ],
                        "word_lengths": [len(word["phones"]) for word in words],
                        "word_labels": [
                            [
                                float(word["accuracy"]) / 5.0,
                                float(word["stress"]) / 5.0,
                                float(word["total"]) / 5.0,
                            ]
                            for word in words
                        ],
                        "utterance_labels": [
                            float(row["accuracy"]) / 5.0,
                            float(row["completeness"]) / 5.0,
                            float(row["fluency"]) / 5.0,
                            float(row["prosodic"]) / 5.0,
                            float(row["total"]) / 5.0,
                        ],
                    }
                    if len(item["phone_labels"]) != len(phones):
                        raise ValueError(
                            f"phone labels do not cover {utterance_id}"
                        )
                    manifest.write(
                        json.dumps(item, ensure_ascii=False) + "\n"
                    )
                    example_count += 1
    if example_count != 5_000:
        raise ValueError(
            f"prepared {example_count} SpeechOcean utterances; expected 5000"
        )
    print(f"prepared {example_count} utterances under {args.output}")


if __name__ == "__main__":
    main()
