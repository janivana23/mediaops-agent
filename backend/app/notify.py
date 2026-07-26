"""Best-effort webhook notifications on job status changes.

Fires a plain JSON POST to config.WEBHOOK_URL — the generic shape an n8n
Webhook trigger node expects, no n8n-specific SDK involved. This is the
hook point the JD's "automation pipelines in n8n connecting internal
systems, comms, and client channels" bullet describes: point WEBHOOK_URL
at an n8n webhook and route job events into Slack, email, a client
portal, whatever workflow needs them, without touching this codebase.

Deliberately best-effort: a webhook failure (n8n down, DNS hiccup,
timeout) must never fail or roll back the job it's reporting on. Errors
are logged and swallowed.
"""
from __future__ import annotations

import logging

import requests

from app import config
from app.models import Job

log = logging.getLogger("mediaops.notify")


def send_job_event(event: str, job: Job) -> None:
    if not config.WEBHOOK_URL:
        return
    payload = {
        "event": event,
        "job_id": job.id,
        "client_id": job.client_id,
        "campaign": job.campaign,
        "kind": job.kind,
        "status": job.status,
        "status_reason": job.status_reason,
        "provider_used": job.provider_used,
        "resolution_used": job.resolution_used,
        "actual_cost_cents": job.actual_cost_cents,
        "qa_identity_score": job.qa_identity_score,
        "qa_brand_score": job.qa_brand_score,
        "output_path": job.output_path,
    }
    try:
        requests.post(config.WEBHOOK_URL, json=payload, timeout=config.WEBHOOK_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        log.warning("webhook delivery failed for job %s event %s: %s", job.id, event, exc)
