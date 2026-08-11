"""Turn acoustic evidence into a conservative, learner-facing outcome.

Continuous acoustic scores are useful feedback, but they are not calibrated as
pass/fail probabilities. A passing outcome therefore requires completeness,
transcript verification, and positive CTC support for the expected phones.
The scorer's conservative red status can still diagnose an error; orange alone
cannot.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping

ASSESSMENT_VERSION = 2
PRONUNCIATION_PASS_COMPLETENESS = 90
POSITIVE_PHONE_MIN_CONFIDENCE_PERCENT = 50.0
PRONUNCIATION_INCONCLUSIVE_RETRY_LIMIT = 3
_IPA_DECORATION = str.maketrans("", "", "/[]() ˈˌː.")


def _normalize_ipa(value: object) -> str:
    normalized = unicodedata.normalize("NFC", str(value or "")).translate(
        _IPA_DECORATION
    )
    return normalized.casefold()


def parse_focus_ipa(value: object) -> tuple[str, ...]:
    """Extract one or more IPA targets from activity metadata."""
    if isinstance(value, (list, tuple)):
        candidates: Iterable[object] = value
    elif isinstance(value, str):
        delimited = re.findall(r"/([^/]+)/", value)
        candidates = delimited or (value,)
    else:
        candidates = ()

    result: list[str] = []
    for candidate in candidates:
        normalized = _normalize_ipa(candidate)
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def phone_status_summary(
    analysis: object,
    *,
    status_key: str = "status",
) -> dict[str, int]:
    """Count phone states while naming which status namespace was summarized."""
    counts = {"correct": 0, "warning": 0, "incorrect": 0, "omitted": 0}
    if isinstance(analysis, list):
        for item in analysis:
            if not isinstance(item, Mapping):
                continue
            status = str(item.get(status_key) or "")
            if status in counts:
                counts[status] += 1
    return {
        "correct_phone_count": counts["correct"],
        "uncertain_phone_count": counts["warning"],
        "incorrect_phone_count": counts["incorrect"],
        "omitted_phone_count": counts["omitted"],
    }


def _base_arpabet(value: object) -> str:
    return re.sub(r"\d+$", "", str(value or "").strip().upper())


def _positive_phone_support(item: Mapping) -> bool:
    expected = _base_arpabet(item.get("arpabet"))
    likely = _base_arpabet(item.get("likely_arpabet"))
    try:
        confidence = float(item.get("likely_phone_probability"))
    except (TypeError, ValueError):
        return False
    return (
        bool(expected)
        and likely == expected
        and confidence >= POSITIVE_PHONE_MIN_CONFIDENCE_PERCENT
    )


def annotate_phone_verification(
    analysis: object,
    *,
    transcript_verified: bool,
    transcript_contradicted: bool,
) -> list[dict]:
    """Add learner-facing status without overwriting raw acoustic status."""
    if not isinstance(analysis, list):
        return []
    result: list[dict] = []
    for raw in analysis:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        acoustic_status = str(item.get("status") or "warning")
        item["acoustic_status"] = acoustic_status
        expected = _base_arpabet(item.get("arpabet"))
        likely = _base_arpabet(item.get("likely_arpabet"))
        try:
            confidence = float(item.get("likely_phone_probability"))
        except (TypeError, ValueError):
            confidence = 0.0
        confident_alternative = (
            bool(expected)
            and bool(likely)
            and likely != expected
            and confidence >= POSITIVE_PHONE_MIN_CONFIDENCE_PERCENT
        )

        if acoustic_status == "omitted":
            display_status = "omitted"
            reason = "omitted"
        elif acoustic_status == "incorrect":
            display_status = "incorrect"
            reason = "conservative_acoustic_error"
        elif transcript_verified and _positive_phone_support(item):
            display_status = "correct"
            reason = "transcript_and_phone_identity_agree"
        elif transcript_contradicted and confident_alternative:
            display_status = "incorrect"
            reason = "transcript_and_phone_identity_contradict"
        else:
            display_status = "warning"
            reason = "insufficient_agreement"
        item["display_status"] = display_status
        item["verification_reason"] = reason
        result.append(item)
    return result


def learner_attention_evidence(analysis: object) -> list[dict]:
    """Return only phones whose final display state still needs attention."""
    if not isinstance(analysis, list):
        return []
    result: list[dict] = []
    for raw in analysis:
        if not isinstance(raw, Mapping):
            continue
        display_status = str(raw.get("display_status") or raw.get("status") or "")
        if display_status not in {"incorrect", "warning"}:
            continue
        item = dict(raw)
        item["status"] = display_status
        item.setdefault("phoneme", item.get("char"))
        result.append(item)
    return result


def assess_pronunciation_evidence(
    *,
    analysis: object,
    completeness: object,
    transcript_verified: bool,
    focus_ipa: object = None,
) -> dict:
    """Return a versioned outcome without turning uncertainty into an error.

    When ``focus_ipa`` is supplied, only occurrences of the sound taught by the
    activity can block pronunciation mastery.  Completeness and transcript
    verification still protect against passing silence, omissions, or a
    different word.
    """
    try:
        completeness_value = int(round(float(completeness)))
    except (TypeError, ValueError):
        completeness_value = 0
    completeness_value = max(0, min(100, completeness_value))

    all_phones = (
        [item for item in analysis if isinstance(item, Mapping)]
        if isinstance(analysis, list)
        else []
    )
    focus = parse_focus_ipa(focus_ipa)
    focus_requested = focus_ipa is not None and bool(str(focus_ipa).strip())
    if focus:
        focused = [
            item for item in all_phones if _normalize_ipa(item.get("char")) in focus
        ]
    elif focus_requested:
        # An explicit but unsupported target (for example a bare stress mark)
        # must never broaden into an all-phone assessment.
        focused = []
    else:
        focused = all_phones
    omitted = [item for item in focused if item.get("status") == "omitted"]
    evaluated = [item for item in focused if item.get("status") != "omitted"]

    incorrect = sum(item.get("status") == "incorrect" for item in evaluated)
    uncertain = sum(item.get("status") == "warning" for item in evaluated)
    correct = sum(item.get("status") == "correct" for item in evaluated)
    supported = sum(_positive_phone_support(item) for item in evaluated)
    unsupported = len(evaluated) - supported

    if completeness_value < PRONUNCIATION_PASS_COMPLETENESS or omitted:
        outcome = "incomplete"
        passed: bool | None = False
    elif not evaluated:
        outcome = "inconclusive"
        passed = None
    elif incorrect:
        outcome = "needs_work"
        passed = False
    elif not transcript_verified:
        outcome = "inconclusive"
        passed = None
    elif unsupported:
        outcome = "inconclusive"
        passed = None
    else:
        outcome = "passed"
        passed = True

    return {
        "version": ASSESSMENT_VERSION,
        "outcome": outcome,
        "passed": passed,
        "focus_ipa": list(focus),
        "focus_requested": focus_requested,
        "evaluated_phone_count": len(evaluated),
        "supported_phone_count": supported,
        "unsupported_phone_count": unsupported,
        "acoustic_omitted_phone_count": len(omitted),
        "acoustic_correct_phone_count": correct,
        "acoustic_uncertain_phone_count": uncertain,
        "acoustic_incorrect_phone_count": incorrect,
        "completeness": completeness_value,
        "minimum_completeness": PRONUNCIATION_PASS_COMPLETENESS,
        "minimum_phone_support_confidence": POSITIVE_PHONE_MIN_CONFIDENCE_PERCENT,
        "transcript_verified": bool(transcript_verified),
    }
