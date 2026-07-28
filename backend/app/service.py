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
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.costs import PROVIDER_ORDER, cost_for
from app.models import ApprovalRequest, ApprovalStatus, Client, Job, JobStatus, UsageLedgerEntry
from app.notify import send_job_event
from app.providers import REGISTRY
from app.providers.base import ProviderError
from app.qa import brand_compliance_score, identity_similarity

log = logging.getLogger("mediaops.service")


class MediaOpsError(Exception):
    """Raised for client-facing failures (unknown client, bad job state)."""


def _validate_reference_path(reference_image_path: str) -> None:
    """This API is unauthenticated and takes a server-side file path
    directly from the caller — without this check it's an arbitrary local
    file read (Pillow will happily open anything that parses as an image,
    anywhere on disk). Confine references to config.REFERENCE_ALLOWED_DIRS,
    which is where the documented workflow expects them to live
    (backend/outputs/...)."""
    resolved = Path(reference_image_path).expanduser().resolve()
    allowed = [d.resolve() for d in config.REFERENCE_ALLOWED_DIRS]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise MediaOpsError(
            f"reference_image_path must be inside one of {allowed} (got {resolved})"
        )
    if not resolved.is_file():
        raise MediaOpsError(f"reference_image_path does not exist: {resolved}")


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
        # Video is priced flat regardless of frame size (see costs.py), but
        # the *string* returned here still has to be a real WxH — it's fed
        # straight to the provider as the keyframe render resolution.
        return requested if cost_for(provider, kind, "video") <= remaining_cents else None
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
    if kind not in ("image", "video"):
        raise MediaOpsError(f"unknown kind {kind!r} — must be 'image' or 'video'")
    if kind != "video" and resolution not in config.RESOLUTION_LADDER:
        raise MediaOpsError(f"unknown resolution {resolution!r} — must be one of {config.RESOLUTION_LADDER}")
    if reference_image_path is not None:
        _validate_reference_path(reference_image_path)

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
        send_job_event("job.rejected", job)
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
        send_job_event("job.awaiting_approval", job)
        return job

    resolution = _affordable_resolution(remaining, job.kind, primary, job.requested_resolution)
    if resolution is None:
        job.status = JobStatus.REJECTED.value
        job.status_reason = "budget_exceeded: no resolution fits remaining budget"
        session.commit()
        send_job_event("job.rejected", job)
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
        send_job_event("job.failed", job)
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
        send_job_event("job.rejected", job)
        return job

    # A provider that failed *before* a later one succeeded is the single
    # most confusing state to debug from the outside: the job looks fine, it
    # just quietly came from the mock. Keep the trail on the job so "why is
    # this mock-seedance?" is answerable from the dashboard rather than from
    # container logs that scroll away on the next redeploy.
    failover_note = "failed over — " + " | ".join(errors) if errors else None

    # A provider whose free tier renders below the requested size upscales to
    # meet it. That's a legitimate pipeline step, but it must be stated: the
    # delivered file is the requested resolution, yet it does not carry that
    # much real detail, and a reviewer comparing two "1024x1024" assets
    # deserves to know which one was interpolated up from 768.
    upscale_note = (
        f"upscaled from {result.native_size} — provider rendered below the requested {resolution}"
        if result.native_size and result.native_size != resolution
        else None
    )

    def _reason(*notes: str | None) -> str | None:
        """Join whichever notes actually apply, preserving earlier ones.

        status_reason carries several independent facts (resolution
        step-down, provider failover, QA scores) and any of them can
        co-occur — assigning it directly silently drops the others.
        """
        present = [n for n in notes if n]
        return "; ".join(present) if present else None

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
        job.status_reason = _reason(stepdown_note, upscale_note, failover_note)
    else:
        job.status = JobStatus.QA_FAILED.value
        reasons = []
        if not identity_ok:
            reasons.append(f"identity {job.qa_identity_score} < {config.QA_IDENTITY_THRESHOLD}")
        if not brand_ok:
            reasons.append(f"brand {job.qa_brand_score} < {config.QA_BRAND_THRESHOLD}")
        qa_note = "qa_failed: " + ", ".join(reasons)
        job.status_reason = _reason(qa_note, stepdown_note, upscale_note, failover_note)

    session.commit()
    session.refresh(job)
    send_job_event(f"job.{job.status}", job)
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
    send_job_event("job.rejected", job)
    return job


# --------------------------------------------------------------------------
# Read models
# --------------------------------------------------------------------------

def list_jobs(
    session: Session, client_id: str | None = None, limit: int = 50, offset: int = 0
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    if client_id:
        stmt = stmt.where(Job.client_id == client_id)
    return list(session.scalars(stmt))


def list_pending_approvals(session: Session) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING.value)
    return list(session.scalars(stmt))


def list_clients(session: Session) -> list[Client]:
    return list(session.scalars(select(Client)))


def create_client(session: Session, *, name: str, monthly_budget_cents: int) -> Client:
    if not name.strip():
        raise MediaOpsError("client name must not be empty")
    if monthly_budget_cents <= 0:
        raise MediaOpsError("monthly_budget_cents must be positive")
    client = Client(name=name.strip(), monthly_budget_cents=monthly_budget_cents)
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


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


def recover_stranded_jobs(session: Session) -> int:
    """Fail any job left mid-generation by a process that died.

    `run_job` commits GENERATING before calling a provider, so the row
    survives a crash but the work does not — a container restart (redeploy,
    OOM, host eviction) leaves jobs stuck in GENERATING with no owner and
    nothing to ever finish them. They aren't retried automatically: a job
    can die *after* a paid provider call succeeded but before the ledger
    entry commits, so a blind retry risks double-charging a client. Mark
    them failed and let a human resubmit.

    Called on startup, which is the moment we can be certain nothing is
    genuinely in flight — this process has just booted and, in a
    single-instance deployment, no other worker owns those rows.
    """
    stranded = session.scalars(
        select(Job).where(Job.status == JobStatus.GENERATING.value)
    ).all()
    for job in stranded:
        job.status = JobStatus.FAILED.value
        job.status_reason = (
            "interrupted: the backend restarted while this job was generating. "
            "No spend was recorded — resubmit it."
        )
        log.warning("recovered stranded job %s left in GENERATING", job.id)
    if stranded:
        session.commit()
    return len(stranded)
