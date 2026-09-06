import httpx

BASE_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


def fetch_recalls(year: int, make: str, model: str) -> list[dict]:
    params = {"make": make, "model": model, "modelYear": year}
    with httpx.Client(timeout=12.0, follow_redirects=True) as client:
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
