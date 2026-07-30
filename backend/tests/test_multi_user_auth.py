from __future__ import annotations

import unittest
import uuid

from sqlalchemy import select

from auth_service import (
    AuthEmailConflictError,
    AuthInvalidCredentialsError,
    auth_service,
)
from plp.database import session_scope
from plp.identity import bind_user
from plp.models import GenerationJob, LearningPlan, PlanLesson, PlanRevision, User
from plp.schemas import (
    GuestSessionInput,
    LearnerProfileInput,
    RoleplayScenarioCreate,
    RoleplaySessionStart,
    RoleplayTurnInput,
    SignInInput,
    SignUpInput,
)
from plp.service import PlpNotFoundError, plp_service


class AuthenticationLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.email = f"auth-{uuid.uuid4().hex}@example.test"
        self.user_ids: set[uuid.UUID] = set()

    def tearDown(self) -> None:
        with session_scope() as session:
            for user_id in self.user_ids:
                user = session.get(User, user_id)
                if user is not None:
                    session.delete(user)

    def test_registered_login_duplicate_email_and_revocation(self) -> None:
        created = auth_service.sign_up(
            SignUpInput(
                email=self.email.upper(),
                password="correct-horse-42",
                display_name="Test Learner",
            )
        )
        self.user_ids.add(created.user.user_id)
        self.assertEqual(created.user.email, self.email)
        self.assertEqual(created.user.kind, "registered")
        self.assertNotEqual(created.access_token, "")
        self.assertEqual(
            auth_service.authenticate(created.access_token).user_id,
            created.user.user_id,
        )
        with self.assertRaises(AuthEmailConflictError):
            auth_service.sign_up(
                SignUpInput(
                    email=self.email,
                    password="another-password",
                    display_name="Duplicate",
                )
            )
        with self.assertRaises(AuthInvalidCredentialsError):
            auth_service.sign_in(
                SignInInput(email=self.email, password="wrong-password")
            )

        signed_in = auth_service.sign_in(
            SignInInput(email=self.email, password="correct-horse-42")
        )
        self.assertNotEqual(signed_in.access_token, created.access_token)
        auth_service.sign_out(signed_in.access_token)
        with self.assertRaises(AuthInvalidCredentialsError):
            auth_service.authenticate(signed_in.access_token)
        # Signing out one device/session must not revoke every device.
        self.assertEqual(
            auth_service.authenticate(created.access_token).user_id,
            created.user.user_id,
        )

    def test_guest_sign_out_deletes_the_unrecoverable_guest(self) -> None:
        guest = auth_service.create_guest(
            GuestSessionInput(display_name="Disposable Guest")
        )
        auth_service.sign_out(guest.access_token)
        with self.assertRaises(AuthInvalidCredentialsError):
            auth_service.authenticate(guest.access_token)
        with session_scope() as session:
            self.assertIsNone(session.get(User, guest.user.user_id))


class MultiUserIsolationTests(unittest.TestCase):
    client_session_id = "shared-client-session-20260726"

    def setUp(self) -> None:
        self.first = auth_service.create_guest(
            GuestSessionInput(display_name="Guest One")
        )
        self.second = auth_service.create_guest(
            GuestSessionInput(display_name="Guest Two")
        )

    def tearDown(self) -> None:
        with session_scope() as session:
            for user_id in (self.first.user.user_id, self.second.user.user_id):
                user = session.get(User, user_id)
                if user is not None:
                    session.delete(user)

    @staticmethod
    def _profile(level: str, interest: str) -> LearnerProfileInput:
        return LearnerProfileInput(
            cefr_level=level,
            native_language="Arabic",
            learning_goals=["Speak confidently"],
            interests=[interest],
        )

    def test_profiles_custom_scenarios_sessions_and_reset_are_isolated(self) -> None:
        first_id = self.first.user.user_id
        second_id = self.second.user.user_id

        with bind_user(first_id):
            plp_service.save_profile(self._profile("A2", "Music"))
            with session_scope() as session:
                plan = LearningPlan(user_id=first_id)
                session.add(plan)
                session.flush()
                revision = PlanRevision(
                    plan_id=plan.id,
                    revision=1,
                    status="ready",
                    learner_snapshot={"cefr_level": "A2"},
                    outline={"weeks": []},
                    planner_version="isolation-test",
                    generator_version="isolation-test",
                )
                session.add(revision)
                session.flush()
                plan.active_revision_id = revision.id
                session.add(
                    PlanLesson(
                        revision_id=revision.id,
                        lesson_key="isolation_lesson",
                        week_sequence=1,
                        unit_sequence=1,
                        lesson_sequence=1,
                        lesson_type="vocabulary",
                        estimated_minutes=10,
                        xp=10,
                        skill_ids=[],
                        required_lesson_keys=[],
                        specification={},
                        content_status="pending",
                    )
                )
                job = GenerationJob(revision_id=revision.id, status="complete")
                session.add(job)
                session.flush()
                first_job_id = job.id
            self.assertEqual(
                plp_service.get_generation(first_job_id).job_id,
                first_job_id,
            )
            first_custom = plp_service.create_roleplay_scenario(
                RoleplayScenarioCreate(
                    category="Music",
                    title="Discuss a concert",
                    description="Ask a friend about a concert and arrange when to meet.",
                )
            )
            first_started = plp_service.start_roleplay_session(
                RoleplaySessionStart(
                    client_session_id=self.client_session_id,
                    scenario_id="airport_check_in",
                )
            )
            plp_service.record_roleplay_turn(
                self.client_session_id,
                RoleplayTurnInput(
                    turn_id="first-user-turn",
                    input_mode="text",
                    user_text="I am flying to Rome.",
                    assistant_text="May I see your passport?",
                    grammar_error_units=0,
                    word_count=5,
                ),
                objective_updates=[],
            )

        with bind_user(second_id):
            plp_service.save_profile(self._profile("B2", "History"))
            second_started = plp_service.start_roleplay_session(
                RoleplaySessionStart(
                    client_session_id=self.client_session_id,
                    scenario_id="airport_check_in",
                )
            )
            self.assertNotEqual(first_started.cefr_level, second_started.cefr_level)
            self.assertEqual(plp_service.get_profile().interests, ["History"])
            self.assertNotIn(
                first_custom.id,
                {item.id for item in plp_service.list_roleplay_scenarios()},
            )
            self.assertEqual(
                plp_service.get_roleplay_transcript(
                    self.client_session_id
                ).turns,
                [],
            )
            with self.assertRaises(PlpNotFoundError):
                plp_service.get_generation(first_job_id)
            plp_service.record_roleplay_turn(
                self.client_session_id,
                RoleplayTurnInput(
                    turn_id="second-user-turn",
                    input_mode="text",
                    user_text="I am flying to Madrid.",
                    assistant_text="Do you have a bag to check?",
                    grammar_error_units=0,
                    word_count=5,
                ),
                objective_updates=[],
            )
            self.assertEqual(len(plp_service.list_roleplay_sessions()), 1)

        with bind_user(first_id):
            transcript = plp_service.get_roleplay_transcript(
                self.client_session_id
            )
            self.assertEqual(
                [turn.turn_id for turn in transcript.turns],
                ["first-user-turn"],
            )
            plp_service.reset_local_learner()
            with self.assertRaises(PlpNotFoundError):
                plp_service.get_profile()
            self.assertEqual(plp_service.list_roleplay_sessions(), [])

        # Resetting learning data must preserve the account/session and must
        # never touch another learner.
        self.assertEqual(
            auth_service.authenticate(self.first.access_token).user_id,
            first_id,
        )
        with bind_user(second_id):
            self.assertEqual(plp_service.get_profile().interests, ["History"])
            transcript = plp_service.get_roleplay_transcript(
                self.client_session_id
            )
            self.assertEqual(
                [turn.turn_id for turn in transcript.turns],
                ["second-user-turn"],
            )

        with session_scope() as session:
            owners = session.scalars(
                select(User.id).where(User.id.in_((first_id, second_id)))
            ).all()
            self.assertEqual(set(owners), {first_id, second_id})


if __name__ == "__main__":
    unittest.main()
