"""Primary provider: real image generation via Gemini on OpenRouter.

Uses the chat-completions endpoint with `modalities: ["image", "text"]`,
which is how OpenRouter surfaces image-output models — the response carries
the image as a base64 data URI on `choices[0].message.images[0]`. Confirm
the current model slug at https://openrouter.ai/models before relying on
this in a real deployment; provider catalogs move.

Deliberately raises ProviderError (never lets exceptions leak) on every
failure mode — missing key, timeout, non-2xx, malformed response — so
`service.run_job` can fail over to the next provider without special-casing
each error type.
"""
from __future__ import annotations

import base64
import time

import requests

from app import config
from app.providers.base import GenerationResult, ProviderError
from app.qa import seed_from_reference

NAME = "gemini-openrouter"


def generate(
    *,
    prompt: str,
    reference_image_path: str | None,
    resolution: str,
    kind: str,
    job_id: str,
) -> GenerationResult:
    if not config.OPENROUTER_API_KEY:
        raise ProviderError("OPENROUTER_API_KEY not set")
    if kind == "video":
        # No video-output model on this path yet — force failover to the
        # keyframe-storyboard fallback rather than silently degrading.
        raise ProviderError("gemini-openrouter does not support kind=video")

    full_prompt = f"{prompt} — {resolution}, on-brand marketing asset"
    try:
        resp = requests.post(
            f"{config.OPENROUTER_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
            json={
                "model": config.OPENROUTER_IMAGE_MODEL,
                "messages": [{"role": "user", "content": full_prompt}],
                "modalities": ["image", "text"],
            },
            timeout=config.PROVIDER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ProviderError(f"openrouter request failed: {exc}") from exc

    if resp.status_code != 200:
        raise ProviderError(f"openrouter returned {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
        images = data["choices"][0]["message"]["images"]
        data_uri = images[0]["image_url"]["url"]
        _, b64 = data_uri.split(",", 1)
        raw = base64.b64decode(b64)
    except (KeyError, IndexError, ValueError) as exc:
        raise ProviderError(f"unexpected openrouter response shape: {exc}") from exc

    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    out_path = job_dir / "image.png"
    out_path.write_bytes(raw)

    seed = seed_from_reference(reference_image_path, prompt) ^ int(time.time())
    return GenerationResult(output_path=out_path, provider_name=NAME, seed=seed)
