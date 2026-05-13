"""Unit tests for BackgroundJob model (Phase 16)."""
import uuid
import pytest
from app.models.jobs import BackgroundJob


def test_background_job_model_columns():
    """BackgroundJob has all 14 required columns from D-04."""
    cols = {c.name for c in BackgroundJob.__table__.columns}
    required = {
        "id", "job_type", "org_id", "platform_connection_id",
        "status", "progress_current", "progress_total",
        "output", "metadata", "error",
        "started_at", "ended_at", "created_at",
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"


def test_background_job_model_indexes():
    """BackgroundJob declares both composite indexes from D-05."""
    index_names = {idx.name for idx in BackgroundJob.__table__.indexes}
    assert "ix_background_jobs_org_status" in index_names
    assert "ix_background_jobs_org_type_started" in index_names


def test_background_job_model_fk_constraints():
    """BackgroundJob has FK on org_id (non-nullable) and platform_connection_id (nullable)."""
    table = BackgroundJob.__table__
    fk_cols = {fk.parent.name: (fk.column.table.name, fk.parent.nullable)
               for col in table.columns for fk in col.foreign_keys}
    assert "org_id" in fk_cols
    assert fk_cols["org_id"][0] == "organizations"
    assert fk_cols["org_id"][1] is False  # non-nullable
    assert "platform_connection_id" in fk_cols
    assert fk_cols["platform_connection_id"][0] == "platform_connections"
    assert fk_cols["platform_connection_id"][1] is True  # nullable


def test_background_job_jsonb_defaults_use_dict():
    """JSONB columns (output, metadata) use default=dict (callable) not default={} (mutable).
    Using default={} would cause rows to share the same dict — silent data corruption.
    """
    for col_name in ("output", "metadata"):
        col = BackgroundJob.__table__.c[col_name]
        assert col.default is not None, f"{col_name} has no column default set"
        assert col.default.is_callable, (
            f"{col_name} default must be a callable (not a scalar mutable), got: {col.default!r}"
        )
