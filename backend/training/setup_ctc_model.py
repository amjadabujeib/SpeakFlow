"""Install the pinned Interspeech-2024 XLSR-53 CMU39 CTC checkpoint.

The 1.26 GB weight is intentionally excluded from Git. The download is
resumable and its Git-LFS SHA-256 digest is verified before promotion.
"""

from __future__ import annotations

import hashlib
import json
import socket
import shutil
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ctc_gop import (
    CTC_BLANK_ID,
    CTC_GOP_FEATURE_DIM,
    CTC_PHONE_TO_ID,
    CTC_SCHEMA_FILENAME,
    CTC_SCHEMA_VERSION,
)


SOURCE_COMMIT = "ffc4823330efe2c836691931a456ea9e3360871e"
SOURCE_ROOT = (
    "https://raw.githubusercontent.com/frank613/CTC-based-GOP/"
    f"{SOURCE_COMMIT}/is24/models/checkpoint-8000"
)
LFS_BATCH_URL = (
    "https://github.com/frank613/CTC-based-GOP.git/info/lfs/objects/batch"
)
WEIGHT_SIZE = 1_262_066_282
WEIGHT_SHA256 = "035b95ada8ec20d83378981a050166391cffdba9810e417097b74f492112541b"
MODEL_FILES = ("config.json", "preprocessor_config.json", "vocab.json")
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "pretrained_models"
    / "wav2vec2_xlsr53_cmu39_ctc"
)


def _download_small(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        destination.write_bytes(response.read())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _lfs_download_url() -> str:
    payload = json.dumps(
        {
            "operation": "download",
            "transfers": ["basic"],
            "objects": [{"oid": WEIGHT_SHA256, "size": WEIGHT_SIZE}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        LFS_BATCH_URL,
        data=payload,
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read())
    try:
        return str(result["objects"][0]["actions"]["download"]["href"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Git-LFS did not return a model download URL") from exc


def _download_weight(destination: Path) -> None:
    download_url = _lfs_download_url()
    partial = destination.with_suffix(destination.suffix + ".part")
    parts_dir = destination.with_suffix(destination.suffix + ".parts")
    chunk_size = 4 * 1024 * 1024
    layout_path = parts_dir / "layout.json"
    expected_layout = {"chunk_size": chunk_size, "weight_size": WEIGHT_SIZE}
    if parts_dir.is_dir():
        try:
            existing_layout = json.loads(layout_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_layout = None
        if existing_layout != expected_layout:
            shutil.rmtree(parts_dir)
    parts_dir.mkdir(exist_ok=True)
    layout_path.write_text(
        json.dumps(expected_layout, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ranges = [
        (index, start, min(start + chunk_size, WEIGHT_SIZE) - 1)
        for index, start in enumerate(range(0, WEIGHT_SIZE, chunk_size))
    ]

    def download_part(index: int, start: int, end: int) -> tuple[int, Path]:
        part = parts_dir / f"{index:04d}.part"
        expected = end - start + 1
        if part.is_file() and part.stat().st_size == expected:
            return index, part
        temporary = part.with_suffix(".tmp")
        if temporary.is_file() and temporary.stat().st_size > expected:
            temporary.unlink()
        failures = 0
        while not temporary.is_file() or temporary.stat().st_size < expected:
            offset = temporary.stat().st_size if temporary.is_file() else 0
            request = urllib.request.Request(
                download_url,
                headers={"Range": f"bytes={start + offset}-{end}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    if response.status != 206:
                        raise RuntimeError(
                            "weight server did not honor the byte range"
                        )
                    with temporary.open("ab") as handle:
                        shutil.copyfileobj(
                            response,
                            handle,
                            length=256 * 1024,
                        )
            except (TimeoutError, socket.timeout, urllib.error.URLError):
                failures += 1
                if failures >= 10:
                    raise
        if temporary.stat().st_size != expected:
            raise RuntimeError(
                f"weight part {index} has {temporary.stat().st_size} of {expected} bytes"
            )
        temporary.replace(part)
        return index, part

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [
            executor.submit(download_part, index, start, end)
            for index, start, end in ranges
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            index, _ = future.result()
            print(
                f"downloaded CTC weight part {completed}/{len(ranges)} "
                f"(chunk {index})",
                flush=True,
            )
    with partial.open("wb") as output:
        for index, _, _ in ranges:
            with (parts_dir / f"{index:04d}.part").open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if _sha256(partial) != WEIGHT_SHA256:
        raise RuntimeError("CTC weight SHA-256 verification failed")
    partial.replace(destination)
    shutil.rmtree(parts_dir)


def main() -> None:
    output = DEFAULT_OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for filename in MODEL_FILES:
        _download_small(f"{SOURCE_ROOT}/{filename}", output / filename)
    weight = output / "pytorch_model.bin"
    if (
        not weight.is_file()
        or weight.stat().st_size != WEIGHT_SIZE
        or _sha256(weight) != WEIGHT_SHA256
    ):
        _download_weight(weight)
    schema = {
        "schema_version": CTC_SCHEMA_VERSION,
        "feature_dim": CTC_GOP_FEATURE_DIM,
        "blank_id": CTC_BLANK_ID,
        "phone_to_id": CTC_PHONE_TO_ID,
        "source": {
            "repository": "frank613/CTC-based-GOP",
            "commit": SOURCE_COMMIT,
            "paper": "Interspeech 2024 alignment-free CTC GOP",
            "weight_sha256": WEIGHT_SHA256,
        },
        "distribution_notice": (
            "The upstream repository does not declare a license. Confirm "
            "redistribution rights before shipping these weights commercially."
        ),
    }
    (output / CTC_SCHEMA_FILENAME).write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"verified CTC model at {output}")


if __name__ == "__main__":
    main()
