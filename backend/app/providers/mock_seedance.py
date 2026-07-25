"""Local stand-in for a second frontier provider (e.g. Seedance 2.0 via
BytePlus). No network call — always available, which is the point: it's
the bottom of the failover chain.

Reference-anchored by construction, not just by seed: when a reference
image is supplied, its actual pixels are composited into the output (not
just hashed into a random-number seed), so the result is genuinely more
similar — under the aHash-based identity-consistency check in app.qa — to
*that* reference than to an unrelated one. That's what makes the QA gate
meaningful in a demo with no real character-consistency model underneath
it: swap this module for a real Seedance/Gemini call and the QA gate
doesn't change, because it was never trusting the generator's self-report.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app import config
from app.providers.base import GenerationResult, ProviderError
from app.qa import seed_from_reference

NAME = "mock-seedance"


def _keyframe(
    size: tuple[int, int], seed: int, label: str, reference_image_path: str | None
) -> Image.Image:
    rng = random.Random(seed)
    w, h = size

    if reference_image_path and Path(reference_image_path).exists():
        # Anchor the composition on the reference itself, softened by a
        # colour-graded overlay so different prompts against the same
        # reference still look like variations, not identical copies.
        with Image.open(reference_image_path) as ref:
            base = ref.convert("RGB").resize((w, h), Image.LANCZOS)
        tint = Image.new("RGB", size, tuple(rng.randint(60, 200) for _ in range(3)))
        img = Image.blend(base, tint, alpha=0.25)
    else:
        top = tuple(rng.randint(20, 235) for _ in range(3))
        bottom = tuple(rng.randint(20, 235) for _ in range(3))
        img = Image.new("RGB", size)
        gdraw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(h - 1, 1)
            row = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            gdraw.line([(0, y), (w, y)], fill=row)

    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 6)):
        r = rng.randint(w // 24, w // 10)
        cx, cy = rng.randint(0, w), rng.randint(0, h)
        color = tuple(rng.randint(0, 255) for _ in range(3))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=max(2, w // 200))

    caption = label[:60]
    draw.rectangle([0, h - 28, w, h], fill=(0, 0, 0))
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((8, h - 22), caption, fill=(255, 255, 255), font=font)
    return img


def generate(
    *,
    prompt: str,
    reference_image_path: str | None,
    resolution: str,
    kind: str,
    job_id: str,
) -> GenerationResult:
    try:
        w, h = (int(x) for x in resolution.split("x"))
    except ValueError as exc:
        raise ProviderError(f"invalid resolution {resolution!r}") from exc

    seed = seed_from_reference(reference_image_path, prompt)
    job_dir = config.OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    if kind == "video":
        # No real video model behind this demo — we render a 3-keyframe
        # contact sheet standing in for a multi-shot storyboard draft.
        frames = [
            _keyframe((w, h), seed + i * 97, f"{prompt} — shot {i + 1}/3", reference_image_path)
            for i in range(3)
        ]
        sheet = Image.new("RGB", (w * 3, h))
        for i, frame in enumerate(frames):
            sheet.paste(frame, (i * w, 0))
        out_path = job_dir / "keyframes.png"
        sheet.save(out_path)
    else:
        out_path = job_dir / "image.png"
        _keyframe((w, h), seed, prompt, reference_image_path).save(out_path)

    return GenerationResult(output_path=out_path, provider_name=NAME, seed=seed)
