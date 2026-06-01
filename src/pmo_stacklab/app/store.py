"""Session-keyed storage for per-session pipeline artifacts.

The generalized endpoint persists each process's output and fetches the previous
step's output through this interface, keyed by ``(session_id, key)`` where the key
is a step/process name. Stored values are session artifacts -- chiefly the working
:class:`~pmo_stacklab.modules.core.ImageData`, and also the terminal
:class:`~pmo_stacklab.modules.core.RGBImage` from colour combination -- so the
value type is left general.

The in-memory implementation is sufficient for the single-user build; the abstract
:class:`SessionStore` is the seam that lets a disk-backed, multi-user store (see
the deployment model) drop in later without touching the endpoint.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta, timezone


class SessionStore(ABC):
    """Stores one artifact per ``(session_id, key)`` (key = a step/process name)."""

    @abstractmethod
    def get(self, session_id: str, key: str) -> object | None:
        """Return the stored artifact for ``(session_id, key)``, or ``None``."""

    @abstractmethod
    def put(self, session_id: str, key: str, value: object) -> None:
        """Store ``value`` under ``(session_id, key)``."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryStore(SessionStore):
    """A process-local, in-memory :class:`SessionStore` (single-user / development).

    Each session's artifacts are held together (keyed by session, then by step), so
    every step's full-resolution working data lives in RAM for the session's
    lifetime. To stop that growing without bound over a long observing session,
    each session is stamped with a last-access time and sessions idle longer than
    ``ttl`` are evicted whole on the next access -- the use the previously unused
    ``SESSION_TTL`` was intended for. State is not shared across workers; a
    disk-backed store replaces this for multi-user.

    :param ttl: how long a session may sit idle before its data is evicted.
    :param now: clock returning an aware UTC ``datetime`` (injectable for tests).
    """

    def __init__(
        self,
        ttl: timedelta = timedelta(hours=2),
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._ttl = ttl
        self._now = now
        # session_id -> {key -> value}
        self._data: dict[str, dict[str, object]] = {}
        # session_id -> last access time
        self._seen: dict[str, datetime] = {}

    def _evict_expired(self) -> None:
        """Drop every session idle longer than the TTL."""
        cutoff = self._now() - self._ttl
        stale = [sid for sid, seen in self._seen.items() if seen < cutoff]
        for sid in stale:
            self._data.pop(sid, None)
            self._seen.pop(sid, None)

    def _touch(self, session_id: str) -> None:
        """Mark a session as just accessed, so it is not evicted while in use."""
        self._seen[session_id] = self._now()

    def get(self, session_id: str, key: str) -> object | None:
        self._evict_expired()
        if session_id not in self._data:
            return None
        self._touch(session_id)
        return self._data[session_id].get(key)

    def put(self, session_id: str, key: str, value: object) -> None:
        self._evict_expired()
        self._data.setdefault(session_id, {})[key] = value
        self._touch(session_id)
