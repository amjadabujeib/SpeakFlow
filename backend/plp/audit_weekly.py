"""Generate one non-persisting mission week for provider/validator auditing."""

from __future__ import annotations

import argparse
import hashlib
import json

from .generator import LessonGenerator
from .database import session_scope
from .planner import PlanningSkill, build_outline
from .retrieval import CurriculumRetriever, RetrievedChunk
from .schemas import LearnerProfileInput
from .seed import seed_records
from .weekly_mission import GenerationError, WeeklyMissionGenerator


def audit_weekly_generation(
    *,
    level: str = "B1",
    goal: str = "Communicate at work",
    interest: str = "Technology",
    native_language: str = "Arabic",
    variation_seed: str = "audit-weekly",
    generation_attempt: int = 1,
) -> dict:
    source, skill_rows, chunk_rows = seed_records()
    skills = [
        PlanningSkill(
            id=item["id"],
            domain=item["domain"],
            level=item["cefr_level"],
            title=item["title"],
            description=item["description"],
            outcomes=item["outcomes"],
        )
        for item in skill_rows
    ]
    profile = LearnerProfileInput(
        cefr_level=level,
        native_language=native_language,
        learning_goals=[goal],
        interests=[interest],
    )
    outline = build_outline(profile, skills, variation_seed=variation_seed)
    week = outline["weeks"][0]
    shells = [
        {
            "lesson_key": lesson["lesson_key"],
            "sequence": lesson["sequence"],
            "week_sequence": week["sequence"],
            "type": lesson["type"],
            "skill_ids": lesson["skill_ids"],
            "specification": lesson["specification"],
        }
        for lesson in week["units"][0]["lessons"]
    ]
    selected_skills = {
        skill_id for lesson in shells for skill_id in lesson["skill_ids"]
    }
    chunks = [
        RetrievedChunk(
            id=item["id"],
            source_id=item["source_id"],
            content=item["content"],
            metadata=item["metadata"],
            score=1.0,
            content_hash=hashlib.sha256(item["content"].encode()).hexdigest(),
        )
        for item in chunk_rows
        if selected_skills.intersection(item["metadata"]["skill_ids"])
    ]
    first_specification = shells[0]["specification"]
    scenario = first_specification["scenario"]
    palette_query = " ".join(
        [
            f"{level} English vocabulary for {interest}.",
            f"Scenario: {scenario['title']}.",
            f"Learner task: {first_specification['can_do']}.",
            "Setting: " + ", ".join(scenario["setting_slots"]) + ".",
            "Lesson domains: "
            + ", ".join(dict.fromkeys(item["type"] for item in shells))
            + ".",
        ]
    )
    retriever = CurriculumRetriever()
    try:
        with session_scope() as session:
            lexical_palette = retriever.retrieve_lexical_palette(
                session,
                cefr_level=level,
                interests=[interest],
                seed=f"{variation_seed}:1:{generation_attempt}",
                limit=2,
                query_text=palette_query,
            )
    finally:
        retriever.close()
    writer = LessonGenerator()
    try:
        generated = WeeklyMissionGenerator(writer).generate(
            lessons=shells,
            chunks=chunks,
            lexical_palette=lexical_palette,
            support_language=profile.support_language,
            generation_attempt=generation_attempt,
        )
    finally:
        writer.close()
    first_payload = generated[shells[0]["lesson_key"]][0]
    mission_payload = week["mission"]
    mission_details = mission_payload.get("mission", mission_payload)
    return {
        "status": "passed",
        "provider": first_payload["provenance"]["provider"],
        "model": first_payload["provenance"]["model"],
        "source_version": source["version"],
        "mission": mission_details["title"],
        "weekly_pack": first_payload["weekly_pack"],
        "writer_request": first_payload["provenance"]["writer_request"],
        "candidate_concept_count": len(lexical_palette),
        "candidate_concept_sources": sorted(
            {item.source_id for item in lexical_palette}
        ),
        "prototype_targets": [
            {
                "concept_id": item["concept_id"],
                "term": item["term"],
            }
            for item in first_payload["provenance"]["writer_request"].get(
                "prototype_targets", []
            )
        ],
        "learner_vocabulary_cards": [
            {
                "lesson_key": key,
                "term": activity["data"]["word"],
                "definition": activity["data"]["definition"],
                "example": activity["data"]["examples"][0],
            }
            for key, (payload, _) in generated.items()
            for activity in payload["content"]["activities"]
            if activity["type"] == "vocabulary_card"
        ],
        "lessons": [
            {
                "lesson_key": key,
                "title": payload["title"],
                "activity_count": len(payload["content"]["activities"]),
                "content_instance_id": payload["content_instance_id"],
                "scored_checks": [
                    summary
                    for activity in payload["content"]["activities"]
                    if (summary := _scored_check_summary(activity)) is not None
                ],
            }
            for key, (payload, _) in generated.items()
        ],
    }


def _scored_check_summary(activity: dict) -> dict | None:
    data = activity["data"]
    if activity["type"] in {"reading_comprehension", "listening_comprehension"}:
        question = data["question"]
        context = data.get("passage") or data.get("transcript") or ""
    elif activity["type"] == "multiple_choice":
        question = data
        context = ""
    elif activity["type"] == "fill_blank":
        return {
            "type": activity["type"],
            "prompt": data["prompt"],
            "answer": data["accepted_answers"][0],
        }
    elif activity["type"] == "sentence_order":
        by_id = {item["id"]: item["text"] for item in data["tokens"]}
        return {
            "type": activity["type"],
            "prompt": data["prompt"],
            "answer": " ".join(by_id[item] for item in data["correct_order"]),
        }
    else:
        return None
    correct = next(
        option["text"]
        for option in question["options"]
        if option["id"] == question["correct_option_id"]
    )
    return {
        "type": activity["type"],
        "context": context,
        "prompt": question["prompt"],
        "answer": correct,
        "distractors": [
            option["text"]
            for option in question["options"]
            if option["id"] != question["correct_option_id"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", default="B1")
    parser.add_argument("--goal", default="Communicate at work")
    parser.add_argument("--interest", default="Technology")
    parser.add_argument("--native-language", default="Arabic")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    try:
        result = audit_weekly_generation(
            level=args.level,
            goal=args.goal,
            interest=args.interest,
            native_language=args.native_language,
            generation_attempt=args.attempt,
        )
    except GenerationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
