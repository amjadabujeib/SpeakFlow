from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from plp.database import session_scope
from plp.models import AuthSession, User
from plp.schemas import (
    AuthSessionView,
    AuthUserView,
    GuestSessionInput,
    SignInInput,
    SignUpInput,
)


SESSION_DAYS = 30
GUEST_SESSION_DAYS = 7
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class AuthInvalidCredentialsError(RuntimeError):
    pass


class AuthEmailConflictError(RuntimeError):
    pass


class AuthUnavailableError(RuntimeError):
    pass


class AuthService:
    def sign_up(self, payload: SignUpInput) -> AuthSessionView:
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
                return _create_session(session, user, SESSION_DAYS)
        except AuthEmailConflictError:
            raise
        except IntegrityError as exc:
            raise AuthEmailConflictError(
                "an account already exists for this email"
            ) from exc
        except SQLAlchemyError as exc:
            raise AuthUnavailableError("authentication database is unavailable") from exc

    def sign_in(self, payload: SignInInput) -> AuthSessionView:
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
                return _create_session(session, user, SESSION_DAYS)
        except AuthInvalidCredentialsError:
            raise
        except SQLAlchemyError as exc:
            raise AuthUnavailableError("authentication database is unavailable") from exc

    def create_guest(self, payload: GuestSessionInput) -> AuthSessionView:
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
                    .where(
                        User.kind == "guest",
                        ~live_guest_session,
                    )
                    .execution_options(synchronize_session=False)
                )
                user = User(
                    id=uuid.uuid4(),
                    kind="guest",
                    display_name=payload.display_name,
                )
                session.add(user)
                session.flush()
                return _create_session(session, user, GUEST_SESSION_DAYS)
        except SQLAlchemyError as exc:
            raise AuthUnavailableError("authentication database is unavailable") from exc

    def authenticate(self, token: str) -> AuthUserView:
        token_hash = _token_hash(token)
        now = _utc_now()
        try:
            with session_scope() as session:
                auth_session = session.scalar(
                    select(AuthSession).where(
                        AuthSession.token_hash == token_hash,
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > now,
                    )
                )
                if auth_session is None:
                    raise AuthInvalidCredentialsError(
                        "authentication session is invalid or expired"
                    )
                user = session.get(User, auth_session.user_id)
                if user is None:
                    raise AuthInvalidCredentialsError(
                        "authentication session is invalid or expired"
                    )
                return _user_view(user)
        except AuthInvalidCredentialsError:
            raise
        except SQLAlchemyError as exc:
            raise AuthUnavailableError("authentication database is unavailable") from exc

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
                        # A guest has no recovery credential. Sign-out is the
                        # explicit lifecycle boundary, so remove its isolated
                        # prototype data instead of retaining an unreachable
                        # account forever.
                        session.delete(user)
                    else:
                        auth_session.revoked_at = _utc_now()
        except SQLAlchemyError as exc:
            raise AuthUnavailableError("authentication database is unavailable") from exc


def _create_session(
    session,
    user: User,
    lifetime_days: int,
) -> AuthSessionView:
    raw_token = secrets.token_urlsafe(48)
    expires_at = _utc_now() + timedelta(days=lifetime_days)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            expires_at=expires_at,
        )
    )
    session.flush()
    return AuthSessionView(
        access_token=raw_token,
        expires_at=expires_at,
        user=_user_view(user),
    )


def _user_view(user: User) -> AuthUserView:
    return AuthUserView(
        user_id=user.id,
        kind=user.kind,
        email=user.email,
        display_name=user.display_name or (
            "Guest" if user.kind in {"guest", "local_guest"} else "Learner"
        ),
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
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


auth_service = AuthService()
