from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import main
from speakflow.features.admin.cli import set_admin
from speakflow.features.admin.infrastructure.models import AdminAuditEvent
from speakflow.features.auth.application.errors import AuthInvalidCredentialsError
from speakflow.features.auth.infrastructure.models import User
from speakflow.features.auth.infrastructure.service import (
    _verify_password,
    auth_service,
)
from speakflow.features.auth.presentation.schemas import SignInInput, SignUpInput
from speakflow.features.learning_plan.engine.database import session_scope
from speakflow.features.learning_plan.engine.models import (
    GenerationJob,
    LearningPlan,
    PlanRevision,
)
from speakflow.features.learning_plan.engine.service_grading import _encode_job_failure
from speakflow.shared.orm import utc_now

main.app.state.runtime_model_loading = "lazy"


class AuthenticationDefensiveParsingTests(unittest.TestCase):
    def test_corrupt_password_hash_is_treated_as_invalid_credentials(self) -> None:
        self.assertFalse(
            _verify_password(
                "correct-horse-42",
                "scrypt$16384$8$1$not-valid-base64$also-not-valid-base64",
            )
        )
        self.assertFalse(
            _verify_password(
                "correct-horse-42",
                "scrypt$999999999999999999999$8$1$YWJj$YWJj",
            )
        )


class AdminSecurityPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        suffix = uuid.uuid4().hex
        self.admin = auth_service.sign_up(
            SignUpInput(
                email=f"admin-{suffix}@example.test",
                password="correct-horse-42",
                display_name="Test Administrator",
            )
        )
        self.target = auth_service.sign_up(
            SignUpInput(
                email=f"target-{suffix}@example.test",
                password="correct-horse-42",
                display_name="Target Learner",
            )
        )
        with session_scope() as session:
            session.get(User, self.admin.user.user_id).is_admin = True

    def tearDown(self) -> None:
        with session_scope() as session:
            session.execute(
                delete(AdminAuditEvent).where(
                    AdminAuditEvent.target_user_id.in_(
                        (self.admin.user.user_id, self.target.user.user_id)
                    )
                )
            )
            for user_id in (self.admin.user.user_id, self.target.user.user_id):
                user = session.get(User, user_id)
                if user is not None:
                    session.delete(user)

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_admin_claim_authorization_revocation_and_audit(self) -> None:
        with TestClient(main.app) as client:
            me = client.get("/api/auth/me", headers=self._headers(self.admin.access_token))
            self.assertEqual(me.status_code, 200)
            self.assertTrue(me.json()["is_admin"])

            forbidden = client.get(
                "/admin/errors",
                headers=self._headers(self.target.access_token),
            )
            self.assertEqual(forbidden.status_code, 403)

            revoked = client.post(
                f"/admin/users/{self.target.user.user_id}/revoke",
                headers=self._headers(self.admin.access_token),
                json={"reason": "Suspected credential compromise"},
            )
            self.assertEqual(revoked.status_code, 200)
            self.assertEqual(revoked.json()["revoked_count"], 1)

            directory = client.get(
                "/admin/users",
                headers=self._headers(self.admin.access_token),
                params={"query": self.target.user.email},
            )
            self.assertEqual(directory.status_code, 200)
            self.assertEqual(directory.json()["total"], 1)
            self.assertEqual(
                directory.json()["items"][0]["id"],
                str(self.target.user.user_id),
            )

            audit_history = client.get(
                "/admin/audit-events",
                headers=self._headers(self.admin.access_token),
            )
            self.assertEqual(audit_history.status_code, 200)
            self.assertTrue(
                any(
                    item["id"] == revoked.json()["audit_event_id"]
                    for item in audit_history.json()["items"]
                )
            )

            signed_out = client.get(
                "/api/auth/me",
                headers=self._headers(self.target.access_token),
            )
            self.assertEqual(signed_out.status_code, 401)

        with session_scope() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.id == uuid.UUID(revoked.json()["audit_event_id"])
                )
            )
            self.assertIsNotNone(audit)
            self.assertEqual(audit.actor_user_id, self.admin.user.user_id)
            self.assertEqual(audit.target_user_id, self.target.user.user_id)
            self.assertEqual(
                audit.detail["reason"],
                "Suspected credential compromise",
            )

    def test_new_administrator_sessions_expire_after_eight_hours(self) -> None:
        signed_in = auth_service.sign_in(
            SignInInput(
                email=self.admin.user.email,
                password="correct-horse-42",
            )
        )
        remaining = signed_in.expires_at - utc_now()
        self.assertGreater(remaining.total_seconds(), 7 * 60 * 60)
        self.assertLessEqual(remaining.total_seconds(), 8 * 60 * 60)

    def test_error_feed_never_returns_raw_failure_text(self) -> None:
        secret_marker = "SECRET-INTERNAL-PATH"
        with session_scope() as session:
            plan = LearningPlan(user_id=self.admin.user.user_id)
            session.add(plan)
            session.flush()
            revision = PlanRevision(
                plan_id=plan.id,
                revision=1,
                status="failed",
                learner_snapshot={},
                outline={},
            )
            session.add(revision)
            session.flush()
            session.add(
                GenerationJob(
                    revision_id=revision.id,
                    status="failed",
                    error=_encode_job_failure(
                        secret_marker,
                        failure_kind="internal",
                        retry_after_seconds=None,
                    ),
                )
            )

        with TestClient(main.app) as client:
            response = client.get(
                "/admin/errors",
                headers=self._headers(self.admin.access_token),
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(secret_marker, response.text)
        self.assertTrue(
            any(item["failure_kind"] == "internal" for item in response.json()["errors"])
        )

    def test_revocation_requires_a_meaningful_reason(self) -> None:
        with TestClient(main.app) as client:
            response = client.post(
                f"/admin/users/{self.target.user.user_id}/revoke",
                headers=self._headers(self.admin.access_token),
                json={"reason": "  "},
            )
            still_signed_in = client.get(
                "/api/auth/me",
                headers=self._headers(self.target.access_token),
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(still_signed_in.status_code, 200)
        with session_scope() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.target_user_id == self.target.user.user_id,
                    AdminAuditEvent.action == "user_sessions_revoked",
                )
            )
        self.assertIsNone(audit)

    def test_cli_privilege_change_revokes_existing_sessions(self) -> None:
        result = set_admin(self.target.user.email, enabled=True)
        self.assertIn("administrator", result)
        with self.assertRaises(AuthInvalidCredentialsError):
            auth_service.authenticate(self.target.access_token)
        with session_scope() as session:
            target = session.get(User, self.target.user.user_id)
            self.assertTrue(target.is_admin)
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.target_user_id == self.target.user.user_id,
                    AdminAuditEvent.action == "admin_access_granted",
                )
            )
            self.assertIsNotNone(audit)
