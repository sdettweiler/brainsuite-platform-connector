"""
Phase 5 — BrainSuite Image Scoring: ScoringEndpointType lookup table tests.

Tests the get_endpoint_type() function and ScoringEndpointType enum from
app.services.scoring_endpoint_type.

Covers all 9 platform/format combinations from the D-11 decision table:
  META+VIDEO → VIDEO
  META+IMAGE → STATIC_IMAGE
  TIKTOK+VIDEO → VIDEO
  TIKTOK+IMAGE → UNSUPPORTED
  GOOGLE_ADS+VIDEO → VIDEO
  GOOGLE_ADS+IMAGE → UNSUPPORTED
  DV360+VIDEO → VIDEO
  DV360+IMAGE → UNSUPPORTED
  any+CAROUSEL → UNSUPPORTED

Plus edge cases: unknown platform, case insensitivity, None handling.
"""
import pytest
from app.services.scoring_endpoint_type import ScoringEndpointType, get_endpoint_type


# ---------------------------------------------------------------------------
# ScoringEndpointType enum values
# ---------------------------------------------------------------------------


def test_endpoint_type_enum_values():
    """ScoringEndpointType enum has VIDEO, STATIC_IMAGE, UNSUPPORTED values."""
    assert ScoringEndpointType.VIDEO == "VIDEO"
    assert ScoringEndpointType.STATIC_IMAGE == "STATIC_IMAGE"
    assert ScoringEndpointType.UNSUPPORTED == "UNSUPPORTED"


# ---------------------------------------------------------------------------
# D-11 lookup table: all 8 explicit platform+format combinations
# ---------------------------------------------------------------------------


def test_endpoint_type_video_meta():
    """META + VIDEO → VIDEO endpoint."""
    assert get_endpoint_type("META", "VIDEO") == ScoringEndpointType.VIDEO


def test_endpoint_type_static_image_meta():
    """META + IMAGE → STATIC_IMAGE endpoint."""
    assert get_endpoint_type("META", "IMAGE") == ScoringEndpointType.STATIC_IMAGE


def test_endpoint_type_video_tiktok():
    """TIKTOK + VIDEO → VIDEO endpoint."""
    assert get_endpoint_type("TIKTOK", "VIDEO") == ScoringEndpointType.VIDEO


def test_endpoint_type_unsupported_tiktok_image():
    """TIKTOK + IMAGE → UNSUPPORTED (Static API does not support TikTok)."""
    assert get_endpoint_type("TIKTOK", "IMAGE") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_video_google_ads():
    """GOOGLE_ADS + VIDEO → VIDEO endpoint."""
    assert get_endpoint_type("GOOGLE_ADS", "VIDEO") == ScoringEndpointType.VIDEO


def test_endpoint_type_unsupported_google_image():
    """GOOGLE_ADS + IMAGE → UNSUPPORTED."""
    assert get_endpoint_type("GOOGLE_ADS", "IMAGE") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_video_dv360():
    """DV360 + VIDEO → VIDEO endpoint."""
    assert get_endpoint_type("DV360", "VIDEO") == ScoringEndpointType.VIDEO


def test_endpoint_type_unsupported_dv360_image():
    """DV360 + IMAGE → UNSUPPORTED."""
    assert get_endpoint_type("DV360", "IMAGE") == ScoringEndpointType.UNSUPPORTED


# ---------------------------------------------------------------------------
# CAROUSEL always UNSUPPORTED (any platform)
# ---------------------------------------------------------------------------


def test_endpoint_type_carousel_always_unsupported():
    """CAROUSEL assets are UNSUPPORTED regardless of platform."""
    assert get_endpoint_type("META", "CAROUSEL") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_carousel_tiktok_unsupported():
    """TIKTOK + CAROUSEL → UNSUPPORTED."""
    assert get_endpoint_type("TIKTOK", "CAROUSEL") == ScoringEndpointType.UNSUPPORTED


# ---------------------------------------------------------------------------
# Edge cases: unknown platform, case insensitivity, None handling
# ---------------------------------------------------------------------------


def test_endpoint_type_unknown_defaults_unsupported():
    """Unknown platform defaults to UNSUPPORTED."""
    assert get_endpoint_type("UNKNOWN", "IMAGE") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_unknown_platform_video_unsupported():
    """Unknown platform + VIDEO defaults to UNSUPPORTED (not in lookup table)."""
    assert get_endpoint_type("SNAPCHAT", "VIDEO") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_case_insensitive():
    """Lookup is case insensitive — lowercase inputs work correctly."""
    assert get_endpoint_type("meta", "image") == ScoringEndpointType.STATIC_IMAGE


def test_endpoint_type_case_insensitive_video():
    """Lowercase platform+format for video works correctly."""
    assert get_endpoint_type("meta", "video") == ScoringEndpointType.VIDEO


def test_endpoint_type_mixed_case():
    """Mixed case inputs are normalized correctly."""
    assert get_endpoint_type("Meta", "Image") == ScoringEndpointType.STATIC_IMAGE


def test_endpoint_type_none_handling():
    """None platform and format returns UNSUPPORTED (safe default)."""
    assert get_endpoint_type(None, None) == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_none_platform():
    """None platform returns UNSUPPORTED."""
    assert get_endpoint_type(None, "VIDEO") == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_none_format():
    """None format returns UNSUPPORTED."""
    assert get_endpoint_type("META", None) == ScoringEndpointType.UNSUPPORTED


def test_endpoint_type_empty_strings():
    """Empty string platform and format returns UNSUPPORTED."""
    assert get_endpoint_type("", "") == ScoringEndpointType.UNSUPPORTED


# ---------------------------------------------------------------------------
# Phase 5 Plan 02: build_static_scoring_payload + map_static_channel tests
# ---------------------------------------------------------------------------

from app.services.brainsuite_static_score import build_static_scoring_payload, map_static_channel


def test_static_announce_payload_basic():
    """build_static_scoring_payload for META/facebook_feed produces correct structure."""
    result = build_static_scoring_payload("img.jpg", "META", "facebook_feed", {})
    assert result["input"]["channel"] == "Facebook"
    legs = result["input"]["legs"]
    assert len(legs) == 1
    assert legs[0]["staticImage"]["assetId"] == "leg1"


def test_static_announce_payload_instagram():
    """META + instagram_stories placement maps to Instagram channel."""
    result = build_static_scoring_payload("img.jpg", "META", "instagram_stories", {})
    assert result["input"]["channel"] == "Instagram"


def test_static_announce_payload_intended_messages():
    """brainsuite_intended_messages are split into list and intendedMessagesLanguage is set."""
    metadata = {"brainsuite_intended_messages": "msg1\nmsg2"}
    result = build_static_scoring_payload("img.jpg", "META", "facebook_feed", metadata)
    assert result["input"]["intendedMessages"] == ["msg1", "msg2"]
    assert "intendedMessagesLanguage" in result["input"]


def test_static_announce_payload_no_brand_values():
    """build_static_scoring_payload output never contains brandValues key."""
    result = build_static_scoring_payload("img.jpg", "META", "facebook_feed", {})
    assert "brandValues" not in str(result)


def test_static_announce_payload_no_aoi():
    """build_static_scoring_payload output never contains areasOfInterest key."""
    result = build_static_scoring_payload("img.jpg", "META", "facebook_feed", {})
    assert "areasOfInterest" not in str(result)


def test_map_static_channel_meta_facebook():
    """META + facebook_feed maps to Facebook."""
    assert map_static_channel("META", "facebook_feed") == "Facebook"


def test_map_static_channel_meta_instagram():
    """META + instagram_stories maps to Instagram."""
    assert map_static_channel("META", "instagram_stories") == "Instagram"


def test_map_static_channel_non_meta_fallback():
    """Non-META platform falls back to Facebook."""
    assert map_static_channel("TIKTOK", None) == "Facebook"
