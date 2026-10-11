from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(64), index=True)
    model_year: Mapped[int] = mapped_column(Integer, index=True)
    make: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    mileage: Mapped[int] = mapped_column(Integer)
    service_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(128))
    technician_note: Mapped[str] = mapped_column(Text)


class TSBChunk(Base):
    __tablename__ = "tsb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    nhtsa_id: Mapped[str] = mapped_column(String(64), index=True)
    document_id: Mapped[str] = mapped_column(String(160), index=True)
    make: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    model_year: Mapped[int] = mapped_column(Integer, index=True)
    component: Mapped[str] = mapped_column(String(256), default="")
    communication_type: Mapped[str] = mapped_column(String(128), default="")
    summary: Mapped[str] = mapped_column(Text)
    chunk_text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_title: Mapped[str] = mapped_column(String(256), default="")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingestion_version: Mapped[str] = mapped_column(String(64), default="v1")
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))


class TriageRun(Base):
    __tablename__ = "triage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="needs_review")
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_work_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_version: Mapped[str] = mapped_column(String(64), default="unknown")
    model_name: Mapped[str] = mapped_column(String(128), default="unknown")
    retrieval_version: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TriageEvent(Base):
    __tablename__ = "triage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("triage_runs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    node_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
