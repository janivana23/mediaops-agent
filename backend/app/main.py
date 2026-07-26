from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import config, schemas, service
from app.db import get_session, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MediaOps Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(config.OUTPUT_DIR)), name="outputs")


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """No-op (auth disabled) unless config.API_KEY is set — matches this
    project's zero-config-by-default pattern. Set API_KEY before putting
    this API anywhere reachable off localhost; there's no other auth
    layer. /health and /outputs are deliberately left open: health checks
    need to work unauthenticated, and outputs are keyed by unguessable job
    ids rather than sequential ones."""
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.MediaOpsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/clients", response_model=list[schemas.ClientOut], dependencies=[Depends(require_api_key)])
def get_clients(session: Session = Depends(get_session)):
    return service.list_clients(session)


@app.post("/clients", response_model=schemas.ClientOut, dependencies=[Depends(require_api_key)])
def post_client(payload: schemas.CreateClientIn, session: Session = Depends(get_session)):
    return _handle(
        service.create_client, session, name=payload.name, monthly_budget_cents=payload.monthly_budget_cents
    )


@app.get("/clients/{client_id}/usage", response_model=schemas.UsageOut, dependencies=[Depends(require_api_key)])
def get_usage(client_id: str, session: Session = Depends(get_session)):
    return _handle(service.usage_summary, session, client_id)


@app.get("/jobs", response_model=list[schemas.JobOut], dependencies=[Depends(require_api_key)])
def get_jobs(
    client_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    limit = max(1, min(limit, 200))
    return service.list_jobs(session, client_id=client_id, limit=limit, offset=offset)


@app.post("/jobs", response_model=schemas.JobOut, dependencies=[Depends(require_api_key)])
def post_job(payload: schemas.CreateJobIn, session: Session = Depends(get_session)):
    job = _handle(
        service.create_job,
        session,
        client_id=payload.client_id,
        campaign=payload.campaign,
        prompt=payload.prompt,
        kind=payload.kind,
        resolution=payload.resolution,
        reference_image_path=payload.reference_image_path,
    )
    return _handle(service.run_job, session, job.id)


@app.get("/approvals", response_model=list[schemas.ApprovalOut], dependencies=[Depends(require_api_key)])
def get_approvals(session: Session = Depends(get_session)):
    return service.list_pending_approvals(session)


@app.post(
    "/approvals/{job_id}/approve", response_model=schemas.JobOut, dependencies=[Depends(require_api_key)]
)
def post_approve(job_id: str, payload: schemas.ApprovalDecisionIn, session: Session = Depends(get_session)):
    return _handle(service.approve_job, session, job_id, payload.decided_by)


@app.post(
    "/approvals/{job_id}/reject", response_model=schemas.JobOut, dependencies=[Depends(require_api_key)]
)
def post_reject(job_id: str, payload: schemas.ApprovalDecisionIn, session: Session = Depends(get_session)):
    return _handle(service.reject_job, session, job_id, payload.decided_by, payload.reason or "")


@app.get("/health")
def health():
    return {"status": "ok"}
