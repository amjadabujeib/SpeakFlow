"""Thread-safe Groq client selection for approved PLP credential pools."""

from __future__ import annotations

import threading
import time

from openai import OpenAI, RateLimitError

from .generation_support import _provider_retry_after_seconds


class GroqClientPool:
    """Round-robin healthy clients and cool down only the key returning 429."""

    def __init__(
        self,
        *,
        api_keys: tuple[str, ...],
        client: OpenAI | None = None,
        clients: list[OpenAI] | None = None,
    ) -> None:
        if client is not None and clients is not None:
            raise ValueError("provide either client or clients, not both")
        if clients is not None and not clients:
            raise ValueError("clients must contain at least one Groq client")
        self._api_keys = api_keys
        self._clients = list(clients) if clients is not None else None
        if client is not None:
            self._clients = [client]
        self._lock = threading.Lock()
        self._next_index = 0
        self._cooldowns: dict[int, float] = {}

    @property
    def primary_client(self) -> OpenAI | None:
        return self._clients[0] if self._clients else None

    def close(self) -> None:
        closed: set[int] = set()
        for client in self._clients or []:
            identity = id(client)
            if identity not in closed:
                client.close()
                closed.add(identity)

    def completion_create(self, **arguments):
        clients = self._configured_clients()
        shortest_rate_limit: tuple[int, RateLimitError] | None = None
        for client_index in self._available_indexes(len(clients)):
            try:
                return clients[client_index].chat.completions.create(**arguments)
            except RateLimitError as exc:
                retry_after = self._mark_rate_limited(client_index, exc)
                if shortest_rate_limit is None or retry_after < shortest_rate_limit[0]:
                    shortest_rate_limit = (retry_after, exc)
        assert shortest_rate_limit is not None
        # The worker should resume when the first credential recovers, not
        # after the longest cooldown returned by the final attempted key.
        raise shortest_rate_limit[1]

    def _configured_clients(self) -> list[OpenAI]:
        if self._clients is not None:
            return self._clients
        if not self._api_keys:
            raise RuntimeError("GROQ_API_KEYS is required for PLP generation")
        with self._lock:
            if self._clients is None:
                self._clients = [
                    OpenAI(
                        api_key=api_key,
                        base_url="https://api.groq.com/openai/v1",
                        timeout=45.0,
                        max_retries=0,
                    )
                    for api_key in self._api_keys
                ]
        return self._clients

    def _available_indexes(self, client_count: int) -> list[int]:
        with self._lock:
            now = time.monotonic()
            start = self._next_index % client_count
            self._next_index = (start + 1) % client_count
            ordered = [
                (start + offset) % client_count for offset in range(client_count)
            ]
            available = [
                index for index in ordered if self._cooldowns.get(index, 0) <= now
            ]
            if available:
                return available
            # Probe the credential expected to recover first so a fresh 429 can
            # provide the authoritative retry hint for the durable PLP job.
            return [min(ordered, key=lambda index: self._cooldowns.get(index, 0))]

    def _mark_rate_limited(self, index: int, exc: RateLimitError) -> int:
        retry_after = _provider_retry_after_seconds(exc)
        with self._lock:
            self._cooldowns[index] = time.monotonic() + retry_after
        return retry_after
