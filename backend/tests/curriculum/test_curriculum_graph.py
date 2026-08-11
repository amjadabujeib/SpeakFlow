import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from speakflow.features.learning_plan.engine.external_curriculum import (
    add_frequency_evidence,
    add_lexical_reference_evidence,
    concept_from_grammar_row,
    concept_from_vocabulary_row,
    normalize_cefr,
)
from speakflow.features.learning_plan.engine.planner import PlanningSkill, build_outline
from speakflow.features.learning_plan.engine.retrieval import CurriculumRetriever
from speakflow.features.learning_plan.engine.schemas import LearnerProfileInput


def _teachable_attributes(
    *, part_of_speech: str = "noun", frequency_count: int = 100
) -> dict:
    return {
        "part_of_speech": part_of_speech,
        "frequency_count": frequency_count,
        "definition": "an item that is useful in a practical task",
        "ipa": "ˈaɪtəm",
    }


def _profile(level: str = "B1") -> LearnerProfileInput:
    return LearnerProfileInput(
        cefr_level=level,
        native_language="Arabic",
        learning_goals=["Communicate at work"],
        interests=["Technology"],
    )


class ExternalCurriculumTests(unittest.TestCase):
    def test_cefr_j_sublevels_normalize_without_inventing_missing_levels(self):
        self.assertEqual(normalize_cefr("A1.2"), "A1")
        self.assertEqual(normalize_cefr("B2"), "B2")
        self.assertEqual(normalize_cefr("C1-C2"), "C1")
        self.assertIsNone(normalize_cefr(""))

    def test_vocabulary_row_keeps_source_claim_and_maps_interest_tags(self):
        concept = concept_from_vocabulary_row(
            {
                "headword": "airport",
                "pos": "noun",
                "CEFR": "A1",
                "CoreInventory 1": "Travel and services vocab",
                "CoreInventory 2": "Things in the town, shops and shopping",
                "Threshold": "Travel",
            }
        )
        self.assertEqual(concept.concept_type, "vocabulary")
        self.assertEqual(concept.cefr_level, "A1")
        self.assertEqual(concept.title, "airport")
        self.assertIn("travel", concept.topic_tags)
        self.assertEqual(concept.attributes["part_of_speech"], "noun")
        self.assertEqual(concept.review_status, "evaluation_only")

    def test_vocabulary_identity_preserves_case_sensitive_homographs(self):
        month = concept_from_vocabulary_row(
            {"headword": "March", "pos": "noun", "CEFR": "A1"}
        )
        movement = concept_from_vocabulary_row(
            {"headword": "march", "pos": "noun", "CEFR": "B1"}
        )
        self.assertNotEqual(month.external_id, movement.external_id)

    def test_frequency_evidence_is_attributed_without_changing_cefr_truth(self):
        concept = concept_from_vocabulary_row(
            {"headword": "network", "pos": "noun", "CEFR": "B1"}
        )
        enriched = add_frequency_evidence([concept], {"network": 123456})[0]
        self.assertEqual(enriched.cefr_level, "B1")
        self.assertEqual(enriched.attributes["frequency_count"], 123456)
        self.assertEqual(
            enriched.attributes["frequency_source_id"],
            "words_cefr_frequency_2024",
        )

    def test_local_definition_and_pronunciation_promote_prototype_target(self):
        concept = concept_from_vocabulary_row(
            {"headword": "network", "pos": "noun", "CEFR": "B1"}
        )
        enriched = add_lexical_reference_evidence([concept])[0]
        self.assertEqual(enriched.review_status, "prototype_ready")
        self.assertTrue(enriched.attributes["definition"])
        self.assertIn("ˈ", enriched.attributes["ipa"])
        self.assertEqual(
            enriched.attributes["definition_source_id"],
            "princeton_wordnet_3_0",
        )

    def test_unsupported_part_of_speech_is_not_promoted_by_an_untyped_sense(self):
        concept = concept_from_vocabulary_row(
            {"headword": "a", "pos": "determiner", "CEFR": "A1"}
        )

        enriched = add_lexical_reference_evidence([concept])[0]

        self.assertEqual(enriched.review_status, "evaluation_only")
        self.assertNotIn("definition", enriched.attributes)
        self.assertNotIn("wordnet_synset", enriched.attributes)

    def test_topic_evidence_avoids_the_wrong_first_wordnet_sense(self):
        screen = concept_from_vocabulary_row(
            {
                "headword": "screen",
                "pos": "noun",
                "CEFR": "A2",
                "CoreInventory 1": "Technology",
            }
        )
        enriched = add_lexical_reference_evidence([screen])[0]
        self.assertEqual(enriched.attributes["wordnet_synset"], "screen.n.03")
        self.assertIn("electronic", enriched.attributes["definition"])

    def test_reviewed_sense_overrides_protect_common_learner_meanings(self):
        expected = {
            "language": "language.n.01",
            "student": "student.n.01",
            "teacher": "teacher.n.01",
            "browser": "browser.n.02",
            "hardware": "hardware.n.03",
            "instrument": "musical_instrument.n.01",
            "queen": "queen.n.02",
            "running": "run.n.07",
            "competition": "contest.n.01",
            "championship": "championship.n.02",
        }
        for word, synset in expected.items():
            with self.subTest(word=word):
                concept = concept_from_vocabulary_row(
                    {
                        "headword": word,
                        "pos": "noun",
                        "CEFR": "A2",
                    }
                )
                enriched = add_lexical_reference_evidence([concept])[0]
                self.assertEqual(enriched.attributes["wordnet_synset"], synset)
                self.assertEqual(
                    enriched.attributes["sense_selection"],
                    "reviewed_override",
                )

        online = concept_from_vocabulary_row(
            {"headword": "online", "pos": "adjective", "CEFR": "A2"}
        )
        enriched_online = add_lexical_reference_evidence([online])[0]
        self.assertEqual(enriched_online.attributes["wordnet_synset"], "on-line.a.02")
        self.assertEqual(
            enriched_online.attributes["sense_selection"], "reviewed_override"
        )

    def test_exact_source_taxonomy_does_not_misread_technical_language(self):
        concept = concept_from_vocabulary_row(
            {
                "headword": "bulimia",
                "pos": "noun",
                "CEFR": "B2",
                "CoreInventory 1": "Technical and legal language",
            }
        )
        self.assertNotIn("technology", concept.topic_tags)
        self.assertNotIn("education", concept.topic_tags)

    def test_broad_media_label_does_not_turn_weather_into_technology(self):
        weather = concept_from_vocabulary_row(
            {
                "headword": "snowstorm",
                "pos": "noun",
                "CEFR": "B1",
                "CoreInventory 1": "Media",
                "Threshold": "Weather",
            }
        )
        network = concept_from_vocabulary_row(
            {
                "headword": "network",
                "pos": "noun",
                "CEFR": "B1",
                "CoreInventory 1": "Media",
            }
        )
        self.assertNotIn("technology", weather.topic_tags)
        self.assertIn("technology", network.topic_tags)

    def test_broad_hobby_label_needs_a_sports_term_for_sports_tag(self):
        curiosity = concept_from_vocabulary_row(
            {
                "headword": "curiosity",
                "pos": "noun",
                "CEFR": "B1",
                "CoreInventory 1": "Hobbies and pastimes",
            }
        )
        referee = concept_from_vocabulary_row(
            {
                "headword": "referee",
                "pos": "noun",
                "CEFR": "B1",
                "CoreInventory 1": "Hobbies and pastimes",
            }
        )
        self.assertNotIn("sports", curiosity.topic_tags)
        self.assertIn("sports", referee.topic_tags)

    def test_grammar_row_keeps_original_sublevel_and_skips_unlevelled_rows(self):
        concept = concept_from_grammar_row(
            {
                "ID": "2-2",
                "Shorthand Code": "PP.are_you",
                "Grammatical Item": "Are you ...?",
                "Sentence Type": "AFF. INT.",
                "CEFR-J Level": "A1.3",
                "Core Inventory": "A1",
                "EGP": "A1-A2",
                "GSELO": "A1",
                "Notes": "",
            }
        )
        self.assertIsNotNone(concept)
        self.assertEqual(concept.cefr_level, "A1")
        self.assertEqual(concept.attributes["source_level"], "A1.3")
        self.assertIsNone(
            concept_from_grammar_row(
                {
                    "ID": "missing",
                    "Shorthand Code": "missing",
                    "Grammatical Item": "Unknown",
                    "CEFR-J Level": "",
                    "FREQ*DISP": "",
                }
            )
        )

    def test_lexical_palette_is_deterministic_and_never_starts_embeddings(self):
        rows = [
            SimpleNamespace(
                id=f"cefr-j:vocabulary:{word}",
                source_id="cefr_j_profiles_2020",
                title=word,
                cefr_level="B1",
                attributes=_teachable_attributes(),
                topic_tags=["technology"],
            )
            for word in ("device", "network", "screen", "update")
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(side_effect=AssertionError("embeddings must stay off"))

        first = retriever.retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="plan:week:1",
            limit=3,
        )
        second = retriever.retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="plan:week:1",
            limit=3,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue(all(item.cefr_level == "B1" for item in first))
        self.assertTrue(all(item.source_id == "cefr_j_profiles_2020" for item in first))
        retriever.embed.assert_not_called()

        remaining = retriever.retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="plan:week:2",
            limit=3,
            exclude_ids={item.id for item in rows[:-1]},
        )
        self.assertEqual([item.id for item in remaining], [rows[-1].id])

    def test_lexical_palette_limits_seeded_variety_to_frequent_candidates(self):
        rows = [
            SimpleNamespace(
                id=f"concept-{index}",
                source_id="cefr_j_profiles_2020",
                title=f"term-{index}",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=1000 - index),
                topic_tags=["technology"],
            )
            for index in range(6)
        ]
        rows[-1].attributes["frequency_count"] = 0
        session = Mock()
        session.scalars.return_value.all.return_value = rows
        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Technology"],
            seed="frequency-filter",
            limit=1,
        )
        self.assertNotEqual(result[0].id, "concept-5")

    def test_lexical_palette_never_fills_with_unrelated_or_duplicate_terms(self):
        rows = [
            SimpleNamespace(
                id="device-noun",
                source_id="cefr_j_profiles_2020",
                title="device",
                cefr_level="A2",
                attributes=_teachable_attributes(frequency_count=100),
                topic_tags=["technology"],
            ),
            SimpleNamespace(
                id="device-verb",
                source_id="cefr_j_profiles_2020",
                title="Device",
                cefr_level="A2",
                attributes=_teachable_attributes(
                    part_of_speech="verb", frequency_count=90
                ),
                topic_tags=["technology"],
            ),
            SimpleNamespace(
                id="unrelated",
                source_id="cefr_j_profiles_2020",
                title="onion",
                cefr_level="A2",
                attributes=_teachable_attributes(frequency_count=1000),
                topic_tags=["food"],
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows

        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="A2",
            interests=["Technology"],
            seed="quality-first",
            limit=3,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title.casefold(), "device")
        self.assertNotIn("onion", [item.title for item in result])

    def test_music_and_history_use_related_reviewed_vocabulary_tags(self):
        rows = [
            SimpleNamespace(
                id="concert",
                source_id="cefr_j_profiles_2020",
                title="concert",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=100),
                topic_tags=["entertainment"],
            ),
            SimpleNamespace(
                id="museum",
                source_id="cefr_j_profiles_2020",
                title="museum",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=90),
                topic_tags=["culture"],
            ),
            SimpleNamespace(
                id="router",
                source_id="cefr_j_profiles_2020",
                title="router",
                cefr_level="B1",
                attributes=_teachable_attributes(frequency_count=1000),
                topic_tags=["technology"],
            ),
        ]
        session = Mock()
        session.scalars.return_value.all.return_value = rows

        result = CurriculumRetriever(client=Mock()).retrieve_lexical_palette(
            session,
            cefr_level="B1",
            interests=["Music", "History"],
            seed="new-interests",
            limit=3,
        )

        self.assertEqual({item.title for item in result}, {"concert", "museum"})


class PrerequisitePlannerTests(unittest.TestCase):
    def test_same_level_dependency_is_delayed_until_an_earlier_week(self):
        domains = [
            "listening",
            "grammar",
            "speaking",
            "reading",
            "vocabulary",
            "pronunciation",
            "discourse",
            "listening",
        ]
        skills = [
            PlanningSkill(
                id=f"skill.b1.{index:02d}",
                domain=domain,
                level="B1",
                title=f"Skill {index}",
                description=f"Reviewed skill {index}",
                outcomes=[f"Can use skill {index}."],
            )
            for index, domain in enumerate(domains, start=1)
        ]
        dependency = {"skill.b1.05": ["skill.b1.01"]}
        outline = build_outline(
            _profile(),
            skills,
            prerequisites_by_skill=dependency,
        )
        week_by_skill: dict[str, int] = {}
        for week in outline["weeks"]:
            for lesson in week["units"][0]["lessons"][:-1]:
                for skill_id in lesson["skill_ids"]:
                    week_by_skill.setdefault(skill_id, week["sequence"])
        self.assertGreater(
            week_by_skill["skill.b1.05"],
            week_by_skill["skill.b1.01"],
        )

    def test_lower_level_prerequisite_is_covered_by_placement_level(self):
        skills = [
            PlanningSkill(
                id="grammar.a2.foundation",
                domain="grammar",
                level="A2",
                title="A2 foundation",
                description="Foundation",
                outcomes=["Can use the foundation."],
            ),
            *[
                PlanningSkill(
                    id=f"{domain}.b1.ready",
                    domain=domain,
                    level="B1",
                    title=f"{domain} ready",
                    description="Ready skill",
                    outcomes=["Can use this skill."],
                )
                for domain in (
                    "grammar",
                    "listening",
                    "speaking",
                    "vocabulary",
                    "reading",
                    "pronunciation",
                    "discourse",
                )
            ],
        ]
        outline = build_outline(
            _profile(),
            skills,
            prerequisites_by_skill={"grammar.b1.ready": ["grammar.a2.foundation"]},
        )
        selected = {
            skill_id
            for week in outline["weeks"]
            for lesson in week["units"][0]["lessons"]
            for skill_id in lesson["skill_ids"]
        }
        self.assertIn("grammar.b1.ready", selected)


if __name__ == "__main__":
    unittest.main()
