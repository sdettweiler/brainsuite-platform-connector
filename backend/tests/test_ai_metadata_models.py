"""
TDD tests for Task 1: AIInferenceTracking model, MetadataField columns,
MetadataFieldResponse schema, and OPENAI_API_KEY setting.

Phase 09, Plan 01.
"""
import os
import uuid
import pytest


# ---------------------------------------------------------------------------
# Test 1: AIInferenceTracking model can be instantiated
# ---------------------------------------------------------------------------

def test_ai_inference_tracking_instantiation():
    """AIInferenceTracking model can be instantiated with required fields."""
    from app.models.ai_inference import AIInferenceTracking

    tracking = AIInferenceTracking(
        asset_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        ai_inference_status="PENDING",
    )
    assert tracking.ai_inference_status == "PENDING"


def test_ai_inference_tracking_has_unique_constraint():
    """AIInferenceTracking has a UniqueConstraint on asset_id."""
    from app.models.ai_inference import AIInferenceTracking
    from sqlalchemy import inspect as sa_inspect

    constraints = {c.name for c in AIInferenceTracking.__table__.constraints}
    assert "uq_ai_inference_asset" in constraints


def test_ai_inference_tracking_tablename():
    """AIInferenceTracking uses __tablename__ = 'ai_inference_tracking'."""
    from app.models.ai_inference import AIInferenceTracking

    assert AIInferenceTracking.__tablename__ == "ai_inference_tracking"


# ---------------------------------------------------------------------------
# Test 2: MetadataField has auto_fill_enabled and auto_fill_type
# ---------------------------------------------------------------------------

def test_metadata_field_has_auto_fill_enabled():
    """MetadataField model has auto_fill_enabled attribute with default False."""
    from app.models.metadata import MetadataField

    field = MetadataField(
        organization_id=uuid.uuid4(),
        name="test",
        label="Test",
    )
    assert hasattr(field, "auto_fill_enabled")
    # Default should be False (column default)
    assert field.auto_fill_enabled is False or field.auto_fill_enabled is None


def test_metadata_field_has_auto_fill_type():
    """MetadataField model has auto_fill_type attribute (nullable)."""
    from app.models.metadata import MetadataField

    field = MetadataField(
        organization_id=uuid.uuid4(),
        name="test",
        label="Test",
    )
    assert hasattr(field, "auto_fill_type")
    assert field.auto_fill_type is None


# ---------------------------------------------------------------------------
# Test 3: MetadataFieldResponse schema includes new fields
# ---------------------------------------------------------------------------

def test_metadata_field_response_has_auto_fill_enabled():
    """MetadataFieldResponse schema includes auto_fill_enabled field."""
    from app.schemas.creative import MetadataFieldResponse

    schema = MetadataFieldResponse.model_json_schema()
    assert "auto_fill_enabled" in schema["properties"]


def test_metadata_field_response_has_auto_fill_type():
    """MetadataFieldResponse schema includes auto_fill_type field."""
    from app.schemas.creative import MetadataFieldResponse

    schema = MetadataFieldResponse.model_json_schema()
    assert "auto_fill_type" in schema["properties"]


def test_metadata_field_create_has_auto_fill_enabled():
    """MetadataFieldCreate schema includes auto_fill_enabled field with default False."""
    from app.schemas.creative import MetadataFieldCreate

    obj = MetadataFieldCreate(name="test", label="Test")
    assert obj.auto_fill_enabled is False


def test_metadata_field_create_has_auto_fill_type():
    """MetadataFieldCreate schema includes auto_fill_type field with default None."""
    from app.schemas.creative import MetadataFieldCreate

    obj = MetadataFieldCreate(name="test", label="Test")
    assert obj.auto_fill_type is None


# ---------------------------------------------------------------------------
# Test 4: OPENAI_API_KEY defaults to None
# ---------------------------------------------------------------------------

def test_openai_api_key_defaults_to_none():
    """settings.OPENAI_API_KEY defaults to None when env var is absent."""
    # Remove the env var if it's set
    env_backup = os.environ.pop("OPENAI_API_KEY", None)
    try:
        from app.core.config import settings
        assert settings.OPENAI_API_KEY is None
    finally:
        if env_backup is not None:
            os.environ["OPENAI_API_KEY"] = env_backup
