from __future__ import annotations

import atexit
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_URL


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=4,
            max_overflow=2,
            future=True,
        )
        _session_factory = sessionmaker(
            bind=_engine, expire_on_commit=False, autoflush=False
        )
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def dispose_engine() -> None:
    """Close pooled database connections and reset the lazy session factory."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


atexit.register(dispose_engine)
