from tests.learning_plan.support.plp_service_test_support import (
    GenerationView,
    LearningPlanEngine,
    Mock,
    SimpleNamespace,
    _scalar_result,
    unittest,
    uuid,
)


class DocumentGroundingTests(unittest.TestCase):
    def test_document_prefers_explicit_provenance_and_exposes_metadata(self):
        plan_id = uuid.uuid4()
        revision_id = uuid.uuid4()
        lesson_rows = []
        weeks = []
        for week_number in range(1, 5):
            lesson_key = f"w{week_number:02d}_l01_input_noticing"
            specification = {
                "title": f"Week {week_number} input",
                "description": "Notice useful language in context.",
                "cefr_level": "B1",
                "completion_policy": {"mode": "required_activities"},
                "objectives": ["Notice the key language"],
                "personalization_reason": "Matches the selected mission.",
                "lesson_role": "input_noticing",
                "can_do": "Can identify the key information in a short exchange.",
            }
            ready = week_number == 1
            generated = None
            source_refs = []
            if ready:
                source_refs = ["source-reviewed"]
                generated = {
                    "provenance": {
                        "origin": "retrieval_generated",
                        "review_status": "generated_validated",
                    },
                    "title": "Personalized input",
                    "description": "A grounded scenario realization.",
                    "content_instance_id": "instance-week-1-input",
                    "content": {
                        "intro": "Read the grounded scenario.",
                        "activities": [
                            {
                                "id": "week1_activity_1",
                                "type": "concept",
                                "required": True,
                                "source_refs": source_refs,
                                "skill_ids": ["reading.b1.core"],
                                "data": {},
                            },
                            {
                                "id": "week1_activity_2",
                                "type": "concept",
                                "required": True,
                                "source_refs": source_refs,
                                "skill_ids": ["reading.b1.core"],
                                "data": {},
                            },
                        ],
                    },
                }
            lesson_rows.append(
                SimpleNamespace(
                    id=uuid.uuid4(),
                    lesson_key=lesson_key,
                    lesson_sequence=1,
                    week_sequence=week_number,
                    lesson_type="reading",
                    estimated_minutes=20,
                    xp=20,
                    skill_ids=["reading.b1.core"],
                    required_lesson_keys=[],
                    specification=specification,
                    content_status="ready" if ready else "pending",
                    content=generated,
                    source_refs=source_refs,
                )
            )
            weeks.append(
                {
                    "id": f"week-{week_number}",
                    "sequence": week_number,
                    "title": f"Week {week_number}",
                    "description": "Mission week.",
                    "objectives": ["Complete the mission"],
                    "mission": {"id": f"mission-{week_number}"},
                    "units": [
                        {
                            "id": f"unit-{week_number}",
                            "sequence": 1,
                            "title": "Mission",
                            "description": "Prepare and apply.",
                            "objectives": ["Apply the weekly language"],
                            "lessons": [
                                {
                                    "lesson_key": lesson_key,
                                    "specification": specification,
                                }
                            ],
                        }
                    ],
                }
            )

        outline = {
            "architecture": "weekly_mission",
            "title": "Personal learning path",
            "description": "Four grounded weekly missions.",
            "level": {"current": "B1", "target": "B2"},
            "schedule": {
                "duration_weeks": 4,
                "days_per_week": 5,
                "minutes_per_day": 20,
            },
            "focus_areas": ["reading"],
            "weeks": weeks,
        }
        snapshot = {
            "native_language": "Arabic",
            "support_language": "Arabic",
            "learning_goals": ["Speak confidently"],
            "interests": ["Technology"],
            "preferred_contexts": [],
            "accent_preference": "no_preference",
            "pronunciation_priorities": [],
        }
        plan = SimpleNamespace(id=plan_id)
        revision = SimpleNamespace(
            id=revision_id,
            revision=1,
            outline=outline,
            learner_snapshot=snapshot,
        )
        job = SimpleNamespace(id=uuid.uuid4())
        source = SimpleNamespace(
            id="source-reviewed",
            title="Reviewed curriculum",
            locator="project://curriculum",
            license="project-authored",
            version="1",
        )
        session = Mock()
        session.scalars.side_effect = [
            _scalar_result(lesson_rows).scalars.return_value,
            _scalar_result([]).scalars.return_value,
            _scalar_result([]).scalars.return_value,
            _scalar_result([source]).scalars.return_value,
            _scalar_result([]).scalars.return_value,
        ]
        service = object.__new__(LearningPlanEngine)
        service._generation_view = Mock(
            return_value=GenerationView(
                job_id=job.id,
                status="idle",
                ready_weeks=0,
                completed_lessons=1,
                total_lessons=4,
                failed_lesson_ids=[],
            )
        )

        document = service._build_document(session, plan, revision, job)
        lesson = document.plan.weeks[0].units[0].lessons[0]

        self.assertEqual(lesson.grounding.origin, "retrieval_generated")
        self.assertEqual(lesson.grounding.review_status, "generated_validated")
        self.assertEqual(lesson.grounding.source_refs, ["source-reviewed"])
        self.assertEqual(lesson.lesson_role, "input_noticing")
        self.assertEqual(
            lesson.can_do_statement,
            "Can identify the key information in a short exchange.",
        )
        self.assertEqual(lesson.content_instance_id, "instance-week-1-input")


if __name__ == "__main__":
    unittest.main()
