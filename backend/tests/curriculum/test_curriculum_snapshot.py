from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from speakflow.features.learning_plan.engine.config import (
    EMBEDDING_DIMENSIONS,
    OLLAMA_EMBED_MODEL,
)
from speakflow.features.learning_plan.engine.curriculum_snapshot import (
    CONCEPTS_FILE,
    SNAPSHOT_FILES,
    CurriculumSnapshotError,
    read_snapshot,
    write_snapshot,
)


def _source() -> dict:
    return {
        "id": "test_source",
        "title": "Test source",
        "author": "Test author",
        "locator": "repo:test",
        "license": "Test license",
        "version": "1",
        "checksum": "a" * 64,
    }


def _concept(*, embedded: bool) -> dict:
    return {
        "id": f"test_source:vocabulary:{'embedded' if embedded else 'plain'}",
        "source_id": "test_source",
        "external_id": f"vocabulary:{'embedded' if embedded else 'plain'}",
        "concept_type": "vocabulary",
        "cefr_level": "A2",
        "title": "journey" if embedded else "ticket",
        "description": None,
        "topic_tags": ["travel"],
        "attributes": {"part_of_speech": "noun"},
        "review_status": "prototype_ready" if embedded else "evaluation_only",
        "content_hash": ("b" if embedded else "c") * 64,
        "embedding_model": OLLAMA_EMBED_MODEL if embedded else None,
        "embedding_row": 0 if embedded else None,
        "active": True,
    }


class CurriculumSnapshotTests(unittest.TestCase):
    def _write_fixture(self, path: Path) -> None:
        write_snapshot(
            path,
            sources=[_source()],
            concepts=[_concept(embedded=True), _concept(embedded=False)],
            embeddings=np.full(
                (1, EMBEDDING_DIMENSIONS),
                0.25,
                dtype=np.float32,
            ),
        )

    def test_snapshot_round_trip_preserves_metadata_and_embeddings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curriculum.zip"
            self._write_fixture(path)
            snapshot = read_snapshot(path)

        self.assertEqual(snapshot.manifest["concept_count"], 2)
        self.assertEqual(snapshot.manifest["embedded_concept_count"], 1)
        self.assertEqual(snapshot.sources[0]["id"], "test_source")
        self.assertEqual(snapshot.concepts[0]["title"], "journey")
        self.assertEqual(
            snapshot.embeddings.shape,
            (1, EMBEDDING_DIMENSIONS),
        )
        self.assertTrue(np.all(snapshot.embeddings == np.float32(0.25)))

    def test_identical_content_produces_identical_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            self._write_fixture(first)
            self._write_fixture(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_snapshot_rejects_payload_changed_after_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curriculum.zip"
            self._write_fixture(path)
            with zipfile.ZipFile(path) as archive:
                payloads = {
                    name: archive.read(name)
                    for name in SNAPSHOT_FILES
                }
            concepts = payloads[CONCEPTS_FILE].decode("utf-8")
            payloads[CONCEPTS_FILE] = concepts.replace(
                '"journey"', '"different"'
            ).encode("utf-8")
            with zipfile.ZipFile(path, "w") as archive:
                for name, payload in payloads.items():
                    archive.writestr(name, payload)

            with self.assertRaisesRegex(
                CurriculumSnapshotError,
                "verification failed",
            ):
                read_snapshot(path)

    def test_snapshot_rejects_duplicate_embedding_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curriculum.zip"
            concepts = [_concept(embedded=True), _concept(embedded=True)]
            concepts[1] = {
                **concepts[1],
                "id": "test_source:vocabulary:second",
                "external_id": "vocabulary:second",
                "title": "second",
                "content_hash": "d" * 64,
            }
            write_snapshot(
                path,
                sources=[_source()],
                concepts=concepts,
                embeddings=np.full(
                    (1, EMBEDDING_DIMENSIONS),
                    0.25,
                    dtype=np.float32,
                ),
            )

            with self.assertRaisesRegex(
                CurriculumSnapshotError,
                "invalid embedding reference",
            ):
                read_snapshot(path)


if __name__ == "__main__":
    unittest.main()
