import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

BASE_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.4, min=0.4, max=3),
    reraise=True,
)
def fetch_recalls(year: int, make: str, model: str) -> list[dict]:
    params = {"make": make, "model": model, "modelYear": year}
    with httpx.Client(
        timeout=get_settings().nhtsa_timeout_seconds,
        follow_redirects=True,
    ) as client:
        response = client.get(BASE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    return payload.get("results", [])


def rank_recalls(recalls: list[dict], query: str, limit: int = 5) -> list[dict]:
    terms = {t for t in query.lower().replace("/", " ").split() if len(t) > 3}

    def score(item: dict) -> int:
        haystack = " ".join([
            str(item.get("Component", "")),
            str(item.get("Summary", "")),
            str(item.get("Consequence", "")),
        ]).lower()
        return sum(1 for term in terms if term in haystack)

    ranked = sorted(recalls, key=score, reverse=True)
    return ranked[:limit]
