"""Process-shared fixed-window request limiting backed by SQLite."""

from __future__ import annotations

import math
import os
import sqlite3
import time
from pathlib import Path


class ProcessSharedRateLimiter:
    """Coordinate limits across local ASGI workers without another service."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get(
            "SPEAKFLOW_RATE_LIMIT_DB",
            "/tmp/speakflow-rate-limits.sqlite3",
        )
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_request_events_key_time "
                "ON request_events(event_key, occurred_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=3000")
        return connection

    def retry_after(self, key: str, *, limit: int, window: int) -> int:
        if limit < 1 or window < 1:
            raise ValueError("rate-limit policy must be positive")
        now = time.time()
        cutoff = now - window
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM request_events WHERE event_key = ? AND occurred_at <= ?",
                (key, cutoff),
            )
            count, oldest = connection.execute(
                "SELECT COUNT(*), MIN(occurred_at) FROM request_events "
                "WHERE event_key = ?",
                (key,),
            ).fetchone()
            if int(count) >= limit:
                connection.commit()
                return max(1, math.ceil(window - (now - float(oldest))))
            connection.execute(
                "INSERT INTO request_events(event_key, occurred_at) VALUES (?, ?)",
                (key, now),
            )
            # Bound abandoned keys even when callers continually use new IPs.
            connection.execute(
                "DELETE FROM request_events WHERE occurred_at <= ?",
                (now - 3600,),
            )
            connection.commit()
        return 0
