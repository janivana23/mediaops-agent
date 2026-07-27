"""Second real provider: image generation via OpenAI's Images API directly
(not through OpenRouter) — a distinct real path so the failover chain has
two independent real providers before ever touching the local mock.

Uses `POST /v1/images/generations` with a real `size` enum, unlike the
OpenRouter/Gemini chat-completions path which takes resolution as free
text in the prompt. OpenAI's image models don't support every size in
this project's own resolution ladder (512x512 / 1024x1024 / 2048x2048) —
there's no 512 or 2048 square option — so requests are mapped to the
nearest size OpenAI actually accepts (_SIZE_MAP below). The job is still
billed at this app's own per-resolution rate (app/costs.py); that's an
internal pricing model, not a pass-through of OpenAI's invoice, same as
the other providers.

Confirm the current model name at https://platform.openai.com/docs/models
before relying on this — image model names and pricing move.
"""
from __future__ import annotations

import base64
import time

import requests

from app import config
from app.providers.base import GenerationResult, ProviderError
from app.qa import seed_from_reference

NAME = "openai-images"

_SIZE_MAP = {
    "512x512": "1024x1024",
    "1024x1024": "1024x1024",
    "2048x2048": "1024x1024",
}


def generate(
    *,
    prompt: str,
    reference_image_path: str | None,
    resolution: str,
    kind: str,
    job_id: str,
) -> GenerationResult:
    if not config.OPENAI_API_KEY:
        raise ProviderError("OPENAI_API_KEY not set")
    if kind == "video":
        raise ProviderError("openai-images does not support kind=video")

    size = _SIZE_MAP.get(resolution, "1024x1024")
    full_prompt = f"{prompt} — on-brand marketing asset"
    try:
        resp = requests.post(
            f"{config.OPENAI_BASE_URL}/images/generations",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json={
                "model": config.OPENAI_IMAGE_MODEL,
                "prompt": full_prompt,
                "size": size,
                "n": 1,
            },
            timeout=config.PROVIDER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ProviderError(f"openai request failed: {exc}") from exc

    if resp.status_code != 200:
        raise ProviderError(f"openai returned {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
        raw = base64.b64decode(b64)
    except (KeyError, IndexError, ValueError) as exc:
        raise ProviderError(f"unexpected openai response shape: {exc}") from exc

    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    out_path = job_dir / "image.png"
    out_path.write_bytes(raw)

    seed = seed_from_reference(reference_image_path, prompt) ^ int(time.time())
    return GenerationResult(output_path=out_path, provider_name=NAME, seed=seed)
