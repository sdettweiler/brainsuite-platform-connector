"""
Dummy ACE Score generator.
Replace with real Brainsuite API integration when available.
"""
import random
from datetime import datetime
from typing import Optional


SCORE_RANGES = {
    "VIDEO": {"min": 40, "max": 85, "mean": 65},
    "IMAGE": {"min": 30, "max": 75, "mean": 55},
    "CAROUSEL": {"min": 35, "max": 78, "mean": 58},
    "default": {"min": 20, "max": 80, "mean": 50},
}

DUMMY_BRAINSUITE_KPIS = {
    "attention_score": {"min": 20, "max": 95},
    "brand_score": {"min": 30, "max": 90},
    "emotion_score": {"min": 25, "max": 88},
    "message_clarity": {"min": 35, "max": 92},
    "visual_impact": {"min": 40, "max": 95},
}


def generate_ace_score(asset_format: Optional[str] = None) -> dict:
    """Generate a dummy ACE score for a creative asset."""
    fmt = (asset_format or "default").upper()
    rng = SCORE_RANGES.get(fmt, SCORE_RANGES["default"])

    score = round(random.uniform(rng["min"], rng["max"]), 1)
    confidence = (
        "high" if score > 65
        else "medium" if score > 45
        else "low"
    )

    brainsuite_kpis = {
        k: round(random.uniform(v["min"], v["max"]), 1)
        for k, v in DUMMY_BRAINSUITE_KPIS.items()
    }

    return {
        "ace_score": score,
        "ace_score_confidence": confidence,
        "brainsuite_metadata": {
            **brainsuite_kpis,
            "generated_at": datetime.utcnow().isoformat(),
            "is_dummy": True,
        },
    }


def get_performer_tag(
    ace_score: Optional[float],
    spend: Optional[float],
    roas: Optional[float],
) -> str:
    """Classify asset performance relative to its peers."""
    if ace_score is None:
        return "Average"
    if ace_score >= 70:
        return "Top Performer"
    if ace_score >= 45:
        return "Average"
    return "Below Average"


def get_score_color(score: Optional[float]) -> str:
    """Return color class for ACE score badge."""
    if score is None:
        return "neutral"
    if score >= 70:
        return "success"
    if score >= 45:
        return "warning"
    return "error"
