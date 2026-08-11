from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from speakflow.features.auth.application.errors import (
    AuthEmailConflictError,
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from speakflow.features.auth.application.ports import (
    AuthenticationPort,
    GuestSessionCommand,
    SignInCommand,
    SignUpCommand,
)
from speakflow.features.auth.domain import AuthenticatedUser, IssuedSession
from speakflow.features.auth.infrastructure.models import AuthSession, User
from speakflow.features.learning_plan.engine.database import session_scope

SESSION_DAYS = 30
GUEST_SESSION_DAYS = 7
ADMIN_SESSION_HOURS = 8
MAX_ACTIVE_SESSIONS = 5
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class AuthService:
    """Authentication use cases backed by the SQLAlchemy adapter."""

    def sign_up(self, payload: SignUpCommand) -> IssuedSession:
        try:
            with session_scope() as session:
                existing = session.scalar(
                    select(User).where(User.email == payload.email)
                )
                if existing is not None:
                    raise AuthEmailConflictError(
                        "an account already exists for this email"
                    )
                user = User(
                    id=uuid.uuid4(),
                    kind="registered",
                    email=payload.email,
                    display_name=payload.display_name,
                    password_hash=_hash_password(payload.password),
                )
                session.add(user)
                session.flush()
                return _create_session(session, user, timedelta(days=SESSION_DAYS))
        except AuthEmailConflictError:
            raise
        except IntegrityError as exc:
            raise AuthEmailConflictError(
                "an account already exists for this email"
            ) from exc
        except SQLAlchemyError as exc:
            raise AuthUnavailableError(
                "authentication database is unavailable"
            ) from exc

    def sign_in(self, payload: SignInCommand) -> IssuedSession:
        try:
            with session_scope() as session:
                user = session.scalar(
                    select(User).where(
                        User.email == payload.email,
                        User.kind == "registered",
                    )
                )
                if (
                    user is None
                    or user.password_hash is None
                    or not _verify_password(payload.password, user.password_hash)
                ):
                    raise AuthInvalidCredentialsError(
                        "email or password is incorrect"
                    )
                lifetime = (
                    timedelta(hours=ADMIN_SESSION_HOURS)
                    if user.is_admin
                    else timedelta(days=SESSION_DAYS)
                )
                return _create_session(session, user, lifetime)
        except AuthInvalidCredentialsError:
            raise
        except SQLAlchemyError as exc:
            raise AuthUnavailableError(
                "authentication database is unavailable"
            ) from exc

    def create_guest(self, payload: GuestSessionCommand) -> IssuedSession:
        try:
            with session_scope() as session:
                now = _utc_now()
                live_guest_session = exists(
                    select(AuthSession.id).where(
                        AuthSession.user_id == User.id,
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > now,
                    )
                )
                session.execute(
                    delete(User)
                    .where(User.kind == "guest", ~live_guest_session)
                    .execution_options(synchronize_session=False)
                )
                user = User(
                    id=uuid.uuid4(),
                    kind="guest",
                    display_name=payload.display_name,
                )
                session.add(user)
                session.flush()
                return _create_session(
                    session,
                    user,
                    timedelta(days=GUEST_SESSION_DAYS),
                )
        except SQLAlchemyError as exc:
            raise AuthUnavailableError(
                "authentication database is unavailable"
            ) from exc

    def authenticate(self, token: str) -> AuthenticatedUser:
        token_hash = _token_hash(token)
        now = _utc_now()
        try:
            with session_scope() as session:
                user = session.scalar(
                    select(User)
                    .join(AuthSession, AuthSession.user_id == User.id)
                    .where(
                        AuthSession.token_hash == token_hash,
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > now,
                    )
                )
                if user is None:
                    raise AuthInvalidCredentialsError(
                        "authentication session is invalid or expired"
                    )
                return _user_view(user)
        except AuthInvalidCredentialsError:
            raise
        except SQLAlchemyError as exc:
            raise AuthUnavailableError(
                "authentication database is unavailable"
            ) from exc

    def sign_out(self, token: str) -> None:
        try:
            with session_scope() as session:
                auth_session = session.scalar(
                    select(AuthSession).where(
                        AuthSession.token_hash == _token_hash(token),
                        AuthSession.revoked_at.is_(None),
                    ).with_for_update()
                )
                if auth_session is not None:
                    user = session.get(User, auth_session.user_id)
                    if user is not None and user.kind == "guest":
                        session.delete(user)
                    else:
                        auth_session.revoked_at = _utc_now()
        except SQLAlchemyError as exc:
            raise AuthUnavailableError(
                "authentication database is unavailable"
            ) from exc


def _create_session(session, user: User, lifetime: timedelta) -> IssuedSession:
    now = _utc_now()
    session.execute(
        select(User.id).where(User.id == user.id).with_for_update()
    )
    session.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            (AuthSession.revoked_at.is_not(None)) | (AuthSession.expires_at <= now),
        )
    )
    retained_ids = session.scalars(
        select(AuthSession.id)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .order_by(AuthSession.created_at.desc())
        .limit(MAX_ACTIVE_SESSIONS - 1)
    ).all()
    session.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            AuthSession.id.not_in(retained_ids),
        )
    )
    raw_token = secrets.token_urlsafe(48)
    expires_at = now + lifetime
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            expires_at=expires_at,
        )
    )
    session.flush()
    return IssuedSession(
        access_token=raw_token,
        expires_at=expires_at,
        user=_user_view(user),
    )


def _user_view(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user.id,
        kind=user.kind,
        email=user.email,
        display_name=user.display_name
        or ("Guest" if user.kind in {"guest", "local_guest"} else "Learner"),
        is_admin=user.is_admin,
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$", 5)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(salt.encode("ascii")),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(
            derived,
            base64.urlsafe_b64decode(expected.encode("ascii")),
        )
    except (binascii.Error, OverflowError, ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


auth_service: AuthenticationPort = AuthService()
