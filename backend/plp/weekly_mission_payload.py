"""Provenance and provider metadata for compiled weekly lesson payloads."""

from __future__ import annotations

import copy
import hashlib
import json

from .retrieval import RetrievedChunk
from .standard import PLP_FORMAT_REVISION, PLP_PIPELINE
from .weekly_mission_models import LessonSurface


def _generated_payload(
    *,
    lesson: dict,
    surface: LessonSurface,
    content: dict,
    chunks: list[RetrievedChunk],
    provider: str,
    model: str,
    response_hash: str,
    weekly_pack_id: str,
    scenario_title: str,
    setting: str,
    roles: list[str],
    generation_metadata: dict | None,
    preserved_context_ids: list[str],
    preserved_distractor_ids: list[str],
    inserted_answer_evidence_ids: list[str],
    extended_input_context_ids: list[str],
    surface_ids_rebound: bool,
) -> dict:
    unique_chunks = {chunk.id: chunk for chunk in chunks}
    chunk_refs = [
        {
            "chunk_id": chunk.id,
            "content_hash": chunk.content_hash,
            "source_id": chunk.source_id,
        }
        for chunk in sorted(unique_chunks.values(), key=lambda value: value.id)
    ]
    content_instance_id = hashlib.sha256(
        json.dumps(
            {
                "lesson_key": lesson["lesson_key"],
                "response_hash": response_hash,
                "content": content,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:32]
    return {
        "title": surface.title,
        "description": surface.description,
        "content": content,
        "content_instance_id": content_instance_id,
        "weekly_pack": {
            "id": weekly_pack_id,
            "scenario_title": scenario_title,
            "setting": setting,
            "roles": roles,
        },
        "provenance": {
            "origin": "retrieval_generated",
            "review_status": "generated_validated",
            "provider": provider,
            "model": model,
            "pipeline": PLP_PIPELINE,
            "format_revision": PLP_FORMAT_REVISION,
            "response_hash": response_hash,
            "writer_request": generation_metadata or {},
            "reviewed_anchor_preserved": preserved_context_ids,
            "reviewed_distractors_preserved": preserved_distractor_ids,
            "answer_evidence_inserted": inserted_answer_evidence_ids,
            "input_context_extended": extended_input_context_ids,
            "surface_ids_rebound": surface_ids_rebound,
            "source_chunks": chunk_refs,
            "validation": {
                "schema": "passed",
                "cefr_limits": "passed",
                "context_personalization": (
                    "reviewed_anchor_preserved"
                    if preserved_context_ids
                    else "passed"
                ),
                "answer_support": "passed",
                "checkpoint_freshness": "passed",
            },
        },
    }


def _aggregate_usage(records: list[dict]) -> dict:
    def total(field: str) -> int | None:
        values = [item.get(field) for item in records if item.get(field) is not None]
        return sum(int(value) for value in values) if values else None

    last = records[-1] if records else {}
    return {
        "provider_calls": len(records),
        "provider": last.get("provider"),
        "model": last.get("model"),
        "temperature": last.get("temperature"),
        "latency_ms": total("latency_ms"),
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "total_tokens": total("total_tokens"),
    }


def _failed_generation_json(error: dict) -> str | None:
    """Extract and mechanically strip non-output fields before full validation."""
    value = error.get("failed_generation")
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return None
    elif isinstance(value, dict):
        payload = copy.deepcopy(value)
    else:
        return None
    if not isinstance(payload, dict):
        return None

    allowed_top = {
        "scenario_title",
        "setting",
        "roles",
        "lesson_surfaces",
        "realizations",
        "context_realizations",
        "stimulus_realizations",
        "choice_realizations",
    }
    allowed_items = {
        "lesson_surfaces": {"lesson_key", "title", "description", "intro"},
        "context_realizations": {
            "request_id", "sentence", "learner_definition",
        },
        "stimulus_realizations": {
            "request_id", "title", "sentences", "text", "opening", "evidence",
            "closing", "prompt",
            "answer", "distractors", "explanation",
        },
        "choice_realizations": {
            "request_id", "prompt", "distractors", "explanation",
        },
        "realizations": {
            "request_id", "kind", "sentence", "learner_definition", "title", "text", "prompt",
            "answer", "distractors", "explanation",
        },
    }
    cleaned = {key: item for key, item in payload.items() if key in allowed_top}
    for bucket, allowed in allowed_items.items():
        values = cleaned.get(bucket)
        if isinstance(values, list):
            cleaned[bucket] = [
                {key: item for key, item in value.items() if key in allowed}
                if isinstance(value, dict)
                else value
                for value in values
            ]
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
