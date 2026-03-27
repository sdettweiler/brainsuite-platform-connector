"""
AST-based static analysis for QUAL-01: Broad except-Exception audit.

Scans all Python files under backend/app/ for bare `except Exception` clauses
outside of the explicitly allowed list.
"""
import ast
import pathlib


# Files where broad except Exception is intentionally allowed:
#   - main.py: startup helpers (_run_migrations, _migrate_static_urls_to_objects)
#   - base.py: db session rollback guard
ALLOWED_FILES = {"main.py", "base.py"}

# Functions where broad except Exception is intentionally allowed:
#   - scheduler.py deadlock retry
#   - scheduler.py top-level job dispatchers (APScheduler job isolation)
#   - scoring_job.py batch processor + failure marker (job isolation / non-fatal)
#   - scoring.py refetch job dispatcher (APScheduler job isolation)
#   - brainsuite_score.py persist_and_replace_visualizations (non-fatal, returns None)
#   - meta_sync.py _generate_and_upload_thumbnail (non-fatal, returns None)
ALLOWED_FUNCTIONS = {
    "_harmonize_with_deadlock_retry",
    "run_daily_sync",
    "run_full_resync",
    "run_initial_sync",
    "run_historical_sync",
    "_run_dv360_asset_downloads",
    # Phase 3/4 additions
    "run_scoring_batch",
    "_mark_failed",
    "_run_refetch_job",
    "persist_and_replace_visualizations",
    "_generate_and_upload_thumbnail",
    # Phase 5 additions
    "_process_asset",  # scoring_job.py per-asset error isolation (must not raise in batch loop)
}


def _enclosing_function_names(tree: ast.AST, target_lineno: int) -> set:
    """Return the names of all function definitions that contain the target line."""
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= target_lineno <= (node.end_lineno or target_lineno):
                    names.add(node.name)
    return names


def _find_broad_catches(root: pathlib.Path) -> list:
    """Scan all Python files for bare except Exception outside the allowed list."""
    violations = []
    for py_file in root.rglob("*.py"):
        if py_file.name in ALLOWED_FILES:
            continue
        source = py_file.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # bare `except:` — also a violation
            if node.type is None:
                violations.append(f"{py_file}:{node.lineno}: bare except")
                continue
            if not (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
                continue
            # It's a broad `except Exception` — check if it's in an allowed function
            enclosing = _enclosing_function_names(tree, node.lineno)
            if enclosing & ALLOWED_FUNCTIONS:
                continue
            violations.append(f"{py_file}:{node.lineno}: except Exception")
    return violations


def test_no_broad_except_exception():
    """QUAL-01: No broad except Exception outside the allowed list.

    Allowed locations:
    - app/main.py: startup helpers (fire-and-forget non-fatal)
    - app/db/base.py: session rollback-and-reraise guard
    - app/services/sync/scheduler.py: _harmonize_with_deadlock_retry (intentional
      deadlock detection by string match) and top-level APScheduler job wrappers
      (run_daily_sync, run_full_resync, run_initial_sync, run_historical_sync,
      _run_dv360_asset_downloads)
    - app/services/sync/scoring_job.py: run_scoring_batch (APScheduler job isolation),
      _mark_failed (error logging safety net — must not raise during failure marking),
      _process_asset (per-asset error isolation — must not raise in batch loop)
    - app/api/v1/endpoints/scoring.py: _run_refetch_job (APScheduler job isolation)
    - app/services/brainsuite_score.py: persist_and_replace_visualizations
      (non-fatal viz persistence — returns None on failure)
    - app/services/sync/meta_sync.py: _generate_and_upload_thumbnail
      (non-fatal thumbnail generation — returns None on failure)
    """
    root = pathlib.Path(__file__).parent.parent / "app"
    violations = _find_broad_catches(root)
    assert violations == [], (
        f"Found {len(violations)} broad except Exception blocks:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
