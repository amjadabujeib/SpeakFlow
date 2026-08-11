from __future__ import annotations

import unittest

from speakflow.features.learning_plan.engine.service_generation_worker import (
    _classify_lexical_exposure,
)
from tests.learning_plan.support.weekly_mission_test_support import (
    RetrievedConcept,
    _compile,
    _valid_draft,
    _week_fixture,
    prepare_week,
)


class WeeklyVocabularyPolicyTests(unittest.TestCase):
    def test_current_terms_are_excluded_and_old_revision_terms_are_review_only(self):
        current = {
            "provenance": {
                "writer_request": {
                    "prototype_targets": [
                        {"concept_id": "network-id", "term": "Network"}
                    ]
                }
            }
        }
        historical = {
            "provenance": {
                "writer_request": {
                    "prototype_targets": [
                        {"concept_id": "network-id", "term": "network"},
                        {"concept_id": "device-id", "term": "Device"},
                    ]
                }
            }
        }

        used_ids, used_terms, historical_ids, historical_terms = (
            _classify_lexical_exposure(
                [("current", current), ("old", historical)],
                current_revision_id="current",
            )
        )

        self.assertEqual(used_ids, {"network-id"})
        self.assertEqual(used_terms, {"network"})
        self.assertEqual(historical_ids, {"device-id"})
        self.assertEqual(historical_terms, {"device"})

    def test_week_without_a_vocabulary_domain_still_teaches_two_terms(self):
        _, lessons, chunks, _ = _week_fixture(2)
        self.assertNotIn("vocabulary", [item["type"] for item in lessons])
        concepts = [
            RetrievedConcept(
                id="cefr_j_profiles_2020:vocabulary:network",
                source_id="cefr_j_profiles_2020",
                title="network",
                cefr_level="B1",
                part_of_speech="noun",
                topic_tags=["technology"],
                definition="an interconnected system of people or things",
                ipa="ˈnɛtˌwɝk",
                definition_source_id="princeton_wordnet_3_0",
                pronunciation_source_id="cmudict_local",
                selection_tier="direct_interest",
            ),
            RetrievedConcept(
                id="cefr_j_profiles_2020:vocabulary:approach",
                source_id="cefr_j_profiles_2020",
                title="approach",
                cefr_level="B1",
                part_of_speech="noun",
                topic_tags=[],
                definition="a way of dealing with a problem",
                ipa="əˈproʊtʃ",
                definition_source_id="princeton_wordnet_3_0",
                pronunciation_source_id="cmudict_local",
                selection_tier="general_context",
            ),
        ]

        prepared = prepare_week(
            lessons=lessons,
            chunks=chunks,
            lexical_palette=concepts,
            support_language="Arabic",
        )

        targets = [
            item.prototype_target
            for item in prepared.context_requests.values()
            if item.prototype_target is not None
        ]
        self.assertEqual([item.title for item in targets], ["network", "approach"])
        self.assertTrue(
            all(
                request.lesson_key == lessons[0]["lesson_key"]
                for request in prepared.context_requests.values()
                if request.prototype_target is not None
            )
        )

        compiled = _compile(prepared, _valid_draft(prepared))
        first_lesson = compiled[lessons[0]["lesson_key"]][0]
        concept_ids = {
            activity["data"].get("concept_id")
            for activity in first_lesson["content"]["activities"]
            if activity["type"] == "vocabulary_card"
        }
        self.assertEqual(concept_ids, {item.id for item in concepts})


if __name__ == "__main__":
    unittest.main()
