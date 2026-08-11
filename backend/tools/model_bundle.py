"""Upload, download, and verify SpeakFlow's private runtime model bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
MODEL_ROOT = BACKEND_ROOT / ".models"
RUNTIME_ROOT = MODEL_ROOT / "runtime"
MODEL_REPO = "speakflow/randomModels"
MANIFEST_NAME = "speakflow-model-bundle.json"
INSTALLED_MANIFEST = MODEL_ROOT / MANIFEST_NAME
BUNDLE_RELEASE = "2026-08-02.1"
MODEL_BUNDLE_FORMAT_REVISION = 2
CHUNK_THRESHOLD = 1024 * 1024 * 1024
CHUNK_SIZE = 16 * 1024 * 1024
CURRICULUM_CHUNK_SIZE = 4 * 1024 * 1024
CHUNK_PREFIX = ".speakflow-parts/"
ALLOWED_DESTINATIONS = (
    "backend/pretrained_models/",
    "backend/.models/",
)
REPOSITORY_OWNED_MODEL_FILES = frozenset(
    {
        "backend/pretrained_models/arabic_pronunciation_ctc_v3/metadata.json",
        "backend/pretrained_models/gopt_ctc/metadata.json",
    }
)


@dataclass(frozen=True)
class Asset:
    source: Path
    destination: str
    chunk_size: int | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_assets(source: Path, destination: str) -> Iterable[Asset]:
    if not source.is_dir():
        raise FileNotFoundError(f"model directory is missing: {source}")
    for path in sorted(source.rglob("*")):
        if path.is_file():
            relative = path.relative_to(source).as_posix()
            yield Asset(path, f"{destination.rstrip('/')}/{relative}")


def local_assets() -> list[Asset]:
    """Resolve only the runtime assets the current application actually uses."""
    assets: list[Asset] = []
    assets.extend(
        _directory_assets(
            BACKEND_ROOT / "pretrained_models" / "wav2vec2_xlsr53_cmu39_ctc",
            "backend/pretrained_models/wav2vec2_xlsr53_cmu39_ctc",
        )
    )
    assets.extend(
        _directory_assets(
            BACKEND_ROOT / "pretrained_models" / "gopt_ctc",
            "backend/pretrained_models/gopt_ctc",
        )
    )
    assets.extend(
        _directory_assets(
            BACKEND_ROOT / "pretrained_models" / "arabic_pronunciation_ctc_v3",
            "backend/pretrained_models/arabic_pronunciation_ctc_v3",
        )
    )
    assets.extend(
        _directory_assets(
            MODEL_ROOT / "gector" / "gector-roberta-base-5k",
            "backend/.models/gector/gector-roberta-base-5k",
        )
    )

    assets.extend(
        _directory_assets(
            RUNTIME_ROOT / "whisperx-small-en",
            "backend/.models/runtime/whisperx-small-en",
        )
    )

    kokoro = RUNTIME_ROOT / "kokoro"
    for relative in ("config.json", "kokoro-v1_0.pth", "voices/af_heart.pt"):
        source = kokoro / relative
        if not source.is_file():
            raise FileNotFoundError(f"Kokoro asset is missing: {source}")
        assets.append(
            Asset(source, f"backend/.models/runtime/kokoro/{relative}")
        )

    aligner = (
        RUNTIME_ROOT
        / "whisperx-align"
        / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    )
    if not aligner.is_file():
        raise FileNotFoundError(f"WhisperX alignment model is missing: {aligner}")
    assets.append(
        Asset(
            aligner,
            "backend/.models/runtime/whisperx-align/"
            "wav2vec2_fairseq_base_ls960_asr_ls960.pth",
        )
    )

    nltk_resources = (
        "corpora/cmudict.zip",
        "corpora/wordnet.zip",
        "taggers/averaged_perceptron_tagger_eng.zip",
        "tokenizers/punkt_tab.zip",
    )
    for relative in nltk_resources:
        local_resource = MODEL_ROOT / "nltk_data" / relative
        if not local_resource.is_file():
            raise FileNotFoundError(
                f"NLTK bundle resource is missing: {local_resource}"
            )
        assets.append(
            Asset(
                local_resource,
                f"backend/.models/nltk_data/{relative}",
            )
        )
    curriculum_snapshot = (
        MODEL_ROOT / "curriculum" / "rag-curriculum-v1.zip"
    )
    if not curriculum_snapshot.is_file():
        raise FileNotFoundError(
            "RAG curriculum snapshot is missing. Export it with "
            "`python -m speakflow.features.learning_plan.engine.curriculum_snapshot export` before publishing "
            f"the bundle: {curriculum_snapshot}"
        )
    assets.append(
        Asset(
            curriculum_snapshot,
            "backend/.models/curriculum/rag-curriculum-v1.zip",
            chunk_size=CURRICULUM_CHUNK_SIZE,
        )
    )
    return sorted(
        (
            asset
            for asset in assets
            if asset.destination not in REPOSITORY_OWNED_MODEL_FILES
        ),
        key=lambda item: item.destination,
    )


def _file_entry(asset: Asset) -> dict:
    size = asset.source.stat().st_size
    if size < CHUNK_THRESHOLD and asset.chunk_size is None:
        return {
            "path": asset.destination,
            "size": size,
            "sha256": _sha256(asset.source),
        }

    chunk_size = asset.chunk_size or CHUNK_SIZE
    if chunk_size <= 0:
        raise ValueError(f"invalid chunk size for {asset.destination}")
    digest = hashlib.sha256()
    chunks: list[dict] = []
    with asset.source.open("rb") as handle:
        for index, block in enumerate(
            iter(lambda: handle.read(chunk_size), b"")
        ):
            digest.update(block)
            chunks.append(
                {
                    "index": index,
                    "size": len(block),
                    "sha256": hashlib.sha256(block).hexdigest(),
                }
            )
    file_hash = digest.hexdigest()
    for chunk in chunks:
        chunk["path"] = (
            f"{CHUNK_PREFIX}{file_hash}/{int(chunk['index']):05d}.part"
        )
        del chunk["index"]
    return {
        "path": asset.destination,
        "size": size,
        "sha256": file_hash,
        "parts": chunks,
    }


def _manifest(assets: list[Asset]) -> dict:
    return {
        "schema_version": MODEL_BUNDLE_FORMAT_REVISION,
        "bundle_version": BUNDLE_RELEASE,
        "files": [_file_entry(asset) for asset in assets],
    }


def _validate_remote_path(value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe model path in manifest: {value}")
    normalized = pure.as_posix()
    if not any(normalized.startswith(prefix) for prefix in ALLOWED_DESTINATIONS):
        raise ValueError(f"unsupported model destination: {value}")
    destination = (PROJECT_ROOT / Path(*pure.parts)).resolve()
    if PROJECT_ROOT.resolve() not in destination.parents:
        raise ValueError(f"model path escapes the project: {value}")
    return destination


def _validate_part_path(value: str) -> PurePosixPath:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe model part path in manifest: {value}")
    normalized = pure.as_posix()
    if not normalized.startswith(CHUNK_PREFIX):
        raise ValueError(f"unsupported model part path: {value}")
    return pure


def _hub_token() -> str:
    from huggingface_hub import get_token, login

    token = os.environ.get("HF_TOKEN") or get_token()
    if token:
        return token
    print("Hugging Face authentication is required for the private model repo.")
    login()
    token = get_token()
    if not token:
        raise RuntimeError("Hugging Face authentication did not provide a token")
    return token


def upload() -> None:
    os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
    from huggingface_hub import HfApi

    token = _hub_token()
    assets = local_assets()
    manifest = _manifest(assets)
    api = HfApi(token=token)
    for index, (asset, entry) in enumerate(
        zip(assets, manifest["files"], strict=True),
        start=1,
    ):
        parts = entry.get("parts")
        if not parts:
            print(f"[{index}/{len(assets)}] Uploading {asset.destination}")
            api.upload_file(
                path_or_fileobj=asset.source,
                path_in_repo=asset.destination,
                repo_id=MODEL_REPO,
                repo_type="model",
                commit_message=f"Upload {asset.destination}",
            )
            continue

        with asset.source.open("rb") as handle:
            for part_index, part in enumerate(parts, start=1):
                data = handle.read(int(part["size"]))
                if (
                    len(data) != int(part["size"])
                    or hashlib.sha256(data).hexdigest() != part["sha256"]
                ):
                    raise RuntimeError(
                        f"model changed while uploading: {asset.destination}"
                    )
                print(
                    f"[{index}/{len(assets)} part "
                    f"{part_index}/{len(parts)}] Uploading {asset.destination}"
                )
                api.upload_file(
                    path_or_fileobj=data,
                    path_in_repo=str(part["path"]),
                    repo_id=MODEL_REPO,
                    repo_type="model",
                    commit_message=(
                        f"Upload {asset.destination} "
                        f"part {part_index}/{len(parts)}"
                    ),
                )
            if handle.read(1):
                raise RuntimeError(
                    f"model changed while uploading: {asset.destination}"
                )
    api.upload_file(
        path_or_fileobj=json.dumps(manifest, indent=2, sort_keys=True).encode(),
        path_in_repo=MANIFEST_NAME,
        repo_id=MODEL_REPO,
        repo_type="model",
        commit_message=f"Publish SpeakFlow model bundle {BUNDLE_RELEASE}",
    )
    print(
        f"Published {len(assets)} files to private model repo {MODEL_REPO}."
    )


def _installed(entry: dict) -> bool:
    relative = str(entry["path"])
    destination = _validate_remote_path(relative)
    expected_size = int(entry["size"])
    expected_hash = str(entry["sha256"])
    return (
        destination.is_file()
        and destination.stat().st_size == expected_size
        and _sha256(destination) == expected_hash
    )


def _validate_parts(entry: dict) -> list[dict]:
    parts = entry.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError(f"invalid model parts for {entry.get('path')}")
    total = 0
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError(f"invalid model part for {entry.get('path')}")
        _validate_part_path(str(part.get("path", "")))
        size = int(part.get("size", -1))
        digest = str(part.get("sha256", ""))
        if size <= 0 or len(digest) != 64:
            raise ValueError(f"invalid model part for {entry.get('path')}")
        total += size
    if total != int(entry["size"]):
        raise ValueError(f"model parts have the wrong size for {entry['path']}")
    return parts


def _staged_source(staging: Path, entry: dict) -> Path:
    parts = entry.get("parts")
    if not parts:
        return staging / Path(*PurePosixPath(str(entry["path"])).parts)

    verified_parts = _validate_parts(entry)
    reconstructed = staging / ".reconstructed" / Path(
        *PurePosixPath(str(entry["path"])).parts
    )
    reconstructed.parent.mkdir(parents=True, exist_ok=True)
    with reconstructed.open("wb") as output:
        for part in verified_parts:
            source = staging / Path(
                *_validate_part_path(str(part["path"])).parts
            )
            if (
                not source.is_file()
                or source.stat().st_size != int(part["size"])
                or _sha256(source) != str(part["sha256"])
            ):
                raise RuntimeError(
                    f"downloaded model part failed verification: "
                    f"{part['path']}"
                )
            with source.open("rb") as handle:
                shutil.copyfileobj(handle, output, length=8 * 1024 * 1024)
    return reconstructed


def download(revision: str) -> None:
    os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
    from huggingface_hub import hf_hub_download, snapshot_download

    token = _hub_token()
    manifest_path = Path(
        hf_hub_download(
            MODEL_REPO,
            filename=MANIFEST_NAME,
            revision=revision,
            token=token,
            force_download=True,
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("schema_version", -1)) != MODEL_BUNDLE_FORMAT_REVISION:
        raise ValueError("unsupported SpeakFlow model bundle manifest")
    bundle_version = manifest.get("bundle_version")
    if not isinstance(bundle_version, str) or not bundle_version:
        raise ValueError("model bundle manifest has no version")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("model bundle manifest contains no files")
    for entry in files:
        _validate_remote_path(str(entry["path"]))
    # These small runtime contracts are tracked by Git. Older private bundle
    # manifests included copies containing machine-specific training paths;
    # never let a bundle download overwrite the repository-owned files.
    files = [
        entry
        for entry in files
        if str(entry["path"]) not in REPOSITORY_OWNED_MODEL_FILES
    ]
    missing: list[dict] = []
    for entry in files:
        relative = str(entry["path"])
        if _installed(entry):
            print(f"Already verified: {relative}")
        else:
            missing.append(entry)
    staging = MODEL_ROOT / ".bundle-download"
    if missing:
        patterns: list[str] = []
        for entry in missing:
            parts = entry.get("parts")
            if parts:
                patterns.extend(
                    str(part["path"]) for part in _validate_parts(entry)
                )
            else:
                patterns.append(str(entry["path"]))
        snapshot_download(
            MODEL_REPO,
            revision=revision,
            token=token,
            local_dir=staging,
            allow_patterns=patterns,
        )
        for entry in missing:
            relative = str(entry["path"])
            source = _staged_source(staging, entry)
            expected_size = int(entry["size"])
            expected_hash = str(entry["sha256"])
            if (
                not source.is_file()
                or source.stat().st_size != expected_size
                or _sha256(source) != expected_hash
            ):
                raise RuntimeError(
                    f"downloaded model failed verification: {relative}"
                )
            destination = _validate_remote_path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.unlink(missing_ok=True)
            source.replace(destination)
            print(f"Installed: {relative}")
        shutil.rmtree(staging)
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, INSTALLED_MANIFEST)
    print(
        f"Installed SpeakFlow model bundle {bundle_version}."
    )


def inventory() -> None:
    assets = local_assets()
    total = sum(asset.source.stat().st_size for asset in assets)
    for asset in assets:
        print(f"{asset.source.stat().st_size:>12}  {asset.destination}")
    print(f"{len(assets)} files, {total / (1024 ** 3):.2f} GiB total")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("upload")
    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--revision", default="main")
    subparsers.add_parser("inventory")
    args = parser.parse_args()

    if args.command == "upload":
        upload()
    elif args.command == "download":
        download(args.revision)
    else:
        inventory()


if __name__ == "__main__":
    main()
