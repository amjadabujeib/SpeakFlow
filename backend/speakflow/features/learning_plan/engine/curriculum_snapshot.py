"""Export and restore SpeakFlow's source-attributed RAG curriculum."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from speakflow.config import LOCAL_MODEL_ROOT

from .config import EMBEDDING_DIMENSIONS, OLLAMA_EMBED_MODEL
from .database import session_scope
from .models import CurriculumConcept, CurriculumSource

SNAPSHOT_FORMAT_REVISION = 1
SNAPSHOT_RELEASE = "2026-07-30.1"
SNAPSHOT_PATH = LOCAL_MODEL_ROOT / "curriculum" / "rag-curriculum-v1.zip"
MANIFEST_FILE = "manifest.json"
SOURCES_FILE = "sources.jsonl"
CONCEPTS_FILE = "concepts.jsonl"
EMBEDDINGS_FILE = "embeddings.npy"
SNAPSHOT_FILES = frozenset(
    {MANIFEST_FILE, SOURCES_FILE, CONCEPTS_FILE, EMBEDDINGS_FILE}
)
MAX_SNAPSHOT_UNCOMPRESSED_BYTES = 128 * 1024 * 1024


class CurriculumSnapshotError(RuntimeError):
    """Raised when a curriculum snapshot is missing or not trustworthy."""


@dataclass(frozen=True)
class CurriculumSnapshot:
    manifest: dict[str, Any]
    sources: tuple[dict[str, Any], ...]
    concepts: tuple[dict[str, Any], ...]
    embeddings: np.ndarray


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_line(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _json_lines(values: list[dict[str, Any]]) -> bytes:
    return b"".join(_json_line(value) for value in values)


def _npy_bytes(embeddings: np.ndarray) -> bytes:
    output = io.BytesIO()
    np.save(output, embeddings, allow_pickle=False)
    return output.getvalue()


def _zip_info(name: str) -> zipfile.ZipInfo:
    # A fixed timestamp and permissions make repeated exports byte-for-byte
    # reproducible when the database content has not changed.
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def _source_record(item: CurriculumSource) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "author": item.author,
        "locator": item.locator,
        "license": item.license,
        "version": item.version,
        "checksum": item.checksum,
    }


def _supporting_source_ids(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_source_id") and isinstance(child, str) and child:
                result.add(child)
            result.update(_supporting_source_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_supporting_source_ids(child))
    return result


def _export_records(
    session: Session,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], np.ndarray]:
    rows = session.scalars(
        select(CurriculumConcept).order_by(CurriculumConcept.id)
    ).all()
    if not rows:
        raise CurriculumSnapshotError(
            "the database contains no external curriculum concepts"
        )

    source_ids = {row.source_id for row in rows}
    for row in rows:
        source_ids.update(_supporting_source_ids(row.attributes))
    sources = session.scalars(
        select(CurriculumSource)
        .where(CurriculumSource.id.in_(sorted(source_ids)))
        .order_by(CurriculumSource.id)
    ).all()
    missing_sources = source_ids.difference(item.id for item in sources)
    if missing_sources:
        raise CurriculumSnapshotError(
            f"curriculum references missing sources: {sorted(missing_sources)}"
        )

    concepts: list[dict[str, Any]] = []
    vectors: list[np.ndarray] = []
    for row in rows:
        embedding_row: int | None = None
        if row.embedding is not None:
            if row.embedding_model != OLLAMA_EMBED_MODEL:
                raise CurriculumSnapshotError(
                    f"{row.id} uses {row.embedding_model!r}, expected "
                    f"{OLLAMA_EMBED_MODEL!r}"
                )
            vector = np.asarray(row.embedding, dtype=np.float32)
            if vector.shape != (EMBEDDING_DIMENSIONS,) or not np.isfinite(vector).all():
                raise CurriculumSnapshotError(
                    f"{row.id} has a malformed curriculum embedding"
                )
            embedding_row = len(vectors)
            vectors.append(vector)
        elif row.embedding_model is not None:
            raise CurriculumSnapshotError(
                f"{row.id} names an embedding model without a vector"
            )
        concepts.append(
            {
                "id": row.id,
                "source_id": row.source_id,
                "external_id": row.external_id,
                "concept_type": row.concept_type,
                "cefr_level": row.cefr_level,
                "title": row.title,
                "description": row.description,
                "topic_tags": row.topic_tags,
                "attributes": row.attributes,
                "review_status": row.review_status,
                "content_hash": row.content_hash,
                "embedding_model": row.embedding_model,
                "embedding_row": embedding_row,
                "active": row.active,
            }
        )

    embeddings = (
        np.stack(vectors).astype(np.float32, copy=False)
        if vectors
        else np.empty((0, EMBEDDING_DIMENSIONS), dtype=np.float32)
    )
    return [_source_record(item) for item in sources], concepts, embeddings


def write_snapshot(
    path: Path,
    *,
    sources: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
    embeddings: np.ndarray,
) -> dict[str, Any]:
    source_payload = _json_lines(sources)
    concept_payload = _json_lines(concepts)
    embedding_payload = _npy_bytes(np.asarray(embeddings, dtype=np.float32))
    payloads = {
        SOURCES_FILE: source_payload,
        CONCEPTS_FILE: concept_payload,
        EMBEDDINGS_FILE: embedding_payload,
    }
    manifest = {
        "schema_version": SNAPSHOT_FORMAT_REVISION,
        "snapshot_version": SNAPSHOT_RELEASE,
        "embedding_model": OLLAMA_EMBED_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "source_count": len(sources),
        "concept_count": len(concepts),
        "embedded_concept_count": int(embeddings.shape[0]),
        "files": {
            name: {"size": len(payload), "sha256": _sha256(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    manifest_payload = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(
        temporary,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr(_zip_info(MANIFEST_FILE), manifest_payload)
        for name, payload in sorted(payloads.items()):
            archive.writestr(_zip_info(name), payload)
    temporary.replace(path)
    return manifest


def export_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    with session_scope() as session:
        sources, concepts, embeddings = _export_records(session)
    manifest = write_snapshot(
        path,
        sources=sources,
        concepts=concepts,
        embeddings=embeddings,
    )
    return {**manifest, "path": str(path)}


def _read_json_lines(payload: bytes, *, name: str) -> list[dict[str, Any]]:
    try:
        rows = [
            json.loads(line)
            for line in payload.decode("utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurriculumSnapshotError(f"{name} is malformed") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise CurriculumSnapshotError(f"{name} must contain JSON objects")
    return rows


def _validate_manifest(
    manifest: dict[str, Any],
    payloads: dict[str, bytes],
) -> None:
    if manifest.get("schema_version") != SNAPSHOT_FORMAT_REVISION:
        raise CurriculumSnapshotError("unsupported curriculum snapshot schema")
    if manifest.get("snapshot_version") != SNAPSHOT_RELEASE:
        raise CurriculumSnapshotError("unsupported curriculum snapshot version")
    if manifest.get("embedding_model") != OLLAMA_EMBED_MODEL:
        raise CurriculumSnapshotError(
            "curriculum snapshot embedding model does not match runtime: "
            f"{manifest.get('embedding_model')!r} != {OLLAMA_EMBED_MODEL!r}"
        )
    if manifest.get("embedding_dimensions") != EMBEDDING_DIMENSIONS:
        raise CurriculumSnapshotError(
            "curriculum snapshot embedding width does not match runtime"
        )
    file_records = manifest.get("files")
    if not isinstance(file_records, dict) or set(file_records) != set(payloads):
        raise CurriculumSnapshotError("curriculum snapshot file manifest is incomplete")
    for name, payload in payloads.items():
        record = file_records.get(name)
        if (
            not isinstance(record, dict)
            or record.get("size") != len(payload)
            or record.get("sha256") != _sha256(payload)
        ):
            raise CurriculumSnapshotError(
                f"curriculum snapshot verification failed for {name}"
            )


def _required_string(row: dict[str, Any], key: str, *, context: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise CurriculumSnapshotError(f"{context} has invalid {key}")
    return value


def read_snapshot(path: Path = SNAPSHOT_PATH) -> CurriculumSnapshot:
    if not path.is_file():
        raise CurriculumSnapshotError(f"curriculum snapshot is missing: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != SNAPSHOT_FILES:
                raise CurriculumSnapshotError(
                    "curriculum snapshot contains unexpected files"
                )
            if (
                sum(item.file_size for item in archive.infolist())
                > MAX_SNAPSHOT_UNCOMPRESSED_BYTES
            ):
                raise CurriculumSnapshotError(
                    "curriculum snapshot exceeds the safe size limit"
                )
            manifest = json.loads(archive.read(MANIFEST_FILE))
            payloads = {
                name: archive.read(name)
                for name in (SOURCES_FILE, CONCEPTS_FILE, EMBEDDINGS_FILE)
            }
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise CurriculumSnapshotError(
            f"could not read curriculum snapshot: {path}"
        ) from exc
    if not isinstance(manifest, dict):
        raise CurriculumSnapshotError("curriculum snapshot manifest is malformed")
    _validate_manifest(manifest, payloads)

    sources = _read_json_lines(payloads[SOURCES_FILE], name=SOURCES_FILE)
    concepts = _read_json_lines(payloads[CONCEPTS_FILE], name=CONCEPTS_FILE)
    try:
        embeddings = np.load(
            io.BytesIO(payloads[EMBEDDINGS_FILE]),
            allow_pickle=False,
        )
    except (OSError, ValueError) as exc:
        raise CurriculumSnapshotError(
            "curriculum snapshot embeddings are malformed"
        ) from exc
    if (
        embeddings.dtype != np.float32
        or embeddings.shape
        != (
            manifest.get("embedded_concept_count"),
            EMBEDDING_DIMENSIONS,
        )
        or not np.isfinite(embeddings).all()
    ):
        raise CurriculumSnapshotError(
            "curriculum snapshot embedding matrix is incompatible"
        )
    if len(sources) != manifest.get("source_count"):
        raise CurriculumSnapshotError("curriculum snapshot source count is wrong")
    if len(concepts) != manifest.get("concept_count"):
        raise CurriculumSnapshotError("curriculum snapshot concept count is wrong")

    source_ids = {
        _required_string(row, "id", context="curriculum source") for row in sources
    }
    if len(source_ids) != len(sources):
        raise CurriculumSnapshotError("curriculum snapshot repeats a source ID")
    for row in sources:
        source_id = str(row["id"])
        for key in (
            "title",
            "author",
            "locator",
            "license",
            "version",
            "checksum",
        ):
            _required_string(row, key, context=source_id)
        if len(str(row["checksum"])) != 64:
            raise CurriculumSnapshotError(f"{source_id} has an invalid source checksum")
    concept_ids: set[str] = set()
    external_keys: set[tuple[str, str]] = set()
    content_hashes: set[str] = set()
    embedding_rows: set[int] = set()
    for row in concepts:
        concept_id = _required_string(row, "id", context="curriculum concept")
        source_id = _required_string(row, "source_id", context=concept_id)
        external_id = _required_string(row, "external_id", context=concept_id)
        content_hash = _required_string(row, "content_hash", context=concept_id)
        for key in (
            "concept_type",
            "title",
            "review_status",
        ):
            _required_string(row, key, context=concept_id)
        if row.get("cefr_level") is not None and not isinstance(
            row.get("cefr_level"), str
        ):
            raise CurriculumSnapshotError(f"{concept_id} has an invalid CEFR level")
        if row.get("description") is not None and not isinstance(
            row.get("description"), str
        ):
            raise CurriculumSnapshotError(f"{concept_id} has an invalid description")
        if len(content_hash) != 64 or not isinstance(row.get("active"), bool):
            raise CurriculumSnapshotError(
                f"{concept_id} has invalid integrity metadata"
            )
        if source_id not in source_ids:
            raise CurriculumSnapshotError(f"{concept_id} references an unknown source")
        if (
            concept_id in concept_ids
            or (source_id, external_id) in external_keys
            or content_hash in content_hashes
        ):
            raise CurriculumSnapshotError(
                "curriculum snapshot contains duplicate concept identity"
            )
        concept_ids.add(concept_id)
        external_keys.add((source_id, external_id))
        content_hashes.add(content_hash)
        if not isinstance(row.get("topic_tags"), list) or not isinstance(
            row.get("attributes"), dict
        ):
            raise CurriculumSnapshotError(
                f"{concept_id} has malformed curriculum metadata"
            )
        embedding_row = row.get("embedding_row")
        embedding_model = row.get("embedding_model")
        if embedding_row is None:
            if embedding_model is not None:
                raise CurriculumSnapshotError(
                    f"{concept_id} names an embedding model without a vector"
                )
        elif (
            not isinstance(embedding_row, int)
            or isinstance(embedding_row, bool)
            or embedding_row < 0
            or embedding_row >= embeddings.shape[0]
            or embedding_row in embedding_rows
            or embedding_model != OLLAMA_EMBED_MODEL
        ):
            raise CurriculumSnapshotError(
                f"{concept_id} has an invalid embedding reference"
            )
        else:
            embedding_rows.add(embedding_row)
    if embedding_rows != set(range(embeddings.shape[0])):
        raise CurriculumSnapshotError("curriculum snapshot has unreferenced embeddings")
    return CurriculumSnapshot(
        manifest=manifest,
        sources=tuple(sources),
        concepts=tuple(concepts),
        embeddings=embeddings,
    )


if __name__ == "__main__":
    from .curriculum_snapshot_store import main

    main()
