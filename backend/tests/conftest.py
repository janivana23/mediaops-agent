from __future__ import annotations

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import config
from app.models import Base, Client


@pytest.fixture(autouse=True)
def _offline_by_default(monkeypatch):
    """Tests must never depend on whatever happens to be in a developer's
    real .env — config.py loads it unconditionally, so without this a real
    OPENROUTER_API_KEY on disk would make the suite hit the live network
    (masked as "passing" because failover swallows the resulting
    ProviderError, but slow, flaky, and not actually testing what it looks
    like it's testing). Individual tests re-enable it explicitly."""
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "WEBHOOK_URL", "")


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "REFERENCE_ALLOWED_DIRS", [tmp_path])
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def reference_image(tmp_path):
    path = tmp_path / "reference.png"
    img = Image.new("RGB", (256, 256), (40, 90, 170))
    img.save(path)
    return str(path)


@pytest.fixture()
def client(session):
    c = Client(name="Test Client", monthly_budget_cents=1000)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c
