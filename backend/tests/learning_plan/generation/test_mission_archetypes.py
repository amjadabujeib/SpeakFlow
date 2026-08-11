from __future__ import annotations

import unittest

from speakflow.features.learning_plan.engine.mission_archetypes_extended import (
    EXTENDED_SCENARIO_ARCHETYPES,
)
from speakflow.features.learning_plan.engine.mission_catalog import (
    GOAL_CLUSTERS,
    INTEREST_TAGS,
    SCENARIO_ARCHETYPES,
    FactPolicy,
    select_scenario_archetype,
)


class MissionArchetypeQualityTests(unittest.TestCase):
    def test_direct_interest_context_outranks_theme_only_compatibility(self) -> None:
        for goal in GOAL_CLUSTERS:
            for interest in INTEREST_TAGS:
                direct = [
                    scenario
                    for scenario in SCENARIO_ARCHETYPES
                    if goal.id in scenario.compatible_goal_ids
                    and scenario.context_family in interest.context_families
                ]
                if not direct:
                    continue
                for seed in ("", "catalog-review", "another-learner"):
                    with self.subTest(goal=goal.id, interest=interest.id, seed=seed):
                        selected = select_scenario_archetype(
                            goal=goal.id,
                            interest=interest.id,
                            week_number=1,
                            stable_seed=seed,
                        )
                        self.assertIn(goal.id, selected.compatible_goal_ids)
                        self.assertIn(
                            selected.context_family,
                            interest.context_families,
                        )

    def test_extended_b2_tasks_name_the_evidence_they_require(self) -> None:
        by_id = {item.id: item for item in EXTENDED_SCENARIO_ARCHETYPES}
        required_evidence = {
            "science.present_comparison": ("limitation",),
            "everyday.give_and_receive_directions": ("map", "obstacle"),
            "everyday.ask_for_and_give_recommendations": ("trade-off", "criteria"),
            "work.give_and_respond_to_feedback": ("constraints", "priorities"),
            "work.handle_a_meeting": ("disputed", "constraint"),
            "study.use_a_reference_source": ("conflicting",),
            "study.give_a_short_presentation": ("audience question",),
            "technology.communicate_a_digital_process": ("decision", "recovery"),
            "technology.evaluate_digital_information": ("supporting", "cautionary"),
            "entertainment.plan_a_fictional_event": ("access", "contingency"),
            "entertainment.review_a_fictional_product": ("contrasting",),
            "sports.discuss_performance": ("tension",),
            "sports.explain_fictional_rules": ("edge case",),
            "culture.interpret_a_cultural_practice": ("change", "misconception"),
        }
        for scenario_id, expected_terms in required_evidence.items():
            scenario = by_id[scenario_id]
            b2 = scenario.outcome_for("B2")
            contract = " ".join(
                (
                    scenario.premise,
                    *scenario.setting_slots,
                    b2.can_do,
                    b2.permitted_support,
                )
            ).casefold()
            with self.subTest(scenario=scenario_id):
                for term in expected_terms:
                    self.assertIn(term, contract)

    def test_sensitive_real_topics_require_sources_and_cannot_read_as_live_advice(
        self,
    ) -> None:
        by_id = {item.id: item for item in EXTENDED_SCENARIO_ARCHETYPES}
        trip = by_id["travel.prepare_for_a_trip"]
        story = by_id["culture.respond_to_shared_story"]
        practice = by_id["culture.interpret_a_cultural_practice"]

        self.assertIn("real destination", trip.premise)
        self.assertIn("dated official evidence or explicitly simulated", trip.premise)
        self.assertIn("current travel advice", trip.premise)
        self.assertIn("public-domain, licensed, or community-authorized", story.premise)
        self.assertIn("without treating one story as representative", story.premise)
        self.assertNotIn("personal experience", story.outcome_for("B1").can_do)
        self.assertIn("community-authored", practice.premise)
        self.assertIn(
            "without exposing restricted or sacred knowledge", practice.premise
        )

    def test_every_archetype_uses_the_real_world_evidence_policy(self) -> None:
        for scenario in SCENARIO_ARCHETYPES:
            with self.subTest(scenario=scenario.id):
                self.assertIs(
                    scenario.fact_policy,
                    FactPolicy.REAL_WORLD_WITH_SUPPLIED_EVIDENCE,
                )
                user_facing_contract = " ".join(
                    (
                        scenario.title,
                        scenario.premise,
                        scenario.learner_role,
                        *scenario.setting_slots,
                        *scenario.text_types,
                        *(
                            value
                            for outcome in scenario.outcomes
                            for value in (
                                outcome.can_do,
                                outcome.mission_product,
                                outcome.permitted_support,
                            )
                        ),
                    )
                ).casefold()
                self.assertNotIn("fictional", user_facing_contract)
                self.assertNotIn("invented", user_facing_contract)

    def test_entertainment_event_owns_operations_instead_of_generic_planning(
        self,
    ) -> None:
        scenario = next(
            item
            for item in EXTENDED_SCENARIO_ARCHETYPES
            if item.id == "entertainment.plan_a_fictional_event"
        )
        contract = " ".join((scenario.title, scenario.premise, *scenario.setting_slots))
        self.assertIn("Coordinate", scenario.title)
        self.assertIn("responsibilities", contract)
        self.assertIn("access", contract)
        self.assertIn("contingency", contract)
        self.assertNotIn("event type options", contract)

    def test_reference_task_requires_no_outside_knowledge(self) -> None:
        scenario = next(
            item
            for item in EXTENDED_SCENARIO_ARCHETYPES
            if item.id == "study.use_a_reference_source"
        )
        self.assertIn("without requiring outside knowledge", scenario.premise)
        self.assertNotIn("without reading comprehension", scenario.premise)


if __name__ == "__main__":
    unittest.main()
