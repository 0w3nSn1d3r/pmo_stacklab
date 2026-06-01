"""Pipeline error type for expected, user-actionable failures.

Some pipeline failures are not bugs -- they are the data or the chosen settings
not fitting, and the user can fix them: too few matched stars for registration,
frames of differing dimensions reaching the stack, a WCS method on frames without
a WCS. These are raised as :class:`PipelineError` with a plain, actionable
message, so the endpoint can return a clean 4xx telling the user what to change,
rather than a 500 with a raw library traceback message.

Genuinely unexpected errors are left to propagate as ordinary exceptions (the
endpoint still maps those to a 500), so real bugs are not silently dressed up as
user error.
"""
from __future__ import annotations


class PipelineError(Exception):
    """An expected, user-actionable pipeline failure (bad data or settings)."""
