"""Runtime configuration, all overridable via environment variables.

Defaults are tuned for zero-config local demo (SQLite, mock provider only).
Set OPENROUTER_API_KEY to exercise the real provider + failover path.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'mediaops.db'}")

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", BASE_DIR / "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Provider chain -------------------------------------------------------
# Primary is a real API call (OpenRouter -> Gemini image model). Secondary is
# a deterministic local mock standing in for a second frontier provider
# (e.g. Seedance 2.0 via BytePlus). The service tries providers in order and
# fails over on any error (missing key, timeout, non-2xx, rate limit).
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# Verify the current slug on https://openrouter.ai/models — image-gen model
# ids on OpenRouter change as providers cycle previews in/out.
OPENROUTER_IMAGE_MODEL = os.environ.get(
    "OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image-preview"
)
PROVIDER_TIMEOUT_SECONDS = float(os.environ.get("PROVIDER_TIMEOUT_SECONDS", "20"))

# --- Business rules (the part an agent is not allowed to talk its way around)
# Jobs costing more than this are never auto-generated, regardless of
# remaining budget — they always create an ApprovalRequest instead.
AUTO_APPROVE_THRESHOLD_CENTS = int(os.environ.get("AUTO_APPROVE_THRESHOLD_CENTS", "100"))

# If the requested resolution would exceed remaining budget, the service
# steps down resolution automatically before generating rather than failing
# outright (cost-aware generation / resolution strategy).
RESOLUTION_LADDER = ["2048x2048", "1024x1024", "512x512"]

# --- QA thresholds ---------------------------------------------------------
# Perceptual-hash similarity (0-100) a generated asset must clear against its
# reference image before it's marked deliverable rather than qa_failed.
QA_IDENTITY_THRESHOLD = float(os.environ.get("QA_IDENTITY_THRESHOLD", "70"))
# Colour-distance-based brand compliance score (0-100).
QA_BRAND_THRESHOLD = float(os.environ.get("QA_BRAND_THRESHOLD", "60"))
BRAND_PALETTE_HEX = os.environ.get(
    "BRAND_PALETTE_HEX", "#1F6FEB,#0D1117,#F0F6FC"
).split(",")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
