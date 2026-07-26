from __future__ import annotations

import requests

from app import config, service
from app.models import JobStatus


def test_webhook_disabled_by_default_makes_no_request(session, client, monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append((a, k)))
    job = service.create_job(session, client_id=client.id, campaign="c", prompt="p")
    service.run_job(session, job.id)
    assert calls == []


def test_webhook_fires_with_job_payload_on_delivery(session, client, monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))

    monkeypatch.setattr(config, "WEBHOOK_URL", "https://example.com/n8n-hook")
    monkeypatch.setattr(requests, "post", fake_post)

    job = service.create_job(session, client_id=client.id, campaign="c", prompt="p")
    result = service.run_job(session, job.id)

    assert result.status == JobStatus.DELIVERED.value
    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == "https://example.com/n8n-hook"
    assert payload["event"] == f"job.{JobStatus.DELIVERED.value}"
    assert payload["job_id"] == job.id
    assert payload["status"] == "delivered"
    assert timeout == config.WEBHOOK_TIMEOUT_SECONDS


def test_webhook_failure_does_not_break_the_job(session, client, monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_URL", "https://example.com/n8n-hook")

    def boom(*a, **k):
        raise requests.ConnectionError("n8n is down")

    monkeypatch.setattr(requests, "post", boom)

    job = service.create_job(session, client_id=client.id, campaign="c", prompt="p")
    result = service.run_job(session, job.id)
    assert result.status == JobStatus.DELIVERED.value  # webhook failure didn't roll anything back
