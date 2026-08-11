"""Local command for granting or removing administrator privileges."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from speakflow.features.admin.infrastructure.models import AdminAuditEvent
from speakflow.features.auth.infrastructure.models import AuthSession, User
from speakflow.features.learning_plan.engine.database import session_scope
from speakflow.shared.orm import utc_now


def set_admin(email: str, *, enabled: bool) -> str:
    normalized_email = email.strip().casefold()
    with session_scope() as session:
        user = session.scalar(
            select(User).where(
                User.email == normalized_email,
                User.kind == "registered",
            ).with_for_update()
        )
        if user is None:
            raise ValueError("registered user was not found")
        user.is_admin = enabled
        revoked_at = utc_now()
        sessions = session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        for auth_session in sessions:
            auth_session.revoked_at = revoked_at
        session.add(
            AdminAuditEvent(
                actor_user_id=None,
                target_user_id=user.id,
                action="admin_access_granted" if enabled else "admin_access_removed",
                detail={"source": "local_cli", "sessions_revoked": len(sessions)},
            )
        )
    state = "administrator" if enabled else "regular user"
    return (
        f"{normalized_email} is now a {state}; "
        f"revoked {len(sessions)} existing session(s)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grant or remove SpeakFlow administrator privileges."
    )
    parser.add_argument("action", choices=("grant", "remove"))
    parser.add_argument("email")
    arguments = parser.parse_args()
    try:
        print(set_admin(arguments.email, enabled=arguments.action == "grant"))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
