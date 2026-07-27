"""Per-provider, per-resolution cost table (USD cents).

Kept as plain data so the founder-facing rule ("what does a 2048px asset
cost from provider X") is one glance, not buried in provider code.
"""
from __future__ import annotations

COST_TABLE_CENTS: dict[str, dict[str, int]] = {
    "gemini-openrouter": {
        "512x512": 25,
        "1024x1024": 50,
        "2048x2048": 150,
        "video": 300,
    },
    "openai-images": {
        "512x512": 20,
        "1024x1024": 45,
        "2048x2048": 135,
        "video": 300,
    },
    "mock-seedance": {
        "512x512": 20,
        "1024x1024": 40,
        "2048x2048": 120,
        "video": 250,
    },
}

# Two real providers before ever touching the local mock.
PROVIDER_ORDER = ["gemini-openrouter", "openai-images", "mock-seedance"]


def cost_for(provider: str, kind: str, resolution: str) -> int:
    table = COST_TABLE_CENTS[provider]
    key = "video" if kind == "video" else resolution
    return table[key]


def cheapest_provider_for(kind: str, resolution: str) -> str:
    return min(PROVIDER_ORDER, key=lambda p: cost_for(p, kind, resolution))
