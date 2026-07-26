from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.db import get_session
from app.main import app
from app.models import Base


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    """Isolated DB per test via FastAPI's dependency override — without
    this, TestClient would hit the real backend/mediaops.db file, since
    db.py's engine is built once at import time from config.DATABASE_URL."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "REFERENCE_ALLOWED_DIRS", [tmp_path])
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(config, "WEBHOOK_URL", "")
    monkeypatch.setattr(config, "API_KEY", "")

    # StaticPool: without it, FastAPI's threadpool for sync endpoints hands
    # each request a different thread, and each thread would otherwise get
    # its own *separate* in-memory SQLite database (they aren't shared
    # across connections) — StaticPool keeps every connection on the one
    # underlying in-memory DB regardless of thread.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def _override():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_never_requires_a_key(api_client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = api_client.get("/health")
    assert resp.status_code == 200


def test_no_api_key_configured_allows_requests(api_client):
    resp = api_client.get("/clients")
    assert resp.status_code == 200


def test_configured_api_key_rejects_missing_header(api_client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = api_client.get("/clients")
    assert resp.status_code == 401


def test_configured_api_key_rejects_wrong_key(api_client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = api_client.get("/clients", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_configured_api_key_accepts_correct_key(api_client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret123")
    resp = api_client.get("/clients", headers={"X-API-Key": "secret123"})
    assert resp.status_code == 200


def test_create_client_endpoint(api_client):
    resp = api_client.post("/clients", json={"name": "New Co", "monthly_budget_cents": 3000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Co"
    assert body["monthly_budget_cents"] == 3000

    listed = api_client.get("/clients").json()
    assert any(c["id"] == body["id"] for c in listed)


def test_create_client_endpoint_rejects_bad_budget(api_client):
    resp = api_client.post("/clients", json={"name": "Bad Co", "monthly_budget_cents": 0})
    assert resp.status_code == 400


def test_jobs_endpoint_pagination(api_client):
    client_id = api_client.post("/clients", json={"name": "Paginate Co", "monthly_budget_cents": 100_000}).json()["id"]
    for i in range(3):
        api_client.post(
            "/jobs",
            json={"client_id": client_id, "campaign": f"c{i}", "prompt": "p", "resolution": "512x512"},
        )
    page = api_client.get("/jobs", params={"client_id": client_id, "limit": 2}).json()
    assert len(page) == 2


def test_invalid_resolution_returns_400_not_500(api_client):
    client_id = api_client.post("/clients", json={"name": "Bad Res Co", "monthly_budget_cents": 1000}).json()["id"]
    resp = api_client.post(
        "/jobs", json={"client_id": client_id, "campaign": "c", "prompt": "p", "resolution": "9999x9999"}
    )
    assert resp.status_code == 400
