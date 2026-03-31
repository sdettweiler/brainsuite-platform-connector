"""Shared BrainSuite exception classes used by all BrainSuite service modules.

Centralising these here prevents the class-identity mismatch that occurs when
each service module defines its own copy: two classes with the same name but
different Python identity are never equal in isinstance() checks, so a caller
that imports BrainSuiteJobError from one module will NOT catch the exception
raised by another module's copy of the same-named class.
"""
from datetime import datetime


class BrainSuiteRateLimitError(Exception):
    """Raised when BrainSuite API responds with HTTP 429."""

    def __init__(self, reset_at: datetime) -> None:
        self.reset_at = reset_at
        super().__init__(f"Rate limited until {reset_at.isoformat()}")


class BrainSuite5xxError(Exception):
    """Raised when BrainSuite API responds with a 5xx error."""
    pass


class BrainSuiteJobError(Exception):
    """Raised when a BrainSuite job fails, goes stale, or times out."""
    pass
