from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import config, schemas, service
from app.db import get_session, init_db

app = FastAPI(title="MediaOps Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.mount("/outputs", StaticFiles(directory=str(config.OUTPUT_DIR)), name="outputs")


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.MediaOpsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/clients", response_model=list[schemas.ClientOut])
def get_clients(session: Session = Depends(get_session)):
    return service.list_clients(session)


@app.get("/clients/{client_id}/usage", response_model=schemas.UsageOut)
def get_usage(client_id: str, session: Session = Depends(get_session)):
    return _handle(service.usage_summary, session, client_id)


@app.get("/jobs", response_model=list[schemas.JobOut])
def get_jobs(client_id: str | None = None, session: Session = Depends(get_session)):
    return service.list_jobs(session, client_id=client_id)


@app.post("/jobs", response_model=schemas.JobOut)
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


@app.get("/approvals", response_model=list[schemas.ApprovalOut])
def get_approvals(session: Session = Depends(get_session)):
    return service.list_pending_approvals(session)


@app.post("/approvals/{job_id}/approve", response_model=schemas.JobOut)
def post_approve(job_id: str, payload: schemas.ApprovalDecisionIn, session: Session = Depends(get_session)):
    return _handle(service.approve_job, session, job_id, payload.decided_by)


@app.post("/approvals/{job_id}/reject", response_model=schemas.JobOut)
def post_reject(job_id: str, payload: schemas.ApprovalDecisionIn, session: Session = Depends(get_session)):
    return _handle(service.reject_job, session, job_id, payload.decided_by, payload.reason or "")


@app.get("/health")
def health():
    return {"status": "ok"}
