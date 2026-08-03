from tests.plp_test_support import *


class PlannerTests(unittest.TestCase):
    def test_seed_skill_graph_is_acyclic(self):
        _, skills, _ = seed_records()
        _validate_skill_graph(skills)

    def test_all_supported_levels_make_four_ordered_weeks(self):
        skills = planning_skills()
        for level in ("A1", "A2", "B1", "B2"):
            with self.subTest(level=level):
                outline = build_outline(profile(level=level), skills)
                self.assertEqual(len(outline["weeks"]), 4)
                flattened = [
                    lesson
                    for week in outline["weeks"]
                    for unit in week["units"]
                    for lesson in unit["lessons"]
                ]
                seen = set()
                for lesson in flattened:
                    self.assertTrue(set(lesson["required_lesson_keys"]).issubset(seen))
                    seen.add(lesson["lesson_key"])
                self.assertEqual(len(seen), len(flattened))

    def test_schedule_is_fixed_and_each_week_uses_the_mission_role_dag(self):
        skills = planning_skills()
        outline = build_outline(profile(), skills)
        self.assertEqual(outline["architecture"], "weekly_mission")
        self.assertEqual(outline["schedule"]["days_per_week"], 5)
        self.assertEqual(outline["schedule"]["minutes_per_day"], 20)
        previous_checkpoint = None
        for week in outline["weeks"]:
            lessons = week["units"][0]["lessons"]
            self.assertEqual(len(lessons), 5)
            self.assertEqual(
                [item["specification"]["lesson_role"] for item in lessons],
                [
                    "input_noticing",
                    "language_tools",
                    "guided_interaction",
                    "independent_transfer",
                    "checkpoint",
                ],
            )
            expected_roots = [previous_checkpoint] if previous_checkpoint else []
            self.assertEqual(lessons[0]["required_lesson_keys"], expected_roots)
            self.assertEqual(lessons[1]["required_lesson_keys"], expected_roots)
            self.assertEqual(
                lessons[2]["required_lesson_keys"],
                [lessons[0]["lesson_key"], lessons[1]["lesson_key"]],
            )
            self.assertEqual(
                lessons[3]["required_lesson_keys"],
                [lessons[2]["lesson_key"]],
            )
            self.assertEqual(lessons[-1]["type"], "assessment")
            self.assertEqual(
                lessons[-1]["lesson_key"],
                f"w{week['sequence']:02d}_l05_assessment",
            )
            self.assertEqual(
                lessons[-1]["required_lesson_keys"],
                [item["lesson_key"] for item in lessons[:4]],
            )
            self.assertEqual(
                lessons[-1]["specification"]["completion_policy"]["minimum_score"],
                75,
            )
            previous_checkpoint = lessons[-1]["lesson_key"]

    def test_weekly_missions_rotate_profile_dimensions_and_do_not_repeat(self):
        first = build_outline(profile(), planning_skills())
        second = build_outline(profile(), planning_skills())
        first_missions = [week["mission"] for week in first["weeks"]]
        self.assertEqual(first_missions, [week["mission"] for week in second["weeks"]])
        self.assertEqual(
            [item["goal"]["id"] for item in first_missions],
            [
                "confident_conversation",
                "workplace_communication",
                "confident_conversation",
                "workplace_communication",
            ],
        )
        self.assertEqual(
            [item["interest"]["id"] for item in first_missions],
            ["technology", "travel", "technology", "travel"],
        )
        scenario_ids = [item["scenario"]["id"] for item in first_missions]
        self.assertEqual(len(scenario_ids), len(set(scenario_ids)))

        for week, mission in zip(first["weeks"], first_missions, strict=True):
            for lesson in week["units"][0]["lessons"]:
                specification = lesson["specification"]
                self.assertEqual(specification["architecture"], "weekly_mission")
                self.assertEqual(specification["can_do"], mission["can_do"])
                self.assertEqual(specification["goal"], mission["goal"])
                self.assertEqual(specification["interest"], mission["interest"])
                self.assertEqual(specification["scenario"], mission["scenario"])
                self.assertEqual(specification["mission"], mission["mission"])
                self.assertEqual(specification["cefr_realization"]["level"], "B1")

    def test_cefr_changes_the_reviewed_mission_realization(self):
        skills = planning_skills()
        a1 = build_outline(profile(level="A1"), skills)["weeks"][0]["mission"]
        b2 = build_outline(profile(level="B2"), skills)["weeks"][0]["mission"]
        self.assertEqual(a1["scenario"]["id"], b2["scenario"]["id"])
        self.assertNotEqual(a1["can_do"], b2["can_do"])
        self.assertLess(
            a1["cefr_realization"]["maximum_sentence_words"],
            b2["cefr_realization"]["maximum_sentence_words"],
        )
        self.assertLess(
            a1["cefr_realization"]["input_word_range"][1],
            b2["cefr_realization"]["input_word_range"][1],
        )

    def test_same_domain_micro_skills_are_kept_as_distinct_records(self):
        same_domain_skills = [
            PlanningSkill(
                id=f"interaction.b1.skill_{index}",
                domain="speaking",
                level="B1",
                title=f"Interaction skill {index}",
                description=f"Use interaction move {index}.",
                outcomes=[f"Can use interaction move {index}."],
            )
            for index in range(1, 5)
        ]
        outline = build_outline(profile(), same_domain_skills)
        first_week = outline["weeks"][0]["units"][0]["lessons"]
        self.assertEqual(
            {lesson["skill_ids"][0] for lesson in first_week[:4]},
            {skill.id for skill in same_domain_skills},
        )
        self.assertEqual({lesson["type"] for lesson in first_week[:4]}, {"speaking"})

    def test_later_checkpoints_include_one_distinct_spaced_review_skill(self):
        outline = build_outline(profile(), planning_skills())
        for week in outline["weeks"][1:]:
            lessons = week["units"][0]["lessons"]
            current = {skill for lesson in lessons[:4] for skill in lesson["skill_ids"]}
            checkpoint = lessons[-1]
            review = checkpoint["specification"]["review_skill_ids"]
            self.assertEqual(len(review), 1)
            self.assertNotIn(review[0], current)
            self.assertEqual(len(checkpoint["skill_ids"]), 5)

    def test_adaptation_priority_reinforces_without_removing_core(self):
        skills = planning_skills()
        baseline = build_outline(profile(), skills)
        adapted = build_outline(
            profile(),
            skills,
            priority_skill_ids=["grammar.b1.core"],
        )

        def teaching_skill_ids(outline):
            return [
                lesson["skill_ids"][0]
                for week in outline["weeks"]
                for unit in week["units"]
                for lesson in unit["lessons"]
                if lesson["type"] != "assessment"
            ]

        baseline_ids = teaching_skill_ids(baseline)
        adapted_ids = teaching_skill_ids(adapted)
        self.assertGreater(
            adapted_ids.count("grammar.b1.core"),
            baseline_ids.count("grammar.b1.core"),
        )
        self.assertTrue(set(baseline_ids).issubset(set(adapted_ids)))
