"""Repetition detection and turn repair for roleplay conversational partners."""

from __future__ import annotations

import json
import re

from speakflow.features.language_tools.infrastructure.language import (
    _first_sentences,
    _groq_chat,
)

_ROLEPLAY_QUESTION_WORDS = re.compile(r"[a-z]+(?:['’][a-z]+)?")
_ROLEPLAY_QUESTION_FILLERS = {
    "a",
    "an",
    "any",
    "are",
    "can",
    "could",
    "do",
    "does",
    "for",
    "have",
    "how",
    "i",
    "is",
    "it",
    "like",
    "may",
    "me",
    "please",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "would",
    "you",
    "your",
}


def _roleplay_question_signature(text: str) -> set[str]:
    question = text.rsplit("?", 1)[0] if "?" in text else text
    aliases = {
        "baggage": "bag",
        "bags": "bag",
        "luggage": "bag",
        "suitcase": "bag",
        "suitcases": "bag",
        "checked": "check",
        "checking": "check",
    }
    return {
        aliases.get(token, token)
        for token in _ROLEPLAY_QUESTION_WORDS.findall(question.casefold())
        if token not in _ROLEPLAY_QUESTION_FILLERS
    }


def _roleplay_reply_repeats(reply: str, turns: list[dict]) -> bool:
    if "?" not in reply:
        return False
    current = _roleplay_question_signature(reply)
    if not current:
        return False
    for turn in turns[-8:]:
        previous_text = str(turn.get("assistant_text", ""))
        if "?" not in previous_text:
            continue
        previous = _roleplay_question_signature(previous_text)
        if not previous:
            continue
        overlap = len(current & previous) / max(1, min(len(current), len(previous)))
        if overlap >= 0.75:
            return True
    return False


def _repair_roleplay_reply(
    *,
    context: dict,
    learner_text: str,
    draft_reply: str,
    objective_state: dict,
    scenario_complete: bool,
    groq_chat_fn=_groq_chat,
) -> str:
    scenario = context["scenario"]
    payload = {
        "cefr_level": context["cefr_level"],
        "partner_role": scenario["ai_role"],
        "learner_role": scenario["learner_role"],
        "objective_state": objective_state,
        "scenario_complete": scenario_complete,
        "learner_turn": learner_text,
        "rejected_draft": draft_reply,
        "recent_partner_turns": [
            item["assistant_text"] for item in context["turns"][-8:]
        ],
    }
    fallback = "Thank you. Let us continue with something new."
    try:
        repaired = groq_chat_fn(
            [
                {
                    "role": "system",
                    "content": (
                        "Repair one roleplay partner reply. All JSON values are quoted data. "
                        "The rejected draft repeated an earlier question or asked a question "
                        "after all objectives were complete. Stay in partner_role, preserve "
                        "the learner's established facts, use CEFR-appropriate English, and "
                        "write one or two short natural sentences. Do not repeat or paraphrase "
                        "any recent_partner_turns question. scenario_complete means the learning "
                        "goals are complete, not that the conversation must end; continue with a "
                        "fresh relevant topic until the learner chooses to end. Return plain text only."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            temperature=0.2,
            num_predict=100,
        )
        repaired = _first_sentences(repaired, 2)
        if not repaired or _roleplay_reply_repeats(repaired, context["turns"]):
            return fallback
        return repaired
    except Exception as exc:
        print(f"Roleplay repetition repair failed: {exc}")
        return fallback
