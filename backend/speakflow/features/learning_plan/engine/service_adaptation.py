"""Adaptive-plan proposal creation and decision behavior."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .database import session_scope
from .identity import current_user_id as _user_id
from .models import (
    ActivityAttempt,
    AdaptationProposal,
    LearningPlan,
    SkillEvidence,
    utc_now,
)
from .schemas import AdaptationProposalView
from .service_errors import (
    PlpConflictError,
    PlpNotFoundError,
)
from .service_identity import _database_error
from .service_progress import _proposal_view


class PlpAdaptationMixin:
    def list_adaptation_proposals(self) -> list[AdaptationProposalView]:
        try:
            with session_scope() as session:
                plan = self._active_plan(session)
                if plan is None:
                    return []
                proposals = session.scalars(
                    select(AdaptationProposal)
                    .where(AdaptationProposal.plan_id == plan.id)
                    .order_by(AdaptationProposal.created_at.desc())
                ).all()
                return [_proposal_view(item) for item in proposals]
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def create_adaptation_proposal(self) -> AdaptationProposalView:
        try:
            with session_scope() as session:
                plan = self._active_plan(session)
                if plan is None or plan.active_revision_id is None:
                    raise PlpConflictError("a ready plan is required")
                session.execute(
                    select(LearningPlan.id)
                    .where(LearningPlan.id == plan.id)
                    .with_for_update()
                )
                existing = session.scalar(
                    select(AdaptationProposal)
                    .where(
                        AdaptationProposal.plan_id == plan.id,
                        AdaptationProposal.base_revision_id == plan.active_revision_id,
                        AdaptationProposal.status == "pending",
                    )
                    .order_by(AdaptationProposal.created_at.desc())
                )
                if existing is not None:
                    return _proposal_view(existing)
                rows = session.execute(
                    select(
                        SkillEvidence.skill_id,
                        func.count(SkillEvidence.id),
                        func.count(func.distinct(ActivityAttempt.lesson_id)),
                        func.sum(SkillEvidence.score * SkillEvidence.weight)
                        / func.sum(SkillEvidence.weight),
                    )
                    .join(
                        ActivityAttempt,
                        ActivityAttempt.id == SkillEvidence.attempt_id,
                    )
                    .where(SkillEvidence.user_id == _user_id())
                    .group_by(SkillEvidence.skill_id)
                ).all()
                weak = [
                    {
                        "skill_id": row[0],
                        "evidence_count": int(row[1]),
                        "lesson_count": int(row[2]),
                        "weighted_score": round(float(row[3]), 1),
                    }
                    for row in rows
                    if int(row[1]) >= 2 and int(row[2]) >= 2 and float(row[3]) < 70
                ]
                if not weak:
                    raise PlpConflictError(
                        "there is not enough repeated weak-skill evidence for a proposal"
                    )
                changes = [
                    {
                        "action": "reinforce",
                        "skill_id": item["skill_id"],
                        "scope": "unstarted_future_lessons",
                    }
                    for item in weak
                ]
                proposal = AdaptationProposal(
                    plan_id=plan.id,
                    base_revision_id=plan.active_revision_id,
                    status="pending",
                    summary=(
                        "Reinforce skills with repeated scores below 70% in "
                        "future unstarted lessons."
                    ),
                    changes=changes,
                    evidence=weak,
                )
                session.add(proposal)
                session.flush()
                return _proposal_view(proposal)
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc

    def decide_adaptation(self, proposal_id: uuid.UUID, approve: bool) -> dict:
        try:
            if approve:
                generation = self.create_generation(reason=f"adaptation:{proposal_id}")
                return {
                    "status": "approved",
                    "proposal_id": str(proposal_id),
                    "generation": generation.model_dump(mode="json"),
                }
            with session_scope() as session:
                proposal = session.scalar(
                    select(AdaptationProposal)
                    .join(
                        LearningPlan,
                        AdaptationProposal.plan_id == LearningPlan.id,
                    )
                    .where(
                        AdaptationProposal.id == proposal_id,
                        LearningPlan.user_id == _user_id(),
                    )
                    .with_for_update()
                )
                if proposal is None:
                    raise PlpNotFoundError("adaptation proposal was not found")
                if proposal.status != "pending":
                    raise PlpConflictError(
                        "adaptation proposal has already been decided"
                    )
                proposal.status = "rejected"
                proposal.decided_at = utc_now()
            return {"status": "rejected", "proposal_id": str(proposal_id)}
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
