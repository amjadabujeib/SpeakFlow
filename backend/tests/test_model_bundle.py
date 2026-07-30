from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_bundle


class ModelBundlePathTests(unittest.TestCase):
    def test_model_repository_is_fixed_for_every_installation(self):
        self.assertEqual(model_bundle.MODEL_REPO, "speakflow/randomModels")

    def test_runtime_model_destination_stays_inside_project(self):
        destination = model_bundle._validate_remote_path(
            "backend/.models/runtime/kokoro/config.json"
        )
        self.assertTrue(destination.is_relative_to(model_bundle.PROJECT_ROOT))

    def test_curriculum_snapshot_is_a_managed_runtime_asset(self):
        destination = model_bundle._validate_remote_path(
            "backend/.models/curriculum/rag-curriculum-v1.zip"
        )
        self.assertTrue(destination.is_relative_to(model_bundle.PROJECT_ROOT))
        destinations = {asset.destination for asset in model_bundle.local_assets()}
        self.assertIn(
            "backend/.models/curriculum/rag-curriculum-v1.zip",
            destinations,
        )

    def test_manifest_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            model_bundle._validate_remote_path(
                "backend/.models/../../outside.bin"
            )

    def test_manifest_rejects_unmanaged_project_files(self):
        with self.assertRaises(ValueError):
            model_bundle._validate_remote_path("backend/main.py")

    def test_manifest_rejects_part_parent_traversal(self):
        with self.assertRaises(ValueError):
            model_bundle._validate_part_path(
                ".speakflow-parts/hash/../../outside.part"
            )

    def test_large_asset_is_split_into_verified_parts(self):
        payload = b"abcdefghij"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "model.bin"
            source.write_bytes(payload)
            asset = model_bundle.Asset(
                source,
                "backend/pretrained_models/test/model.bin",
            )
            with (
                patch.object(model_bundle, "CHUNK_THRESHOLD", 5),
                patch.object(model_bundle, "CHUNK_SIZE", 4),
            ):
                entry = model_bundle._file_entry(asset)

        self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual([part["size"] for part in entry["parts"]], [4, 4, 2])
        for part in entry["parts"]:
            model_bundle._validate_part_path(part["path"])

    def test_asset_can_force_smaller_verified_parts(self):
        payload = b"abcdefghij"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "curriculum.zip"
            source.write_bytes(payload)
            entry = model_bundle._file_entry(
                model_bundle.Asset(
                    source,
                    "backend/.models/curriculum/curriculum.zip",
                    chunk_size=4,
                )
            )

        self.assertEqual([part["size"] for part in entry["parts"]], [4, 4, 2])

    def test_staged_parts_reconstruct_original_file(self):
        payload = b"abcdefghij"
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            parts = []
            for index, block in enumerate((b"abcd", b"efgh", b"ij")):
                relative = (
                    f".speakflow-parts/test/{index:05d}.part"
                )
                part_path = staging / relative
                part_path.parent.mkdir(parents=True, exist_ok=True)
                part_path.write_bytes(block)
                parts.append(
                    {
                        "path": relative,
                        "size": len(block),
                        "sha256": hashlib.sha256(block).hexdigest(),
                    }
                )
            entry = {
                "path": "backend/pretrained_models/test/model.bin",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "parts": parts,
            }
            reconstructed = model_bundle._staged_source(staging, entry)
            self.assertEqual(reconstructed.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
