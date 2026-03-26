"""ScoringEndpointType — routing enum and lookup table for BrainSuite scoring endpoints.

Determines which BrainSuite API endpoint to use based on the creative asset's
platform and asset_format. Populated at sync time (never inferred at scoring time).

Decision reference: D-09, D-10, D-11 in 05-CONTEXT.md.

Supported combinations (D-11):

    platform    | asset_format | ScoringEndpointType
    ------------|--------------|--------------------
    META        | VIDEO        | VIDEO
    META        | IMAGE        | STATIC_IMAGE
    TIKTOK      | VIDEO        | VIDEO
    TIKTOK      | IMAGE        | UNSUPPORTED
    GOOGLE_ADS  | VIDEO        | VIDEO
    GOOGLE_ADS  | IMAGE        | UNSUPPORTED
    DV360       | VIDEO        | VIDEO
    DV360       | IMAGE        | UNSUPPORTED
    any         | CAROUSEL     | UNSUPPORTED

Anything not in the table (unknown platform, unknown format, None values) defaults
to UNSUPPORTED — the safe default that excludes the asset from scoring.
"""
from enum import Enum
from typing import Optional


class ScoringEndpointType(str, Enum):
    """Routing identifier for which BrainSuite scoring endpoint to use.

    VIDEO        — ACE_VIDEO_SMV_API (existing video scoring pipeline)
    STATIC_IMAGE — ACE_STATIC_SOCIAL_STATIC_API (Phase 5 image scoring)
    UNSUPPORTED  — asset type not supported; excluded from scoring batch
    """

    VIDEO = "VIDEO"
    STATIC_IMAGE = "STATIC_IMAGE"
    UNSUPPORTED = "UNSUPPORTED"


# Explicit lookup table for all supported platform+format combinations (D-11).
# Keyed on (PLATFORM_UPPER, FORMAT_UPPER). CAROUSEL is handled as a pre-check
# before this table is consulted.
_ENDPOINT_TYPE_LOOKUP: dict[tuple[str, str], ScoringEndpointType] = {
    ("META", "VIDEO"):       ScoringEndpointType.VIDEO,
    ("META", "IMAGE"):       ScoringEndpointType.STATIC_IMAGE,
    ("TIKTOK", "VIDEO"):     ScoringEndpointType.VIDEO,
    ("TIKTOK", "IMAGE"):     ScoringEndpointType.UNSUPPORTED,
    ("GOOGLE_ADS", "VIDEO"): ScoringEndpointType.VIDEO,
    ("GOOGLE_ADS", "IMAGE"): ScoringEndpointType.UNSUPPORTED,
    ("DV360", "VIDEO"):      ScoringEndpointType.VIDEO,
    ("DV360", "IMAGE"):      ScoringEndpointType.UNSUPPORTED,
}


def get_endpoint_type(
    platform: Optional[str],
    asset_format: Optional[str],
) -> ScoringEndpointType:
    """Return the ScoringEndpointType for a given platform + asset_format combination.

    Inputs are normalized to uppercase before lookup — case insensitive.
    None values are treated as empty strings and resolve to UNSUPPORTED.

    CAROUSEL assets always return UNSUPPORTED regardless of platform.
    Any platform+format combination not in the lookup table returns UNSUPPORTED.

    Args:
        platform:     Platform identifier (e.g. "META", "TIKTOK", "GOOGLE_ADS", "DV360").
        asset_format: Asset format identifier (e.g. "VIDEO", "IMAGE", "CAROUSEL").

    Returns:
        ScoringEndpointType enum value.
    """
    format_upper = (asset_format or "").upper()

    # CAROUSEL is always UNSUPPORTED regardless of platform (D-11)
    if format_upper == "CAROUSEL":
        return ScoringEndpointType.UNSUPPORTED

    platform_upper = (platform or "").upper()
    key = (platform_upper, format_upper)
    return _ENDPOINT_TYPE_LOOKUP.get(key, ScoringEndpointType.UNSUPPORTED)
