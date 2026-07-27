from __future__ import annotations

from app.providers import gemini_openrouter, mock_seedance, openai_images

REGISTRY = {
    gemini_openrouter.NAME: gemini_openrouter,
    openai_images.NAME: openai_images,
    mock_seedance.NAME: mock_seedance,
}
