from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

from .config import LOCAL_GUEST_ID


LEGACY_TEST_USER_ID = uuid.UUID(LOCAL_GUEST_ID)
_current_user_id: ContextVar[uuid.UUID] = ContextVar(
    "current_user_id",
    default=LEGACY_TEST_USER_ID,
)


def current_user_id() -> uuid.UUID:
    return _current_user_id.get()


@contextmanager
def bind_user(user_id: uuid.UUID) -> Iterator[None]:
    token = _current_user_id.set(user_id)
    try:
        yield
    finally:
        _current_user_id.reset(token)
