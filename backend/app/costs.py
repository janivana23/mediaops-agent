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
    # Free and keyless, so the billed rate is zero. It still sits in the cost
    # table because every other part of the system (budget check, approval
    # threshold, ledger) reads costs from here and must not special-case it.
    "pollinations": {
        "512x512": 0,
        "1024x1024": 0,
        "2048x2048": 0,
        "video": 0,
    },
    "mock-seedance": {
        "512x512": 20,
        "1024x1024": 40,
        "2048x2048": 120,
        "video": 250,
    },
}

# Paid providers first (better quality), then the free keyless one, and only
# then the local mock. Ordering is deliberately *not* cheapest-first: the
# mock is a last-resort placeholder, not a budget option, so it must stay at
# the end even though `pollinations` now undercuts it on price.
PROVIDER_ORDER = ["gemini-openrouter", "openai-images", "pollinations", "mock-seedance"]


def cost_for(provider: str, kind: str, resolution: str) -> int:
    table = COST_TABLE_CENTS[provider]
    key = "video" if kind == "video" else resolution
    return table[key]


def cheapest_provider_for(kind: str, resolution: str) -> str:
    return min(PROVIDER_ORDER, key=lambda p: cost_for(p, kind, resolution))
