from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    GENERATING = "generating"
    QA_FAILED = "qa_failed"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    FAILED = "failed"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    monthly_budget_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="client")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    campaign: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="image")  # image | video
    reference_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_resolution: Mapped[str] = mapped_column(String(20), default="1024x1024")
    resolution_used: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    status_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    estimated_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    actual_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    qa_identity_score: Mapped[float | None] = mapped_column(nullable=True)
    qa_brand_score: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="jobs")
    approval: Mapped["ApprovalRequest | None"] = relationship(back_populates="job", uselist=False)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.PENDING.value)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="approval")


class UsageLedgerEntry(Base):
    """Append-only usage record. Client spend is *always* derived by summing
    this table, never tracked as a mutable counter — it's the audit trail
    and the source of truth budget checks read from."""

    __tablename__ = "usage_ledger"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
