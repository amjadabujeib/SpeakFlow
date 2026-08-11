from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from speakflow.features.learning_plan.engine.config import OLLAMA_EMBED_MODEL
from speakflow.features.learning_plan.engine.curriculum_snapshot import (
    SNAPSHOT_PATH,
    read_snapshot,
)
from speakflow.features.learning_plan.engine.external_curriculum import (
    concept_from_vocabulary_row,
)
from speakflow.features.learning_plan.engine.interest_vocabulary import (
    REVIEWED_INTEREST_TERMS,
    concept_term_key,
    effective_interest_tags,
    reviewed_term_count,
)
from speakflow.features.learning_plan.engine.lexical_policy import (
    is_teachable_lexical_concept,
)
from speakflow.features.learning_plan.engine.mission_catalog import (
    CEFR_CONSTRAINT_BY_LEVEL,
    INTEREST_TAGS,
)
from speakflow.features.learning_plan.engine.retrieval import CurriculumRetriever


def _teachable_attributes(*, frequency_count: int) -> dict:
    return {
        "part_of_speech": "noun",
        "frequency_count": frequency_count,
        "definition": "an item that is useful in a practical task",
        "ipa": "ˈaɪtəm",
    }


class InterestVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot_concepts = (
            read_snapshot(SNAPSHOT_PATH).concepts if SNAPSHOT_PATH.is_file() else None
        )

    def _managed_snapshot_concepts(self) -> list[dict]:
        if self.snapshot_concepts is None:
            self.skipTest("managed curriculum snapshot is not installed")
        return self.snapshot_concepts

    def test_every_reviewed_assignment_exists_in_the_source_catalog(self):
        source_keys = {
            concept_term_key(
                cefr_level=item["cefr_level"],
                title=item["title"],
                part_of_speech=item["attributes"].get("part_of_speech"),
            )
            for item in self._managed_snapshot_concepts()
            if item["concept_type"] == "vocabulary"
        }
        reviewed_keys = set().union(*REVIEWED_INTEREST_TERMS.values())

        self.assertEqual(len(reviewed_keys), reviewed_term_count())
        self.assertEqual(reviewed_keys - source_keys, set())

    def test_every_supported_level_and_interest_has_eight_teachable_terms(self):
        coverage = {
            (level, interest.id): set()
            for level in CEFR_CONSTRAINT_BY_LEVEL
            for interest in INTEREST_TAGS
        }
        for item in self._managed_snapshot_concepts():
            if (
                not item["active"]
                or item["concept_type"] != "vocabulary"
                or item["review_status"] != "prototype_ready"
            ):
                continue
            attributes = item["attributes"]
            level = item["cefr_level"]
            if level not in CEFR_CONSTRAINT_BY_LEVEL:
                continue
            if not is_teachable_lexical_concept(
                title=item["title"],
                part_of_speech=attributes.get("part_of_speech"),
                cefr_level=level,
                source_definition=attributes.get("definition", ""),
                ipa=attributes.get("ipa", ""),
                request_id=item["id"],
            ):
                continue
            tags = effective_interest_tags(
                item["topic_tags"],
                cefr_level=level,
                title=item["title"],
                part_of_speech=attributes.get("part_of_speech"),
            )
            for tag in tags:
                if (level, tag) in coverage:
                    coverage[(level, tag)].add(item["title"].casefold())

        deficits = {
            f"{level}/{interest}": len(terms)
            for (level, interest), terms in coverage.items()
            if len(terms) < 8
        }
        self.assertEqual(deficits, {})

    def test_review_is_exact_by_level_word_and_part_of_speech(self):
        a1_phone = effective_interest_tags(
            ["daily_life"],
            cefr_level="A1",
            title="phone",
            part_of_speech="noun",
        )
        b2_phone = effective_interest_tags(
            ["daily_life"],
            cefr_level="B2",
            title="phone",
            part_of_speech="noun",
        )

        self.assertIn("technology", a1_phone)
        self.assertNotIn("technology", b2_phone)

    def test_review_removes_known_broad_taxonomy_false_positives(self):
        tags = effective_interest_tags(
            ["science", "technology"],
            cefr_level="B1",
            title="chemical",
            part_of_speech="noun",
        )
        source_concept = concept_from_vocabulary_row(
            {
                "headword": "chemical",
                "pos": "noun",
                "CEFR": "B1",
                "CoreInventory 1": "Scientific development",
            }
        )

        self.assertEqual(tags, ["science"])
        self.assertNotIn("technology", source_concept.topic_tags)

    def test_direct_interest_vocabulary_outranks_related_themes(self):
        rows = [
            SimpleNamespace(
                id="flute",
                source_id="cefr_j_profiles_2020",
                title="flute",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=1),
                topic_tags=["entertainment"],
            ),
            SimpleNamespace(
                id="museum",
                source_id="cefr_j_profiles_2020",
                title="museum",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=1_000_000),
                topic_tags=["culture"],
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows

        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Music"],
            seed="exact-before-related",
            limit=1,
        )

        self.assertEqual([item.title for item in result], ["flute"])
        self.assertIn("music", result[0].topic_tags)

    def test_semantic_retrieval_admits_only_a_safe_relevant_general_term(self):
        rows = [
            SimpleNamespace(
                id="network",
                source_id="cefr_j_profiles_2020",
                title="network",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=100),
                topic_tags=["technology"],
                embedding=[0.0],
                embedding_model=OLLAMA_EMBED_MODEL,
            ),
            SimpleNamespace(
                id="approach",
                source_id="cefr_j_profiles_2020",
                title="approach",
                cefr_level="B1",
                attributes={
                    "part_of_speech": "noun",
                    "frequency_count": 90,
                    "definition": "a way of dealing with a problem",
                    "ipa": "əˈproʊtʃ",
                },
                topic_tags=[],
                embedding=[0.0],
                embedding_model=OLLAMA_EMBED_MODEL,
            ),
            SimpleNamespace(
                id="onion",
                source_id="cefr_j_profiles_2020",
                title="onion",
                cefr_level="B1",
                attributes={
                    "part_of_speech": "noun",
                    "frequency_count": 1_000,
                    "definition": "a round vegetable with a strong smell",
                    "ipa": "ˈʌnjən",
                },
                topic_tags=[],
                embedding=[0.0],
                embedding_model=OLLAMA_EMBED_MODEL,
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows
        session.execute.return_value = [
            SimpleNamespace(id="network", distance=0.20),
            SimpleNamespace(id="approach", distance=0.52),
            SimpleNamespace(id="onion", distance=0.80),
        ]
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(return_value=[[0.0] * 768])

        result = retriever.retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="technology-problem",
            limit=4,
            query_text="solve a familiar technology problem",
        )

        self.assertEqual({item.title for item in result}, {"network", "approach"})
        approach = next(item for item in result if item.title == "approach")
        self.assertEqual(approach.selection_tier, "general_context")
        self.assertNotIn("onion", [item.title for item in result])

    def test_fresh_topical_term_outranks_a_previously_seen_term(self):
        rows = [
            SimpleNamespace(
                id=word,
                source_id="cefr_j_profiles_2020",
                title=word,
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=100),
                topic_tags=["technology"],
            )
            for word in ("network", "device")
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows

        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="prefer-new",
            limit=1,
            deprioritize_terms={"network"},
        )

        self.assertEqual([item.title for item in result], ["device"])
        self.assertFalse(result[0].previously_seen)

    def test_unsupported_part_of_speech_never_enters_the_runtime_palette(self):
        rows = [
            SimpleNamespace(
                id="determiner-a",
                source_id="cefr_j_profiles_2020",
                title="a",
                cefr_level="A1",
                attributes={"part_of_speech": "determiner", "frequency_count": 999},
                topic_tags=["technology"],
            ),
            SimpleNamespace(
                id="phone",
                source_id="cefr_j_profiles_2020",
                title="phone",
                cefr_level="A1",
                attributes=_teachable_attributes(frequency_count=100),
                topic_tags=["technology"],
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows

        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="A1",
            interests=["Technology"],
            seed="supported-pos-only",
            limit=2,
        )

        self.assertEqual([item.title for item in result], ["phone"])


if __name__ == "__main__":
    unittest.main()
