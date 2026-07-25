from __future__ import annotations

from app.providers import gemini_openrouter, mock_seedance

REGISTRY = {
    gemini_openrouter.NAME: gemini_openrouter,
    mock_seedance.NAME: mock_seedance,
}
