"""
AST-based static analysis stub for QUAL-01: Broad except-Exception audit.

Implementation target: plan 02-05.

The test will use the `ast` module to scan all Python files in the backend
for bare `except Exception` clauses outside of the allowed list:
  - app/main.py: startup helpers (_run_migrations, _migrate_static_urls_to_objects,
                  _background_startup, lifespan)
  - app/db/base.py: rollback guard
  - app/services/sync/scheduler.py: deadlock retry

All tests are skipped until implementation is complete.
"""
import pytest


@pytest.mark.skip(reason="stub - implementation in plan 02-05")
def test_no_broad_except_exception():
    """No Python file in backend/app/ uses bare 'except Exception' outside the allowed list."""
    pass
