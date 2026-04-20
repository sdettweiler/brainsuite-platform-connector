"""Pydantic schemas for BrainSuite field mapping endpoints (Phase 13)."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re
import uuid


class FieldMappingStandard(BaseModel):
    """A single standard BrainSuite API field mapping."""
    api_field_name: str = Field(..., description="Standard BrainSuite API field name (e.g. 'brandValues')")
    metadata_field_id: Optional[uuid.UUID] = Field(None, description="Mapped metadata field UUID, or None for unmapped")
    is_mandatory: bool = Field(False, description="If True, scoring skips assets missing this field's value")


class FieldMappingCustom(BaseModel):
    """A single custom BrainSuite API field mapping."""
    api_field_name: str = Field(..., min_length=1, max_length=255, description="Custom API field name")
    metadata_field_id: Optional[uuid.UUID] = Field(None, description="Mapped metadata field UUID")
    is_mandatory: bool = Field(False, description="If True, scoring skips assets missing this field's value")

    @field_validator("api_field_name")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            raise ValueError("API field name must start with a letter and contain only letters, digits, and underscores")
        return v


class FieldMappingUpdate(BaseModel):
    """PUT /apps/{app_id}/field-mappings request body. Replaces all mappings atomically."""
    standard_fields: list[FieldMappingStandard] = Field(
        ...,
        description="All standard field mappings for this app"
    )
    custom_fields: list[FieldMappingCustom] = Field(
        default_factory=list,
        description="All custom field mappings for this app"
    )


class MetadataFieldOption(BaseModel):
    """A metadata field available for mapping (dropdown option)."""
    id: uuid.UUID
    name: str
    label: str
    field_type: str  # SELECT, TEXT, NUMBER


class FieldMappingRow(BaseModel):
    """A single field mapping row in the GET response (standard or custom)."""
    api_field_name: str
    metadata_field_id: Optional[uuid.UUID] = None
    is_mandatory: bool = False
    is_custom: bool = False


class FieldMappingResponse(BaseModel):
    """GET /apps/{app_id}/field-mappings response."""
    app_id: uuid.UUID
    app_name: str
    app_type: str  # VIDEO or IMAGE
    standard_fields: list[FieldMappingRow]
    custom_fields: list[FieldMappingRow]
    metadata_options: list[MetadataFieldOption]

    class Config:
        from_attributes = True
