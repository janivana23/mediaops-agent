"""MediaOps as an MCP server.

Exposes the same service layer used by the FastAPI app (app/service.py) as
MCP tools, so an agent (Claude Code, Claude Desktop, or any MCP client) can
drive the generation pipeline directly — while still going through every
guardrail: budget caps, the approval checkpoint, provider failover, and the
QA gate. The tool layer is a thin translation to text; it enforces nothing
itself, which is intentional — an agent talking to this server has exactly
the same limits as a client calling the REST API.

Run standalone for local testing:
    python mcp_server.py

Or inspect it with the official MCP Inspector:
    npx @modelcontextprotocol/inspector python mcp_server.py
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app import service
from app.db import init_db, session_scope
from app.models import Job

mcp = FastMCP("mediaops")

init_db()


def _describe(job: Job) -> str:
    lines = [
        f"job {job.id} [{job.campaign}] -> {job.status}",
        f"  prompt: {job.prompt!r} ({job.kind}, requested {job.requested_resolution})",
    ]
    if job.status_reason:
        lines.append(f"  reason: {job.status_reason}")
    if job.status == "delivered" or job.status == "qa_failed":
        lines.append(
            f"  provider={job.provider_used} resolution={job.resolution_used} "
            f"cost={job.actual_cost_cents}c qa_identity={job.qa_identity_score} "
            f"qa_brand={job.qa_brand_score} output={job.output_path}"
        )
    return "\n".join(lines)


@mcp.tool()
def generate_asset(
    client_id: str,
    campaign: str,
    prompt: str,
    resolution: str = "1024x1024",
    kind: str = "image",
    reference_image_path: str | None = None,
) -> str:
    """Generate a marketing asset for a client campaign.

    Enforces the client's monthly budget, the auto-approve cost threshold,
    and a QA gate (identity consistency against reference_image_path, brand
    colour compliance) before a job is considered delivered. If the job's
    cost exceeds the auto-approve threshold it will NOT generate — it stops
    at 'awaiting_approval' and a human must call approve_job. If the
    requested resolution doesn't fit the client's remaining budget, a
    cheaper resolution is used automatically and noted in the result.

    Args:
        client_id: id from list_clients.
        campaign: free-text campaign name, used for grouping/reporting.
        prompt: what to generate.
        resolution: "512x512" | "1024x1024" | "2048x2048" (image), ignored for kind="video".
        kind: "image" or "video" (video renders a 3-shot keyframe storyboard, not real video).
        reference_image_path: path to a reference image for character/identity
            consistency, must resolve to somewhere inside the backend/
            project directory (this API has no auth, so arbitrary
            filesystem paths are rejected).
    """
    with session_scope() as session:
        try:
            job = service.create_job(
                session,
                client_id=client_id,
                campaign=campaign,
                prompt=prompt,
                kind=kind,
                resolution=resolution,
                reference_image_path=reference_image_path,
            )
            job = service.run_job(session, job.id)
        except service.MediaOpsError as exc:
            return f"error: {exc}"
        return _describe(job)


@mcp.tool()
def list_clients() -> str:
    """List clients with their monthly budget in cents."""
    with session_scope() as session:
        clients = service.list_clients(session)
        if not clients:
            return "no clients configured — run `python -m app.seed` first"
        return "\n".join(f"{c.id}  {c.name}  budget={c.monthly_budget_cents}c" for c in clients)


@mcp.tool()
def get_usage(client_id: str) -> str:
    """Get a client's monthly budget, spend so far, and remaining headroom."""
    with session_scope() as session:
        try:
            usage = service.usage_summary(session, client_id)
        except service.MediaOpsError as exc:
            return f"error: {exc}"
        return (
            f"{usage['client_name']}: used {usage['used_cents']}c of "
            f"{usage['monthly_budget_cents']}c ({usage['remaining_cents']}c remaining)"
        )


@mcp.tool()
def list_pending_approvals() -> str:
    """List jobs currently blocked on a human approval checkpoint."""
    with session_scope() as session:
        pending = service.list_pending_approvals(session)
        if not pending:
            return "no jobs awaiting approval"
        return "\n".join(f"approval {a.id} for job {a.job_id}: {a.reason}" for a in pending)


@mcp.tool()
def approve_job(job_id: str, decided_by: str) -> str:
    """Approve a job stuck at awaiting_approval and run it (subject to
    budget and QA checks, same as any other job)."""
    with session_scope() as session:
        try:
            job = service.approve_job(session, job_id, decided_by)
        except service.MediaOpsError as exc:
            return f"error: {exc}"
        return _describe(job)


@mcp.tool()
def reject_job(job_id: str, decided_by: str, reason: str = "") -> str:
    """Reject a job stuck at awaiting_approval — it will never generate."""
    with session_scope() as session:
        try:
            job = service.reject_job(session, job_id, decided_by, reason)
        except service.MediaOpsError as exc:
            return f"error: {exc}"
        return _describe(job)


@mcp.tool()
def list_jobs(client_id: str | None = None) -> str:
    """List recent jobs, optionally filtered to one client."""
    with session_scope() as session:
        jobs = service.list_jobs(session, client_id=client_id)
        if not jobs:
            return "no jobs yet"
        return "\n".join(f"{j.id}  {j.campaign!r}  {j.status}  cost={j.actual_cost_cents}c" for j in jobs[:20])


if __name__ == "__main__":
    mcp.run()
