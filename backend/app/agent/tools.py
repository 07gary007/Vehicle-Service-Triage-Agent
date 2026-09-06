import json
from langchain_core.tools import tool
from sqlalchemy import select
from ..db import SessionLocal
from ..models import ServiceRecord
from ..services.nhtsa import fetch_recalls, rank_recalls
from ..services.retrieval import search_tsb_chunks


@tool
def search_recalls(year: int, make: str, model: str, symptoms: str) -> str:
    """Search official NHTSA recalls for a vehicle, ranked against the current symptoms."""
    recalls = fetch_recalls(year, make, model)
    ranked = rank_recalls(recalls, symptoms, limit=5)
    result = [
        {
            "campaign_number": r.get("NHTSACampaignNumber", ""),
            "component": r.get("Component", ""),
            "summary": r.get("Summary", ""),
            "consequence": r.get("Consequence", ""),
            "remedy": r.get("Remedy", ""),
        }
        for r in ranked
    ]
    return json.dumps(result, ensure_ascii=False)


@tool
def search_technical_bulletins(year: int, make: str, model: str, query: str, k: int = 5) -> str:
    """Semantic search over ingested NHTSA manufacturer technical-communication records for this vehicle."""
    rows = search_tsb_chunks(year, make, model, query, k=k)
    return json.dumps(rows, ensure_ascii=False)


@tool
def get_service_history(vehicle_id: str, limit: int = 8) -> str:
    """Read prior dealership service records and technician notes for this specific demo vehicle."""
    with SessionLocal() as db:
        stmt = (
            select(ServiceRecord)
            .where(ServiceRecord.vehicle_id == vehicle_id)
            .order_by(ServiceRecord.service_date.desc())
            .limit(limit)
        )
        rows = db.scalars(stmt).all()
    result = [
        {
            "service_date": row.service_date.isoformat(),
            "mileage": row.mileage,
            "category": row.category,
            "technician_note": row.technician_note,
        }
        for row in rows
    ]
    return json.dumps(result, ensure_ascii=False)


TOOLS = [search_recalls, search_technical_bulletins, get_service_history]
