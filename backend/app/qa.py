"""QA tooling: identity consistency + brand compliance scoring.

Both scores are computed from pixels, not asserted by the generator, so a
provider can't self-report a good result — the same gate would run against
a real Seedance/Gemini output.

Identity consistency uses a simple average-hash (aHash) perceptual hash
compared via Hamming distance. It's a coarse proxy for "does this look like
the same character/subject as the reference" — good enough to catch a
generator that drifted wildly, not a substitute for an embedding-based face
match in production (see README).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from app import config

HASH_SIZE = 8  # 64-bit hash


def average_hash(image: Image.Image, hash_size: int = HASH_SIZE) -> int:
    gray = image.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= mean else 0)
    return bits


def hamming_distance(a: int, b: int, bits: int = HASH_SIZE * HASH_SIZE) -> int:
    return bin(a ^ b).count("1")


def seed_from_reference(reference_image_path: str | None, fallback_text: str) -> int:
    """Deterministic seed: derived from the reference image's perceptual
    hash when one is supplied, so the mock generator reliably produces a
    visually consistent output for the same reference — otherwise derived
    from the prompt text so repeat prompts still look the same."""
    if reference_image_path and Path(reference_image_path).exists():
        with Image.open(reference_image_path) as img:
            return average_hash(img)
    digest = hashlib.sha256(fallback_text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def identity_similarity(reference_image_path: str, generated_image_path: str) -> float:
    """0-100: 100 = identical hash, 0 = maximally different."""
    with Image.open(reference_image_path) as ref, Image.open(generated_image_path) as gen:
        ref_hash = average_hash(ref)
        gen_hash = average_hash(gen)
    dist = hamming_distance(ref_hash, gen_hash)
    bits = HASH_SIZE * HASH_SIZE
    return round(100 * (1 - dist / bits), 1)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def brand_compliance_score(
    generated_image_path: str, palette_hex: list[str] | None = None
) -> float:
    """0-100: how close the image's average colour sits to the nearest
    brand palette colour. A real deployment would swap this for a proper
    CLIP/colour-histogram brand-safety model; the interface stays the same."""
    palette = palette_hex or config.BRAND_PALETTE_HEX
    with Image.open(generated_image_path) as img:
        small = img.convert("RGB").resize((32, 32))
        pixels = list(small.getdata())
    n = len(pixels)
    avg = tuple(sum(c[i] for c in pixels) / n for i in range(3))

    max_dist = (255**2 * 3) ** 0.5
    best = min(
        sum((avg[i] - _hex_to_rgb(hexc)[i]) ** 2 for i in range(3)) ** 0.5
        for hexc in palette
    )
    return round(100 * (1 - best / max_dist), 1)
