from __future__ import annotations

import base64

import pytest
import requests

from app import config
from app.providers import gemini_openrouter
from app.providers.base import ProviderError


def _ok_response(monkeypatch, captured: dict):
    png = b"\x89PNG\r\n\x1a\npretend pixels"
    uri = "data:image/png;base64," + base64.b64encode(png).decode()

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"images": [{"image_url": {"url": uri}}]}}]}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)
    return png


def test_missing_key_raises_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY not set"):
        gemini_openrouter.generate(
            prompt="p", reference_image_path=None, resolution="1024x1024", kind="image", job_id="j1"
        )


def test_request_caps_max_tokens(tmp_path, monkeypatch):
    """OpenRouter pre-authorises max_tokens worth of credit before generating.

    Omitting it makes them reserve the model's full context ceiling, which
    402s on a low-balance account even though one image only costs ~1290
    completion tokens. Regression test for exactly that 402.
    """
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(config, "OPENROUTER_MAX_TOKENS", 2000)
    captured: dict = {}
    png = _ok_response(monkeypatch, captured)

    result = gemini_openrouter.generate(
        prompt="mascot", reference_image_path=None, resolution="1024x1024", kind="image", job_id="j1"
    )

    assert captured["json"]["max_tokens"] == 2000
    assert captured["json"]["modalities"] == ["image", "text"]
    assert result.provider_name == "gemini-openrouter"
    assert result.output_path.read_bytes() == png


def test_timeout_is_generous_enough_for_image_generation(tmp_path, monkeypatch):
    """A too-short timeout is indistinguishable from a dead provider: the
    request raises, the chain fails over, and the job silently comes from the
    mock. Image generation measured well over the old 20s default."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-test")
    captured: dict = {}
    _ok_response(monkeypatch, captured)

    gemini_openrouter.generate(
        prompt="p", reference_image_path=None, resolution="512x512", kind="image", job_id="j2"
    )
    assert captured["timeout"] >= 60


def test_402_surfaces_the_credit_message(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-test")

    class FakeResp:
        status_code = 402
        text = '{"error":{"message":"This request requires more credits"}}'

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(ProviderError, match="openrouter returned 402.*more credits"):
        gemini_openrouter.generate(
            prompt="p", reference_image_path=None, resolution="512x512", kind="image", job_id="j3"
        )
