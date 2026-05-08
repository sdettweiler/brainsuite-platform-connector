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
