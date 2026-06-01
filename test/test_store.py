"""Tests for the in-memory session store, especially TTL eviction."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pmo_stacklab.app.store import InMemoryStore


class _Clock:
    """A controllable clock for exercising TTL eviction deterministically."""

    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kwargs) -> None:
        self.t += timedelta(**kwargs)


class InMemoryStoreTests(unittest.TestCase):
    def test_put_then_get_roundtrip(self) -> None:
        store = InMemoryStore()
        store.put("s1", "Calibrate", 42)
        self.assertEqual(store.get("s1", "Calibrate"), 42)

    def test_missing_returns_none(self) -> None:
        store = InMemoryStore()
        self.assertIsNone(store.get("s1", "Stack"))

    def test_sessions_are_isolated(self) -> None:
        store = InMemoryStore()
        store.put("s1", "Stack", "a")
        store.put("s2", "Stack", "b")
        self.assertEqual(store.get("s1", "Stack"), "a")
        self.assertEqual(store.get("s2", "Stack"), "b")

    def test_idle_session_is_evicted_after_ttl(self) -> None:
        clock = _Clock()
        store = InMemoryStore(ttl=timedelta(hours=2), now=clock)
        store.put("s1", "Stack", "data")

        clock.advance(hours=3)  # idle past the TTL
        # The next access evicts the stale session.
        self.assertIsNone(store.get("s1", "Stack"))

    def test_access_keeps_session_alive(self) -> None:
        clock = _Clock()
        store = InMemoryStore(ttl=timedelta(hours=2), now=clock)
        store.put("s1", "Stack", "data")

        clock.advance(hours=1)
        self.assertEqual(store.get("s1", "Stack"), "data")  # touches it
        clock.advance(hours=1, minutes=30)  # < 2h since the last access
        self.assertEqual(store.get("s1", "Stack"), "data")  # still alive

    def test_eviction_does_not_affect_active_sessions(self) -> None:
        clock = _Clock()
        store = InMemoryStore(ttl=timedelta(hours=2), now=clock)
        store.put("old", "Stack", "x")
        clock.advance(hours=1)
        store.put("new", "Stack", "y")  # 'new' touched now; 'old' is 1h idle

        clock.advance(hours=1, minutes=30)  # old: 2.5h idle (evict), new: 1.5h (keep)
        store.put("trigger", "k", "z")  # any access runs eviction
        self.assertIsNone(store.get("old", "Stack"))
        self.assertEqual(store.get("new", "Stack"), "y")


if __name__ == "__main__":
    unittest.main()
