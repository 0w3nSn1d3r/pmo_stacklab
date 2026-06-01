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


class SessionStore(ABC):
    """Stores one artifact per ``(session_id, key)`` (key = a step/process name)."""

    @abstractmethod
    def get(self, session_id: str, key: str) -> object | None:
        """Return the stored artifact for ``(session_id, key)``, or ``None``."""

    @abstractmethod
    def put(self, session_id: str, key: str, value: object) -> None:
        """Store ``value`` under ``(session_id, key)``."""


class InMemoryStore(SessionStore):
    """A process-local, in-memory :class:`SessionStore` (single-user / development).

    Holds references in a dict keyed by ``(session_id, key)``. State lives only for
    the lifetime of the process and is not shared across workers -- adequate for the
    single-user deployment; a disk-backed store replaces this for multi-user.
    """

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], object] = {}

    def get(self, session_id: str, key: str) -> object | None:
        return self._data.get((session_id, key))

    def put(self, session_id: str, key: str, value: object) -> None:
        self._data[(session_id, key)] = value
