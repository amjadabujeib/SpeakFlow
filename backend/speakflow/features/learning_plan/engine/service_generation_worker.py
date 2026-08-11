"""Provider-backed generation of individual lessons and weekly cohorts."""

from __future__ import annotations

import copy
import uuid

from sqlalchemy import select

from .database import session_scope
from .generator import GenerationError
from .models import GenerationJob, PlanLesson, PlanRevision, utc_now
from .retrieval import WEEKLY_LEXICAL_CANDIDATE_LIMIT


def _classify_lexical_exposure(
    ready_contents: list[tuple[object, dict | None]],
    *,
    current_revision_id: object,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Separate current-plan exclusions from older-revision review candidates."""

    used_ids: set[str] = set()
    used_terms: set[str] = set()
    historical_ids: set[str] = set()
    historical_terms: set[str] = set()
    for content_revision_id, content in ready_contents:
        target_ids = (
            used_ids if content_revision_id == current_revision_id else historical_ids
        )
        target_terms = (
            used_terms
            if content_revision_id == current_revision_id
            else historical_terms
        )
        writer_request = (content or {}).get("provenance", {}).get("writer_request", {})
        for target in writer_request.get("prototype_targets", []):
            concept_id = target.get("concept_id")
            if isinstance(concept_id, str) and concept_id:
                target_ids.add(concept_id)
            term = target.get("term")
            if isinstance(term, str) and term.strip():
                target_terms.add(term.strip().casefold())
    historical_ids.difference_update(used_ids)
    historical_terms.difference_update(used_terms)
    return used_ids, used_terms, historical_ids, historical_terms


class PlpGenerationWorkerMixin:
    def _generate_lesson(self, job_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
        # Commit the attempt before any embedding/network work. A generation
        # failure must never roll this counter back into an infinite loop.
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            lesson = session.get(PlanLesson, lesson_id)
            if job is None or lesson is None or lesson.content_status == "ready":
                return
            revision = session.get(PlanRevision, lesson.revision_id)
            assert revision is not None
            support_language = revision.learner_snapshot.get("support_language")
            lesson.generation_attempts += 1
            lesson.generation_error = None
            job.updated_at = utc_now()
            specification = copy.deepcopy(lesson.specification)
            lesson_type = lesson.lesson_type
            skill_ids = list(lesson.skill_ids)
            lesson_key = lesson.lesson_key

        with session_scope() as session:
            if lesson_type == "assessment":
                # Retrieve each assessed skill, then deduplicate.
                chunks_by_id = {}
                for skill_id in skill_ids:
                    for chunk in self.retriever.retrieve(
                        session,
                        query=f"{specification['title']} {skill_id}",
                        cefr_level=specification["cefr_level"],
                        skill_ids=[skill_id],
                        limit=3,
                    ):
                        chunks_by_id[chunk.id] = chunk
                chunks = list(chunks_by_id.values())[:8]
            else:
                chunks = self.retriever.retrieve(
                    session,
                    query=(
                        f"{specification['title']} {specification['description']} "
                        f"{' '.join(specification.get('topics', []))}"
                    ),
                    cefr_level=specification["cefr_level"],
                    skill_ids=skill_ids,
                )
        generated, source_refs = self.generator.generate(
            specification=specification,
            lesson_key=lesson_key,
            chunks=chunks,
            support_language=support_language,
        )

        with session_scope() as session:
            lesson = session.get(PlanLesson, lesson_id)
            if lesson is None:
                return
            lesson.content = generated
            lesson.source_refs = source_refs
            lesson.content_status = "ready"
            lesson.generation_error = None

    def _generate_week(self, job_id: uuid.UUID, week_sequence: int) -> None:
        """Generate and persist one weekly cohort after one writer call."""
        with session_scope() as session:
            job = session.get(GenerationJob, job_id)
            if job is None:
                return
            revision_id = job.revision_id
            revision = session.get(PlanRevision, revision_id)
            assert revision is not None
            lessons = session.scalars(
                select(PlanLesson)
                .where(
                    PlanLesson.revision_id == revision_id,
                    PlanLesson.week_sequence == week_sequence,
                )
                .order_by(PlanLesson.lesson_sequence)
            ).all()
            if len(lessons) != 5:
                raise GenerationError(
                    f"mission week {week_sequence} must contain exactly five lessons"
                )
            if all(lesson.content_status == "ready" for lesson in lessons):
                return
            if any(lesson.content_status == "ready" for lesson in lessons):
                raise GenerationError(
                    "a mission cohort is partially ready; refusing to overwrite immutable content"
                )
            prior_attempts = {lesson.generation_attempts for lesson in lessons}
            if len(prior_attempts) != 1:
                raise GenerationError(
                    "mission cohort generation attempts diverged; refusing an ambiguous retry"
                )
            for lesson in lessons:
                lesson.generation_attempts += 1
                lesson.generation_error = None
            generation_attempt = next(iter(prior_attempts)) + 1
            job.updated_at = utc_now()
            support_language = revision.learner_snapshot.get("support_language")
            level = lessons[0].specification["cefr_level"]
            selected_interest = (
                lessons[0].specification.get("interest", {}).get("label")
            )
            interests = [selected_interest] if selected_interest else []
            first_specification = lessons[0].specification
            scenario = first_specification.get("scenario", {})
            palette_query = " ".join(
                [
                    f"{level} English vocabulary for {selected_interest or 'general English'}.",
                    f"Scenario: {scenario.get('title', '')}.",
                    f"Learner task: {first_specification.get('can_do', '')}.",
                    "Setting: " + ", ".join(scenario.get("setting_slots", [])) + ".",
                    "Lesson domains: "
                    + ", ".join(dict.fromkeys(lesson.lesson_type for lesson in lessons))
                    + ".",
                ]
            )
            palette_seed = (
                f"{lessons[0].specification.get('variation_seed', 'default')}:"
                f"{week_sequence}:{generation_attempt}"
            )
            skill_ids = list(
                dict.fromkeys(
                    skill_id for lesson in lessons for skill_id in lesson.skill_ids
                )
            )
            lesson_shells = [
                {
                    "lesson_key": lesson.lesson_key,
                    "sequence": lesson.lesson_sequence,
                    "week_sequence": lesson.week_sequence,
                    "type": lesson.lesson_type,
                    "skill_ids": list(lesson.skill_ids),
                    "specification": copy.deepcopy(lesson.specification),
                }
                for lesson in lessons
            ]
            ready_contents = session.execute(
                select(PlanLesson.revision_id, PlanLesson.content)
                .join(PlanRevision, PlanRevision.id == PlanLesson.revision_id)
                .where(
                    PlanRevision.plan_id == revision.plan_id,
                    PlanLesson.content_status == "ready",
                )
            ).all()
            (
                used_concept_ids,
                used_concept_terms,
                historical_concept_ids,
                historical_concept_terms,
            ) = _classify_lexical_exposure(
                ready_contents,
                current_revision_id=revision_id,
            )

        with session_scope() as session:
            chunks = self.retriever.retrieve_exact(
                session,
                cefr_level=level,
                skill_ids=skill_ids,
            )
            lexical_palette = self.retriever.retrieve_lexical_palette(
                session,
                cefr_level=level,
                interests=interests,
                seed=palette_seed,
                # Over-fetch because preparation excludes circular, excessively
                # long, or otherwise unsafe source definitions before choosing
                # the two words taught in the week.
                limit=WEEKLY_LEXICAL_CANDIDATE_LIMIT,
                exclude_ids=used_concept_ids,
                exclude_terms=used_concept_terms,
                deprioritize_ids=historical_concept_ids,
                deprioritize_terms=historical_concept_terms,
                query_text=palette_query,
            )
            if len(lexical_palette) < 2:
                raise GenerationError(
                    "weekly vocabulary retrieval needs at least two safe distinct "
                    f"terms for {level}; found {len(lexical_palette)}"
                )
        generated = self.weekly_generator.generate(
            lessons=lesson_shells,
            chunks=chunks,
            lexical_palette=lexical_palette,
            support_language=support_language,
            generation_attempt=generation_attempt,
        )
        if set(generated) != {item["lesson_key"] for item in lesson_shells}:
            raise GenerationError(
                "weekly compiler returned an incomplete lesson cohort"
            )

        # One transaction makes the cohort immutable and prevents a half-week
        # from becoming visible if persistence or validation fails.
        with session_scope() as session:
            lessons = session.scalars(
                select(PlanLesson)
                .where(
                    PlanLesson.revision_id == revision_id,
                    PlanLesson.week_sequence == week_sequence,
                )
                .order_by(PlanLesson.lesson_sequence)
                .with_for_update()
            ).all()
            if any(lesson.content_status == "ready" for lesson in lessons):
                raise GenerationError(
                    "mission cohort changed during generation; refusing to overwrite it"
                )
            for lesson in lessons:
                payload, source_refs = generated[lesson.lesson_key]
                lesson.content = payload
                lesson.source_refs = source_refs
                lesson.content_status = "ready"
                lesson.generation_error = None
