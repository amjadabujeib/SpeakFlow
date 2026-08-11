from __future__ import annotations

import unittest
from types import SimpleNamespace

from speakflow.features.learning_plan.engine.curriculum_readiness import (
    assess_curriculum,
)
from speakflow.features.learning_plan.engine.seed import seed_records


class CurriculumReadinessTests(unittest.TestCase):
    @staticmethod
    def _seed_catalog():
        _, skills, chunks = seed_records()
        skill_rows = [SimpleNamespace(**item) for item in skills]
        return skill_rows, [item["metadata"] for item in chunks]

    def test_empty_catalog_is_unavailable_for_every_level(self):
        readiness = assess_curriculum([], [])
        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.unavailable_levels, ("A1", "A2", "B1", "B2"))

    def test_complete_reviewed_seed_is_ready(self):
        skills, metadata = self._seed_catalog()
        readiness = assess_curriculum(skills, metadata)
        self.assertTrue(readiness.ready)
        self.assertTrue(readiness.supports("A1"))

    def test_outdated_reviewed_seed_disables_every_level(self):
        skills, metadata = self._seed_catalog()
        readiness = assess_curriculum(
            skills,
            metadata,
            reviewed_source_current=False,
        )
        self.assertFalse(readiness.ready)
        self.assertFalse(readiness.supports("B2"))

    def test_missing_reviewed_chunk_disables_its_level(self):
        skills, metadata = self._seed_catalog()
        metadata = [
            value
            for value in metadata
            if "grammar.a1.core" not in value["skill_ids"]
        ]
        readiness = assess_curriculum(skills, metadata)
        self.assertFalse(readiness.supports("A1"))
        self.assertTrue(readiness.supports("A2"))


if __name__ == "__main__":
    unittest.main()
