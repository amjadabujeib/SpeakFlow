"""Download and verify the two SpeechOcean762 Hugging Face parquet files.

This downloader uses resumable byte ranges because the standard Hub/Xet client
can stall indefinitely on constrained development networks.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REPOSITORY = "mispeech/speechocean762"
FILES = {
    "train-00000-of-00001.parquet": (
        332_843_486,
        "b06fe00f49d2c02c7239677714c68502706e914e029bc01d8e8c6c52416326a7",
    ),
    "test-00000-of-00001.parquet": (
        311_543_671,
        "c951056c8bbc52f776b571c0d02f46b6753f49774a8526f130fcf89400736e98",
    ),
}
DEFAULT_OUTPUT = (
    Path.home()
    / "english_learning_app_data"
    / "speechocean762_hf"
    / "data"
)
CHUNK_SIZE = 4 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolved_url(filename: str) -> str:
    source = (
        f"https://huggingface.co/datasets/{REPOSITORY}/resolve/main/"
        f"data/{filename}"
    )
    request = urllib.request.Request(source, method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.geturl()


def _download_file(
    destination: Path,
    size: int,
    sha256: str,
) -> None:
    if (
        destination.is_file()
        and destination.stat().st_size == size
        and _sha256(destination) == sha256
    ):
        print(f"verified cached {destination.name}")
        return
    url = _resolved_url(destination.name)
    parts_root = destination.with_suffix(destination.suffix + ".parts")
    layout = {"chunk_size": CHUNK_SIZE, "size": size, "sha256": sha256}
    layout_path = parts_root / "layout.json"
    if parts_root.is_dir():
        try:
            existing = json.loads(layout_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing != layout:
            shutil.rmtree(parts_root)
    parts_root.mkdir(parents=True, exist_ok=True)
    layout_path.write_text(
        json.dumps(layout, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ranges = [
        (index, start, min(start + CHUNK_SIZE, size) - 1)
        for index, start in enumerate(range(0, size, CHUNK_SIZE))
    ]

    def fetch(index: int, start: int, end: int) -> Path:
        part = parts_root / f"{index:04d}.part"
        expected = end - start + 1
        if part.is_file() and part.stat().st_size == expected:
            return part
        temporary = part.with_suffix(".tmp")
        if temporary.is_file() and temporary.stat().st_size > expected:
            temporary.unlink()
        failures = 0
        while not temporary.is_file() or temporary.stat().st_size < expected:
            offset = temporary.stat().st_size if temporary.is_file() else 0
            request = urllib.request.Request(
                url,
                headers={"Range": f"bytes={start + offset}-{end}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    if response.status != 206:
                        raise RuntimeError("dataset host ignored the byte range")
                    with temporary.open("ab") as output:
                        shutil.copyfileobj(
                            response,
                            output,
                            length=256 * 1024,
                        )
            except (TimeoutError, socket.timeout, urllib.error.URLError):
                failures += 1
                if failures >= 10:
                    raise
        if temporary.stat().st_size != expected:
            raise RuntimeError(f"incomplete part {index} for {destination.name}")
        temporary.replace(part)
        return part

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [
            executor.submit(fetch, index, start, end)
            for index, start, end in ranges
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            future.result()
            print(
                f"{destination.name}: part {completed}/{len(ranges)}",
                flush=True,
            )
    temporary_destination = destination.with_suffix(
        destination.suffix + ".tmp"
    )
    with temporary_destination.open("wb") as output:
        for index, _, _ in ranges:
            with (parts_root / f"{index:04d}.part").open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if (
        temporary_destination.stat().st_size != size
        or _sha256(temporary_destination) != sha256
    ):
        raise RuntimeError(f"SHA-256 verification failed for {destination.name}")
    temporary_destination.replace(destination)
    shutil.rmtree(parts_root)


def main() -> None:
    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, (size, sha256) in FILES.items():
        _download_file(DEFAULT_OUTPUT / filename, size, sha256)
    print(f"verified SpeechOcean762 parquet files under {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
