from datetime import date, datetime
from typing import Any
from sqlalchemy import Date, DateTime, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
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
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))


class TriageRun(Base):
    __tablename__ = "triage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="needs_review")
    approved_work_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
