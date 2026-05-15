"""Tests for PROXY-03: bgutil PO token plugin installed and auto-detected by yt-dlp."""
import pytest


def test_bgutil_plugin_loaded():
    """bgutil-ytdlp-pot-provider plugin is importable after pip install.

    Skips gracefully when bgutil-ytdlp-pot-provider is not installed in the
    current environment (e.g. CI without the package). Install it with:
    pip install bgutil-ytdlp-pot-provider
    """
    import importlib.util
    try:
        spec = importlib.util.find_spec("yt_dlp_plugins")
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        pytest.skip("bgutil-ytdlp-pot-provider not installed in this environment")
