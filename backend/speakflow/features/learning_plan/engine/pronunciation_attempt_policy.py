"""Persistence and retry policy for trusted pronunciation attempts."""

from __future__ import annotations

from speakflow.features.pronunciation.domain import (
    PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT,
)

from .models import ActivityAttempt
from .service_grading import _normalize_text_answer


def should_accept_inconclusive_progress(
    attempts: list[ActivityAttempt],
    target: str,
) -> bool:
    normalized_target = _normalize_text_answer(target)
    prior_inconclusive = sum(
        attempt.correct is None
        and isinstance((attempt.response or {}).get("pronunciation"), dict)
        and _normalize_text_answer(
            (attempt.response or {})["pronunciation"].get("target", "")
        )
        == normalized_target
        for attempt in attempts
    )
    return prior_inconclusive + 1 >= PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT


def should_record_pronunciation_evidence(
    attempts: list[ActivityAttempt],
    *,
    target: str,
    evidence_allowed: bool,
    attempt_kind: str,
) -> bool:
    """Record the first conclusive initial result for each assigned target."""
    if not evidence_allowed or attempt_kind != "initial":
        return False
    normalized_target = _normalize_text_answer(target)
    return not any(
        bool((attempt.response or {}).get("_mastery_evidence_recorded"))
        and isinstance((attempt.response or {}).get("pronunciation"), dict)
        and _normalize_text_answer(
            (attempt.response or {})["pronunciation"].get("target", "")
        )
        == normalized_target
        for attempt in attempts
    )


def pronunciation_evidence_weight(
    *,
    base_weight: float,
    assigned_target_count: int,
) -> float:
    """Share one activity's evidence weight evenly across its targets."""
    return base_weight / max(1, assigned_target_count)


def pronunciation_attempt_response(
    trusted: dict,
    *,
    completion_accepted: bool,
) -> dict:
    phone_evidence = [
        {
            key: item.get(key)
            for key in (
                "phone_index",
                "char",
                "arpabet",
                "status",
                "acoustic_status",
                "display_status",
                "verification_reason",
                "score",
                "likely_arpabet",
                "likely_ipa",
                "likely_phone_probability",
                "closest_arpabet",
                "closest_ipa",
                "deletion_probability",
                "replacement_verified",
                "error_type",
            )
        }
        for item in trusted.get("analysis", [])
        if isinstance(item, dict)
    ]
    return {
        "target": trusted["target"],
        "accuracy": trusted["accuracy"],
        "completeness": trusted["completeness"],
        "diagnostic_score": trusted.get("diagnostic_score"),
        "transcript_verified": bool(trusted.get("transcript_verified")),
        "completion_accepted": completion_accepted,
        "phone_evidence": phone_evidence,
    }


def pronunciation_progress_explanation(
    *,
    activity_completed: bool,
    progress_accepted: bool,
    completed_targets: int,
    required_targets: int,
) -> str:
    if activity_completed:
        if progress_accepted:
            return (
                f"All {required_targets} assigned pronunciation targets completed. "
                "This target remained inconclusive, so it was not recorded as "
                "pronunciation mastery."
            )
        return f"All {required_targets} assigned pronunciation targets passed."
    prefix = (
        "This target remained inconclusive after "
        f"{PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT} attempts, so you may continue "
        "without a mastery record. "
        if progress_accepted
        else "Target passed. "
    )
    return (
        prefix + f"{completed_targets} of {required_targets} assigned targets complete."
    )
