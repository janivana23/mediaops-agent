from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProviderError(Exception):
    """Raised on any failure that should trigger failover to the next
    provider in the chain (missing key, timeout, bad response, rate limit)."""


@dataclass
class GenerationResult:
    output_path: Path
    provider_name: str
    seed: int
    # Set only when the provider rendered at a different size than requested
    # and upscaled to meet it (e.g. a free tier that caps resolution). The
    # service records this on the job so the delivered resolution is never
    # a claim the pixels can't back up.
    native_size: str | None = None


class Provider(Protocol):
    name: str

    def generate(
        self,
        *,
        prompt: str,
        reference_image_path: str | None,
        resolution: str,
        kind: str,
        job_id: str,
    ) -> GenerationResult: ...
