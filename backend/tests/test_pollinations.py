from __future__ import annotations

import io

import pytest
import requests
from PIL import Image

from app import config
from app.providers import pollinations
from app.providers.base import ProviderError


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 80, 160)).save(buf, format="PNG")
    return buf.getvalue()


class _Resp:
    def __init__(self, content: bytes, status_code: int = 200, text: str = ""):
        self.content = content
        self.status_code = status_code
        self.text = text


@pytest.fixture(autouse=True)
def _enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "POLLINATIONS_ENABLED", True)


def _generate(**overrides):
    kwargs = dict(
        prompt="a cheerful mascot",
        reference_image_path=None,
        resolution="512x512",
        kind="image",
        job_id="job1",
    )
    kwargs.update(overrides)
    return pollinations.generate(**kwargs)


def test_disabled_raises_provider_error(monkeypatch):
    monkeypatch.setattr(config, "POLLINATIONS_ENABLED", False)
    with pytest.raises(ProviderError, match="pollinations disabled"):
        _generate()


def test_video_kind_raises_provider_error():
    with pytest.raises(ProviderError, match="does not support kind=video"):
        _generate(kind="video")


def test_invalid_resolution_raises_provider_error():
    with pytest.raises(ProviderError, match="invalid resolution"):
        _generate(resolution="enormous")


def test_non_200_raises_provider_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(b"", 503, "upstream busy"))
    with pytest.raises(ProviderError, match="pollinations returned 503"):
        _generate()


def test_html_error_page_with_200_is_rejected(monkeypatch):
    """The upstream serves error pages with a 200 when overloaded, so a
    success status alone must not be treated as proof of an image."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(b"<html>error</html>"))
    with pytest.raises(ProviderError, match="non-image data"):
        _generate()


def test_native_size_recorded_when_provider_renders_smaller(monkeypatch):
    """The free tier caps at 768 — asking for 1024 returns 768. The result
    must be upscaled to the requested size AND disclose the native size, so
    the job never claims detail the pixels don't carry."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(_png_bytes(768, 768)))

    result = _generate(resolution="1024x1024")

    assert result.native_size == "768x768"
    with Image.open(result.output_path) as im:
        assert im.size == (1024, 1024)


def test_native_size_is_none_when_size_matches(monkeypatch):
    """No upscale note should appear on a job the provider served natively."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(_png_bytes(512, 512)))

    result = _generate(resolution="512x512")

    assert result.native_size == "512x512"
    with Image.open(result.output_path) as im:
        assert im.size == (512, 512)


def test_request_never_asks_above_the_native_cap(monkeypatch):
    """Requesting more than the cap wastes upstream time and returns 768
    anyway, so the outbound URL should be clamped."""
    captured = {}

    def fake_get(url, timeout):
        captured["url"] = url
        return _Resp(_png_bytes(768, 768))

    monkeypatch.setattr(requests, "get", fake_get)
    _generate(resolution="2048x2048")

    assert f"width={pollinations.NATIVE_MAX_PX}" in captured["url"]
    assert "width=2048" not in captured["url"]


def test_timeout_raises_provider_error(monkeypatch):
    def boom(*a, **k):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(ProviderError, match="pollinations request failed"):
        _generate()
