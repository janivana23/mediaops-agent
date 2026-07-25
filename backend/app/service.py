"""Core business logic — the one place budget limits, approval checkpoints,
usage metering and provider failover are enforced.

This module is imported by both the FastAPI app (app/main.py) and the MCP
server (mcp_server.py). That's deliberate: whichever surface an agent talks
through, the same guardrails run. An agent cannot get a cheaper answer by
calling the MCP tool instead of the REST endpoint, or vice versa.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.costs import PROVIDER_ORDER, cost_for
from app.models import ApprovalRequest, ApprovalStatus, Client, Job, JobStatus, UsageLedgerEntry
from app.providers import REGISTRY
from app.providers.base import ProviderError
from app.qa import brand_compliance_score, identity_similarity

log = logging.getLogger("mediaops.service")


class MediaOpsError(Exception):
    """Raised for client-facing failures (unknown client, bad job state)."""


# --------------------------------------------------------------------------
# Budget
# --------------------------------------------------------------------------

def get_client_usage_cents(session: Session, client_id: str) -> int:
    """Spend is always derived by summing the append-only ledger — never a
    mutable counter that could drift from the audit trail."""
    now = dt.datetime.now(dt.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = session.scalars(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.client_id == client_id,
            UsageLedgerEntry.created_at >= month_start,
        )
    )
    return sum(r.amount_cents for r in rows)


def _affordable_resolution(remaining_cents: int, kind: str, provider: str, requested: str) -> str | None:
    """Cost-aware resolution strategy: step *down* from the requested
    resolution until something fits the remaining budget, instead of
    failing a job outright over a resolution choice. Never steps up past
    what was requested."""
    if kind == "video":
        return "video" if cost_for(provider, kind, "video") <= remaining_cents else None
    ladder = config.RESOLUTION_LADDER
    start = ladder.index(requested) if requested in ladder else 0
    for res in ladder[start:]:
        if cost_for(provider, kind, res) <= remaining_cents:
            return res
    return None


# --------------------------------------------------------------------------
# Job lifecycle
# --------------------------------------------------------------------------

def create_job(
    session: Session,
    *,
    client_id: str,
    campaign: str,
    prompt: str,
    kind: str = "image",
    resolution: str = "1024x1024",
    reference_image_path: str | None = None,
) -> Job:
    client = session.get(Client, client_id)
    if client is None:
        raise MediaOpsError(f"unknown client_id {client_id!r}")

    provider = PROVIDER_ORDER[0]
    job = Job(
        client_id=client_id,
        campaign=campaign,
        prompt=prompt,
        kind=kind,
        requested_resolution=resolution,
        reference_image_path=reference_image_path,
        estimated_cost_cents=cost_for(provider, kind, resolution),
        status=JobStatus.PENDING.value,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def run_job(session: Session, job_id: str) -> Job:
    """Attempt to generate the asset for a job, enforcing (in order):

    1. Budget cap — refuse if even the cheapest resolution would blow the
       client's remaining monthly budget.
    2. Approval checkpoint — jobs above AUTO_APPROVE_THRESHOLD_CENTS never
       auto-generate, regardless of budget headroom. They stop at
       awaiting_approval until a human calls approve_job.
    3. Cost-aware resolution stepdown — if the requested resolution doesn't
       fit remaining budget but a smaller one does, generate at the smaller
       size rather than failing.
    4. Provider failover — try providers in order; the first success wins.
    5. QA gate — score the result before marking it delivered.
    """
    job = session.get(Job, job_id)
    if job is None:
        raise MediaOpsError(f"unknown job_id {job_id!r}")
    client = session.get(Client, job.client_id)

    if job.status not in (JobStatus.PENDING.value, JobStatus.APPROVED.value):
        raise MediaOpsError(f"job {job_id} is not runnable from status {job.status!r}")

    was_pre_approved = job.status == JobStatus.APPROVED.value

    usage = get_client_usage_cents(session, client.id)
    remaining = client.monthly_budget_cents - usage

    primary = PROVIDER_ORDER[0]
    cheapest_cost = cost_for(primary, job.kind, config.RESOLUTION_LADDER[-1] if job.kind != "video" else "video")
    if remaining < cheapest_cost:
        job.status = JobStatus.REJECTED.value
        job.status_reason = f"budget_exceeded: {remaining}c remaining, cheapest option is {cheapest_cost}c"
        session.commit()
        return job

    requested_cost = cost_for(primary, job.kind, job.requested_resolution)
    if requested_cost > config.AUTO_APPROVE_THRESHOLD_CENTS and not was_pre_approved:
        job.status = JobStatus.AWAITING_APPROVAL.value
        job.status_reason = (
            f"cost {requested_cost}c exceeds auto-approve threshold "
            f"{config.AUTO_APPROVE_THRESHOLD_CENTS}c"
        )
        session.add(
            ApprovalRequest(job_id=job.id, reason=job.status_reason, status=ApprovalStatus.PENDING.value)
        )
        session.commit()
        return job

    resolution = _affordable_resolution(remaining, job.kind, primary, job.requested_resolution)
    if resolution is None:
        job.status = JobStatus.REJECTED.value
        job.status_reason = "budget_exceeded: no resolution fits remaining budget"
        session.commit()
        return job

    # Clear whatever status_reason got set on the way in here (e.g. the
    # approval-threshold note from before a human signed off) — from this
    # point on it should only reflect what happens to *this* attempt.
    stepdown_note = None
    if job.kind != "video" and resolution != job.requested_resolution:
        stepdown_note = f"stepped down from {job.requested_resolution} to {resolution} to fit budget"
    job.status_reason = stepdown_note

    job.status = JobStatus.GENERATING.value
    session.commit()

    result = None
    errors: list[str] = []
    used_provider = None
    for provider_name in PROVIDER_ORDER:
        try:
            result = REGISTRY[provider_name].generate(
                prompt=job.prompt,
                reference_image_path=job.reference_image_path,
                resolution=resolution,
                kind=job.kind,
                job_id=job.id,
            )
            used_provider = provider_name
            break
        except ProviderError as exc:
            errors.append(f"{provider_name}: {exc}")
            log.warning("provider %s failed for job %s, failing over: %s", provider_name, job.id, exc)
            continue

    if result is None:
        job.status = JobStatus.FAILED.value
        job.status_reason = "all providers failed: " + " | ".join(errors)
        session.commit()
        return job

    actual_cost = cost_for(used_provider, job.kind, resolution)

    # Re-check budget just before committing spend — best-effort guard
    # against a second job racing past the same limit between our read and
    # write. A production deployment on Postgres would additionally take a
    # `SELECT ... FOR UPDATE` on the client row here for a hard guarantee;
    # SQLite (this demo's default) doesn't support row locking the same way.
    usage_now = get_client_usage_cents(session, client.id)
    if usage_now + actual_cost > client.monthly_budget_cents:
        job.status = JobStatus.REJECTED.value
        job.status_reason = "budget_exceeded: exhausted by a concurrent job"
        session.commit()
        return job

    job.resolution_used = resolution
    job.provider_used = used_provider
    job.actual_cost_cents = actual_cost
    job.output_path = str(result.output_path)
    session.add(UsageLedgerEntry(client_id=client.id, job_id=job.id, amount_cents=actual_cost, provider=used_provider))

    if job.kind == "image" and job.reference_image_path:
        job.qa_identity_score = identity_similarity(job.reference_image_path, str(result.output_path))
    if job.kind == "image":
        job.qa_brand_score = brand_compliance_score(str(result.output_path))

    identity_ok = job.qa_identity_score is None or job.qa_identity_score >= config.QA_IDENTITY_THRESHOLD
    brand_ok = job.qa_brand_score is None or job.qa_brand_score >= config.QA_BRAND_THRESHOLD
    if identity_ok and brand_ok:
        job.status = JobStatus.DELIVERED.value
    else:
        job.status = JobStatus.QA_FAILED.value
        reasons = []
        if not identity_ok:
            reasons.append(f"identity {job.qa_identity_score} < {config.QA_IDENTITY_THRESHOLD}")
        if not brand_ok:
            reasons.append(f"brand {job.qa_brand_score} < {config.QA_BRAND_THRESHOLD}")
        job.status_reason = "qa_failed: " + ", ".join(reasons)

    session.commit()
    session.refresh(job)
    return job


def approve_job(session: Session, job_id: str, decided_by: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise MediaOpsError(f"unknown job_id {job_id!r}")
    if job.status != JobStatus.AWAITING_APPROVAL.value:
        raise MediaOpsError(f"job {job_id} is not awaiting approval (status={job.status})")

    approval = job.approval
    approval.status = ApprovalStatus.APPROVED.value
    approval.decided_by = decided_by
    approval.decided_at = dt.datetime.now(dt.timezone.utc)
    job.status = JobStatus.APPROVED.value
    session.commit()

    return run_job(session, job_id)


def reject_job(session: Session, job_id: str, decided_by: str, reason: str = "") -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise MediaOpsError(f"unknown job_id {job_id!r}")
    if job.status != JobStatus.AWAITING_APPROVAL.value:
        raise MediaOpsError(f"job {job_id} is not awaiting approval (status={job.status})")

    approval = job.approval
    approval.status = ApprovalStatus.REJECTED.value
    approval.decided_by = decided_by
    approval.decided_at = dt.datetime.now(dt.timezone.utc)
    job.status = JobStatus.REJECTED.value
    job.status_reason = reason or "rejected by approver"
    session.commit()
    session.refresh(job)
    return job


# --------------------------------------------------------------------------
# Read models
# --------------------------------------------------------------------------

def list_jobs(session: Session, client_id: str | None = None) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if client_id:
        stmt = stmt.where(Job.client_id == client_id)
    return list(session.scalars(stmt))


def list_pending_approvals(session: Session) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING.value)
    return list(session.scalars(stmt))


def list_clients(session: Session) -> list[Client]:
    return list(session.scalars(select(Client)))


def usage_summary(session: Session, client_id: str) -> dict:
    client = session.get(Client, client_id)
    if client is None:
        raise MediaOpsError(f"unknown client_id {client_id!r}")
    used = get_client_usage_cents(session, client_id)
    return {
        "client_id": client.id,
        "client_name": client.name,
        "monthly_budget_cents": client.monthly_budget_cents,
        "used_cents": used,
        "remaining_cents": client.monthly_budget_cents - used,
    }
