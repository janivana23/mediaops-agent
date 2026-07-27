from __future__ import annotations

import base64

import pytest
import requests

from app import config
from app.providers import openai_images
from app.providers.base import ProviderError


def test_missing_key_raises_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY not set"):
        openai_images.generate(
            prompt="p", reference_image_path=None, resolution="1024x1024", kind="image", job_id="job1"
        )


def test_video_kind_raises_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    with pytest.raises(ProviderError, match="does not support kind=video"):
        openai_images.generate(
            prompt="p", reference_image_path=None, resolution="1024x1024", kind="video", job_id="job1"
        )


def test_non_200_response_raises_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")

    class FakeResp:
        status_code = 402
        text = '{"error":"insufficient_quota"}'

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(ProviderError, match="openai returned 402"):
        openai_images.generate(
            prompt="p", reference_image_path=None, resolution="1024x1024", kind="image", job_id="job1"
        )


def test_successful_generation_writes_image_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")

    fake_png_bytes = b"\x89PNG\r\n\x1a\nnot a real png but bytes are bytes"
    b64 = base64.b64encode(fake_png_bytes).decode()

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [{"b64_json": b64}]}

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)

    result = openai_images.generate(
        prompt="a cheerful mascot", reference_image_path=None, resolution="2048x2048", kind="image", job_id="job1"
    )

    assert result.provider_name == "openai-images"
    assert result.output_path.read_bytes() == fake_png_bytes
    assert captured["url"].endswith("/images/generations")
    # 2048x2048 isn't a real OpenAI size — mapped down to the nearest one.
    assert captured["json"]["size"] == "1024x1024"


def test_unexpected_response_shape_raises_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"unexpected": "shape"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(ProviderError, match="unexpected openai response shape"):
        openai_images.generate(
            prompt="p", reference_image_path=None, resolution="1024x1024", kind="image", job_id="job1"
        )
