"""Tests for PROXY-03: bgutil PO token plugin installed and auto-detected by yt-dlp."""
import pytest


def test_bgutil_plugin_loaded():
    """bgutil-ytdlp-pot-provider plugin is importable after pip install.

    Fails until bgutil-ytdlp-pot-provider is installed (Task 2 adds it to requirements.txt;
    test environment requires `pip install bgutil-ytdlp-pot-provider` to pass).
    """
    import importlib.util
    spec = importlib.util.find_spec("yt_dlp_plugins")
    assert spec is not None, (
        "yt_dlp_plugins namespace not found — bgutil-ytdlp-pot-provider may not be installed. "
        "Run: pip install bgutil-ytdlp-pot-provider"
    )
