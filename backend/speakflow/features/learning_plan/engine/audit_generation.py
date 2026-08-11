from __future__ import annotations

import argparse
import json
import time

from sqlalchemy import select

from .database import get_engine, session_scope
from .generator import LessonGenerator
from .models import Skill
from .retrieval import CurriculumRetriever


def audit_generation(*, domain: str, level: str) -> dict:
    """Generate and validate one lesson without persisting learner state."""
    skill_id = f"{domain}.{level.casefold()}.core"
    retriever = CurriculumRetriever()
    generator = LessonGenerator()
    started = time.monotonic()
    try:
        with session_scope() as session:
            skill = session.scalar(select(Skill).where(Skill.id == skill_id))
            if skill is None:
                raise ValueError(f"reviewed skill {skill_id} was not found")
            chunks = retriever.retrieve(
                session,
                query=f"{skill.title} {skill.description}",
                cefr_level=level,
                skill_ids=[skill_id],
            )
        generated, source_refs = generator.generate(
            specification={
                "domain": domain,
                "title": skill.title,
                "description": skill.description,
                "cefr_level": level,
                "objectives": list(skill.outcomes),
                "skill_ids": [skill_id],
                "topics": ["Technology"],
                "contexts": ["Real-life conversations"],
            },
            lesson_key=f"audit_{level.casefold()}_{domain}",
            chunks=chunks,
            support_language="Arabic",
        )
        return {
            "provider": generator.provider,
            "model": generator.model_name,
            "domain": domain,
            "level": level,
            "duration_seconds": round(time.monotonic() - started, 1),
            "source_refs": source_refs,
            "title": generated["title"],
            "activities": [
                _activity_summary(item) for item in generated["content"]["activities"]
            ],
        }
    finally:
        retriever.close()
        generator.close()


def _activity_summary(activity: dict) -> dict:
    data = activity["data"]
    question = data.get("question", data)
    result = {"type": activity["type"]}
    if "prompt" in question:
        result["prompt"] = question["prompt"]
    if "options" in question:
        result["options"] = [item["text"] for item in question["options"]]
        correct_id = question["correct_option_id"]
        result["correct_answer"] = next(
            item["text"] for item in question["options"] if item["id"] == correct_id
        )
    if "accepted_answers" in data:
        result["accepted_answers"] = data["accepted_answers"]
    if "ipa" in data:
        result["ipa"] = data["ipa"]
        result["practice_items"] = data.get("practice_items", [])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one non-persisting PLP lesson for quality review."
    )
    parser.add_argument(
        "--domain",
        required=True,
        choices=(
            "vocabulary",
            "grammar",
            "reading",
            "listening",
            "speaking",
            "pronunciation",
            "discourse",
        ),
    )
    parser.add_argument("--level", default="B1", choices=("A1", "A2", "B1", "B2"))
    args = parser.parse_args()
    try:
        print(
            json.dumps(audit_generation(domain=args.domain, level=args.level), indent=2)
        )
    finally:
        get_engine().dispose()


if __name__ == "__main__":
    main()
