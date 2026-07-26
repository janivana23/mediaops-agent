from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    monthly_budget_cents: int


class CreateClientIn(BaseModel):
    name: str
    monthly_budget_cents: int


class CreateJobIn(BaseModel):
    client_id: str
    campaign: str
    prompt: str
    kind: str = "image"
    resolution: str = "1024x1024"
    reference_image_path: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    reason: str
    status: str


class ApprovalDecisionIn(BaseModel):
    decided_by: str
    reason: str | None = None


class UsageOut(BaseModel):
    client_id: str
    client_name: str
    monthly_budget_cents: int
    used_cents: int
    remaining_cents: int
