"""Keyless real-image provider: Pollinations.

Exists because every other real provider in the chain is gated behind a
funded account, and a demo that can only ever show `mock-seedance` fails to
demonstrate the thing this project is actually about — that the guardrails
sit around a *real* generation call. This provider needs no API key and no
billing, so the failover chain reaches a genuine model out of the box.

Two honesty constraints drive the shape of this module:

1. The upstream silently caps output at 768x768. Ask for 1024 or 2048 and
   you get 768 back with a 200 and no warning. Returning that unchanged
   would mean a job row reading "2048x2048" next to a file that is nothing
   of the sort — precisely the self-reported-success problem the QA gate
   exists to catch. So we measure what actually came back and upscale to
   the requested size explicitly, recording the native size on the result.
2. Being free, it is best-effort infrastructure: no SLA, and it will
   occasionally time out or return an HTML error page with a 200. Every
   failure path raises ProviderError so the chain falls through to the
   mock rather than surfacing a broken asset.
"""
from __future__ import annotations

import io
import time
import urllib.parse

import requests
from PIL import Image

from app import config
from app.providers.base import GenerationResult, ProviderError
from app.qa import seed_from_reference

NAME = "pollinations"

# Measured, not documented: the free tier renders at most 768x768 regardless
# of the width/height asked for. Anything above this is upscaled locally.
NATIVE_MAX_PX = 768


def generate(
    *,
    prompt: str,
    reference_image_path: str | None,
    resolution: str,
    kind: str,
    job_id: str,
) -> GenerationResult:
    if not config.POLLINATIONS_ENABLED:
        raise ProviderError("pollinations disabled")
    if kind == "video":
        raise ProviderError("pollinations does not support kind=video")

    try:
        width, height = (int(part) for part in resolution.lower().split("x"))
    except ValueError as exc:
        raise ProviderError(f"invalid resolution {resolution!r}") from exc

    # Ask for no more than the upstream can actually render; we handle the
    # gap to the requested size ourselves, below, where it's visible.
    req_w = min(width, NATIVE_MAX_PX)
    req_h = min(height, NATIVE_MAX_PX)

    # A stable seed keeps a re-run of the same job reproducible, which is
    # what makes the identity-consistency score meaningful across retries.
    seed = seed_from_reference(reference_image_path, prompt)

    url = (
        f"{config.POLLINATIONS_BASE_URL}/prompt/"
        f"{urllib.parse.quote(f'{prompt} — on-brand marketing asset')}"
        f"?width={req_w}&height={req_h}&seed={seed % 2**31}&nologo=true"
    )

    try:
        resp = requests.get(url, timeout=config.PROVIDER_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise ProviderError(f"pollinations request failed: {exc}") from exc

    if resp.status_code != 200:
        raise ProviderError(f"pollinations returned {resp.status_code}: {resp.text[:200]}")

    # A 200 is not proof of an image — the service returns HTML error pages
    # with a 200 when it is overloaded, so validate by decoding the bytes.
    try:
        image = Image.open(io.BytesIO(resp.content))
        image.load()
    except Exception as exc:
        raise ProviderError(f"pollinations returned non-image data: {exc}") from exc

    native_w, native_h = image.size
    if (native_w, native_h) != (width, height):
        image = image.convert("RGB").resize((width, height), Image.LANCZOS)

    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    out_path = job_dir / "image.png"
    image.convert("RGB").save(out_path, format="PNG")

    return GenerationResult(
        output_path=out_path,
        provider_name=NAME,
        seed=seed ^ int(time.time()),
        native_size=f"{native_w}x{native_h}",
    )
