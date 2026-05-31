"""Application configuration, including the user-configurable pipeline order."""
from __future__ import annotations

from datetime import timedelta

from ..modules.calibration import CALIBRATE
from ..modules.stacking import STACK

# Reserved for future session-store eviction (the in-memory store does not yet
# expire entries).
SESSION_TTL = timedelta(hours=2)

# The pipeline: an ordered tuple of ProcessSpecs. The generalized /api/run endpoint
# indexes this to resolve the requested process and locate its input (the previous
# process's output). Reproject and Post-Process will be inserted here once adopted;
# Upload supplies the initial data ahead of the first entry.
ORDER = (CALIBRATE, STACK)
