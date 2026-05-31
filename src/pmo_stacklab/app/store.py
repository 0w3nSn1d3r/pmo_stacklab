"""Session-keyed storage for the working ImageData between pipeline steps.

The generalized endpoint persists each process's output and fetches the previous
step's output through this interface. The in-memory implementation is sufficient
for the single-user build; the abstract :class:`SessionStore` is the seam that lets
a disk-backed, multi-user store (see the deployment model) drop in later without
touching the endpoint.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..modules.core import ImageData


class SessionStore(ABC):
    """Stores one :class:`ImageData` per ``(session_id, process)`` key."""

    @abstractmethod
    def get(self, session_id: str, process: str) -> ImageData | None:
        """Return the stored ImageData for ``(session_id, process)``, or ``None``."""

    @abstractmethod
    def put(self, session_id: str, process: str, data: ImageData) -> None:
        """Store ``data`` as the output of ``process`` for ``session_id``."""


class InMemoryStore(SessionStore):
    """A process-local, in-memory :class:`SessionStore` (single-user / development).

    Holds references in a dict keyed by ``(session_id, process)``. State lives only
    for the lifetime of the process and is not shared across workers -- adequate for
    the single-user deployment; a disk-backed store replaces this for multi-user.
    """

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], ImageData] = {}

    def get(self, session_id: str, process: str) -> ImageData | None:
        return self._data.get((session_id, process))

    def put(self, session_id: str, process: str, data: ImageData) -> None:
        self._data[(session_id, process)] = data
