from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class ClientOut(BaseModel):
    id: str
    name: str
    monthly_budget_cents: int

    class Config:
        from_attributes = True


class CreateJobIn(BaseModel):
    client_id: str
    campaign: str
    prompt: str
    kind: str = "image"
    resolution: str = "1024x1024"
    reference_image_path: str | None = None


class JobOut(BaseModel):
    id: str
    client_id: str
    campaign: str
    prompt: str
    kind: str
    requested_resolution: str
    resolution_used: str | None
    status: str
    status_reason: str | None
    estimated_cost_cents: int
    actual_cost_cents: int | None
    provider_used: str | None
    output_path: str | None
    qa_identity_score: float | None
    qa_brand_score: float | None
    created_at: dt.datetime

    class Config:
        from_attributes = True


class ApprovalOut(BaseModel):
    id: str
    job_id: str
    reason: str
    status: str

    class Config:
        from_attributes = True


class ApprovalDecisionIn(BaseModel):
    decided_by: str
    reason: str | None = None


class UsageOut(BaseModel):
    client_id: str
    client_name: str
    monthly_budget_cents: int
    used_cents: int
    remaining_cents: int
