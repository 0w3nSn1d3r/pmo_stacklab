"""Small request-scoped helpers for the app blueprints."""
from __future__ import annotations

import os

from flask import session


def session_id() -> str:
    """Return this browser session's stable id, creating one on first use.

    Used to key the per-session working data in the
    :class:`~pmo_stacklab.app.store.SessionStore`. This is the single-user
    stand-in for authentication; a multi-user build would derive the key from the
    authenticated user instead.
    """
    if "session_id" not in session:
        session["session_id"] = os.urandom(16).hex()
    return session["session_id"]
