"""Content sanitization, grading, and durable failure-envelope helpers."""

from __future__ import annotations

import copy
import json
import re
import unicodedata

from speakflow.features.pronunciation.domain import assess_pronunciation_evidence

from .learner_glosses import reviewed_learner_gloss
from .models import PlanLesson
from .schemas import ActivityAttemptInput
from .service_errors import (
    FAILURE_ENVELOPE_PREFIX,
    PlpInvalidAttemptError,
)


def _sanitize_content(
    content: dict | None,
    *,
    reviewed_template: dict | None = None,
) -> dict | None:
    if content is None:
        return None
    result = copy.deepcopy(content)
    if reviewed_template is not None:
        reviewed_fills = {
            tuple(
                sorted(
                    _normalize_text_answer(answer)
                    for answer in activity["data"]["accepted_answers"]
                )
            ): activity["data"]
            for activity in reviewed_template.get("activities", [])
            if activity.get("type") == "fill_blank"
        }
        for activity in result.get("activities", []):
            if activity.get("type") != "fill_blank":
                continue
            data = activity.get("data", {})
            answer_key = tuple(
                sorted(
                    _normalize_text_answer(answer)
                    for answer in data.get("accepted_answers", [])
                )
            )
            reviewed = reviewed_fills.get(answer_key)
            if reviewed is not None:
                data["prompt"] = reviewed["prompt"]
                data["explanation"] = reviewed["explanation"]
    for activity in result.get("activities", []):
        data = activity.get("data", {})
        if activity["type"] == "vocabulary_card":
            reviewed_gloss = reviewed_learner_gloss(
                str(data.get("word", "")),
                str(data.get("part_of_speech", "")) or None,
            )
            if reviewed_gloss is not None:
                # Repairs already-persisted prototype packs that predate the
                # learner-definition contract without mutating immutable
                # generated content or its original source provenance.
                data.setdefault("source_definition", data.get("definition"))
                data["definition"] = reviewed_gloss
                data["definition_origin"] = "reviewed_project_gloss"
            # Early prototype packs stored the curriculum-concept identity in
            # source_refs. A concept is content provenance, not a
            # CurriculumSource, so expose it in the card data and keep
            # source_refs closed over the public knowledge_sources registry.
            refs = activity.get("source_refs", [])
            concept_refs = [
                ref.removeprefix("concept:")
                for ref in refs
                if ref.startswith("concept:")
            ]
            if concept_refs and not data.get("concept_id"):
                data["concept_id"] = concept_refs[0]
            activity["source_refs"] = [
                ref for ref in refs if not ref.startswith("concept:")
            ]
        elif activity["type"] == "multiple_choice":
            data.pop("correct_option_id", None)
            data["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] == "fill_blank":
            data.pop("accepted_answers", None)
            data["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] in {"reading_comprehension", "listening_comprehension"}:
            if activity["type"] == "listening_comprehension":
                transcript = data.get("transcript")
                if isinstance(transcript, str):
                    data["transcript"] = _clean_listening_transcript(transcript)
            question = data.get("question", {})
            question.pop("correct_option_id", None)
            question["explanation"] = "Submit an answer to see the explanation."
        elif activity["type"] == "sentence_order":
            data.pop("correct_order", None)
            data["explanation"] = "Submit an answer to see the explanation."
    return result


_LISTENING_TRANSCRIPT_BOILERPLATE = {
    "please answer",
    "the group compares this detail before choosing an option",
    "each person checks the supplied information before agreeing",
    "they explain how the detail affects the practical next step",
    "finally the group records the decision for everyone to follow",
    "the complete plan now reflects the evidence in the message",
}


def _clean_listening_transcript(transcript: str) -> str:
    original_lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    had_legacy_boilerplate = any(
        _normalize_text_answer(line) in _LISTENING_TRANSCRIPT_BOILERPLATE
        for line in original_lines
    )
    lines = [
        line
        for line in original_lines
        if _normalize_text_answer(line) not in _LISTENING_TRANSCRIPT_BOILERPLATE
    ]
    if had_legacy_boilerplate and lines and lines[0].endswith("?"):
        lines.pop(0)
    lines = [
        re.sub(r"^speaker\s*:\s*", "", line, flags=re.IGNORECASE) for line in lines
    ]
    return "\n".join(lines) if lines else transcript


def _grade_activity(
    activity: dict,
    payload: ActivityAttemptInput,
    *,
    trusted_pronunciation: dict | None = None,
) -> tuple[bool | None, int, str, bool]:
    kind = activity["type"]
    data = activity["data"]
    if kind == "pronunciation_drill":
        if trusted_pronunciation is None:
            raise PlpInvalidAttemptError(
                "record and score an assigned target before completing this sound check"
            )
        target = str(trusted_pronunciation.get("target", ""))
        allowed = {
            _normalize_text_answer(_practice_item_text(item))
            for item in data.get("practice_items", [])
        }
        if _normalize_text_answer(target) not in allowed:
            raise PlpInvalidAttemptError(
                "the pronunciation target does not belong to this sound check"
            )
        accuracy = _bounded_pronunciation_metric(
            trusted_pronunciation.get("accuracy"), "accuracy"
        )
        completeness = _bounded_pronunciation_metric(
            trusted_pronunciation.get("completeness"), "completeness"
        )
        diagnostic_score = round((accuracy * 0.8) + (completeness * 0.2))
        focus_ipa = data.get("target_ipa") or data.get("ipa")
        assessment = assess_pronunciation_evidence(
            analysis=trusted_pronunciation.get("analysis"),
            completeness=completeness,
            transcript_verified=(
                trusted_pronunciation.get("transcript_verified") is True
            ),
            focus_ipa=focus_ipa,
        )
        passed = assessment["passed"]
        # PLP scores and skill evidence express verified mastery, not a second
        # copy of the advisory whole-utterance acoustic estimate.
        score = 100 if passed is True else 0
        display_focus = (
            " and ".join(f"/{phone}/" for phone in assessment["focus_ipa"])
            or "the assigned sound"
        )
        if assessment["outcome"] == "passed":
            explanation = (
                f"Target sound {display_focus} verified. The {accuracy}% acoustic "
                "quality estimate remains feedback, not a pass threshold."
            )
        elif assessment["outcome"] == "incomplete":
            explanation = (
                "Try again and say the complete target exactly as shown; "
                f"completeness was {completeness}%."
            )
        elif assessment["outcome"] == "needs_work":
            explanation = (
                f"Try again: a confirmed issue was detected on {display_focus}. "
                "Orange sounds are uncertain and do not cause this result."
            )
        elif assessment["unsupported_phone_count"]:
            explanation = (
                f"The recognizers did not agree strongly enough on {display_focus}. "
                "Try once more; this is inconclusive, not a confirmed mistake."
            )
        else:
            explanation = (
                "The target could not be verified reliably from this recording. "
                "Try once more; this is not marked as a pronunciation mistake."
            )
        evidence_allowed = assessment["outcome"] in {"passed", "needs_work"}
        trusted_pronunciation["diagnostic_score"] = diagnostic_score
        return passed, score, explanation, evidence_allowed
    if kind == "multiple_choice":
        valid_ids = {item["id"] for item in data["options"]}
        if payload.selected_option_id not in valid_ids:
            raise PlpInvalidAttemptError("choose one of the available options")
        correct = payload.selected_option_id == data["correct_option_id"]
        return correct, 100 if correct else 0, data["explanation"], True
    if kind == "fill_blank":
        answer = _normalize_text_answer(payload.text_answer or "")
        if not answer:
            raise PlpInvalidAttemptError("enter an answer before submitting")
        accepted = {_normalize_text_answer(item) for item in data["accepted_answers"]}
        correct = answer in accepted
        return correct, 100 if correct else 0, data["explanation"], True
    if kind in {"reading_comprehension", "listening_comprehension"}:
        question = data["question"]
        valid_ids = {item["id"] for item in question["options"]}
        if payload.selected_option_id not in valid_ids:
            raise PlpInvalidAttemptError("choose one of the available options")
        correct = payload.selected_option_id == question["correct_option_id"]
        return correct, 100 if correct else 0, question["explanation"], True
    if kind == "sentence_order":
        submitted = payload.ordered_token_ids or []
        valid_ids = {item["id"] for item in data["tokens"]}
        if len(submitted) != len(valid_ids) or set(submitted) != valid_ids:
            raise PlpInvalidAttemptError("use every sentence chunk exactly once")
        correct = payload.ordered_token_ids == data["correct_order"]
        return correct, 100 if correct else 0, data["explanation"], True
    if kind == "guided_speaking":
        transcript = (payload.transcript or "").strip().casefold()
        if not transcript:
            raise PlpInvalidAttemptError(
                "record a spoken response before completing this activity"
            )
        duration = payload.duration_seconds or 0
        if duration < data["minimum_seconds"]:
            raise PlpInvalidAttemptError(
                f"speak for at least {data['minimum_seconds']} seconds"
            )
        covered = any(
            item.casefold() in transcript for item in data["target_expressions"]
        )
        score = 100 if covered else 50
        return (
            None,
            score,
            "Participation is recorded; this is not an acoustic pronunciation grade.",
            False,
        )
    return None, 100, "Activity completed.", False


def _normalize_text_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("’", "'")
    normalized = " ".join(normalized.split())
    return normalized.strip(" \t\r\n.,!?;:")


def _correct_response(activity: dict) -> dict | None:
    kind = activity["type"]
    data = activity["data"]
    if kind == "multiple_choice":
        return {"selected_option_id": data["correct_option_id"]}
    if kind in {"reading_comprehension", "listening_comprehension"}:
        return {"selected_option_id": data["question"]["correct_option_id"]}
    if kind == "fill_blank":
        return {"text_answer": data["accepted_answers"][0]}
    if kind == "sentence_order":
        return {"ordered_token_ids": data["correct_order"]}
    return None


def _required_activities(lesson: PlanLesson) -> list[str]:
    return [
        item["id"]
        for item in (lesson.content or {}).get("content", {}).get("activities", [])
        if item.get("required", True)
    ]


def _scored_activities(lesson: PlanLesson) -> list[dict]:
    scored_types = {
        "pronunciation_drill",
        "multiple_choice",
        "fill_blank",
        "reading_comprehension",
        "listening_comprehension",
        "sentence_order",
    }
    return [
        item
        for item in (lesson.content or {}).get("content", {}).get("activities", [])
        if item.get("required", True) and item.get("type") in scored_types
    ]


def _practice_item_text(item: str | dict) -> str:
    return item if isinstance(item, str) else str(item.get("text", ""))


def _bounded_pronunciation_metric(value: object, name: str) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PlpInvalidAttemptError(f"pronunciation {name} is missing")
    rounded = round(float(value))
    if rounded < 0 or rounded > 100:
        raise PlpInvalidAttemptError(f"pronunciation {name} is invalid")
    return rounded


def _classify_failure(message: str) -> str:
    normalized = message.casefold()
    if "rate-limit" in normalized or "rate limit" in normalized:
        return "rate_limited"
    if "groq" in normalized or "scenario writer" in normalized:
        return "provider_validation"
    if "retriev" in normalized or "curriculum" in normalized:
        return "retrieval"
    if "validation" in normalized or "compiler" in normalized:
        return "content_validation"
    return "internal"


def _encode_job_failure(
    message: str,
    *,
    failure_kind: str,
    retry_after_seconds: int | None,
) -> str:
    payload = {
        "message": message[:1800],
        "failure_kind": failure_kind,
        "retry_after_seconds": retry_after_seconds,
    }
    return FAILURE_ENVELOPE_PREFIX + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decode_job_failure(value: str | None) -> dict | None:
    if not value:
        return None
    if value.startswith(FAILURE_ENVELOPE_PREFIX):
        try:
            payload = json.loads(value[len(FAILURE_ENVELOPE_PREFIX) :])
            if isinstance(payload, dict) and isinstance(payload.get("message"), str):
                return {
                    "message": payload["message"],
                    "failure_kind": str(
                        payload.get("failure_kind")
                        or _classify_failure(payload["message"])
                    ),
                    "retry_after_seconds": payload.get("retry_after_seconds"),
                }
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {
        "message": value,
        "failure_kind": _classify_failure(value),
        "retry_after_seconds": None,
    }
