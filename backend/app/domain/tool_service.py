"""Typed, framework-independent service operations.

The LangGraph tools and MCP tools both call these functions. Keeping the domain
operations here prevents the agent framework from becoming the data contract.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from ..db import SessionLocal
from ..models import ServiceRecord
from ..services.nhtsa import fetch_recalls, rank_recalls
from ..services.retrieval import search_tsb_chunks


def lookup_recalls(year: int, make: str, model: str, symptoms: str) -> dict[str, Any]:
    recalls = fetch_recalls(year, make, model)
    ranked = rank_recalls(recalls, symptoms, limit=5)
    source_url = (
        "https://api.nhtsa.gov/recalls/recallsByVehicle"
        f"?make={make}&model={model}&modelYear={year}"
    )
    items = [
        {
            "campaign_number": r.get("NHTSACampaignNumber", ""),
            "component": r.get("Component", ""),
            "summary": r.get("Summary", ""),
            "consequence": r.get("Consequence", ""),
            "remedy": r.get("Remedy", ""),
        }
        for r in ranked
    ]
    evidence = [
        {
            "source_type": "nhtsa_recall",
            "source_id": item["campaign_number"] or f"recall-{index}",
            "source_url": source_url,
            "title": item["component"] or "NHTSA recall",
            "snippet": item["summary"],
            "confidence": None,
            "metadata": {"year": year, "make": make.upper(), "model": model.upper()},
        }
        for index, item in enumerate(items, start=1)
    ]
    return {
        "status": "ok",
        "items": items,
        "evidence": evidence,
        "source": "NHTSA Recalls API",
    }


def search_technical_communications(
    year: int,
    make: str,
    model: str,
    query: str,
    k: int = 5,
) -> dict[str, Any]:
    items = search_tsb_chunks(year, make, model, query, k=k)
    evidence = [
        {
            "source_type": "manufacturer_communication",
            "source_id": item["document_id"],
            "source_url": item.get("source_url"),
            "title": item.get("summary") or item["document_id"],
            "section": item.get("section_title") or None,
            "snippet": item["chunk_text"],
            "confidence": item.get("score"),
            "metadata": {
                "nhtsa_id": item.get("nhtsa_id"),
                "page_number": item.get("page_number"),
                "vehicle_match": item.get("vehicle_match"),
                "vector_score": item.get("vector_score"),
                "lexical_score": item.get("lexical_score"),
            },
        }
        for item in items
    ]
    return {
        "status": "ok" if items else "no_match",
        "items": items,
        "evidence": evidence,
        "source": "Indexed manufacturer communications",
        "query": query,
    }


def lookup_service_history(vehicle_id: str, limit: int = 8) -> dict[str, Any]:
    with SessionLocal() as db:
        stmt = (
            select(ServiceRecord)
            .where(ServiceRecord.vehicle_id == vehicle_id)
            .order_by(ServiceRecord.service_date.desc())
            .limit(limit)
        )
        rows = db.scalars(stmt).all()

    items = [
        {
            "record_id": row.id,
            "service_date": row.service_date.isoformat(),
            "mileage": row.mileage,
            "category": row.category,
            "technician_note": row.technician_note,
        }
        for row in rows
    ]
    evidence = [
        {
            "source_type": "service_history",
            "source_id": f"service_record:{item['record_id']}",
            "source_url": None,
            "title": item["category"],
            "snippet": item["technician_note"],
            "confidence": None,
            "metadata": {"vehicle_id": vehicle_id, "service_date": item["service_date"]},
        }
        for item in items
    ]
    return {
        "status": "ok" if items else "no_match",
        "items": items,
        "evidence": evidence,
        "source": "Dealership service history",
    }


def as_tool_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)

