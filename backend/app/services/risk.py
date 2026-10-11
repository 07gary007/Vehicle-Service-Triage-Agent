import re

SAFETY_TERMS = {
    "brake", "brakes", "braking", "abs", "steering", "airbag", "smoke",
    "fire", "fuel leak", "gas leak", "unintended acceleration", "accelerates by itself",
    "loss of power", "stalls in traffic", "overheating", "overheat", "wheel came off",
    "temperature gauge", "hot smell", "smelled something hot", "above normal",
}

PRIORITY_TERMS = {
    "warning light", "check engine", "vibration", "grinding", "leak", "won't start",
    "will not start", "battery light", "transmission", "rough idle",
}


def _is_negated(text: str, term: str) -> bool:
    """Detect short English negations such as 'no warning lights'."""
    term_pattern = r"\s+".join(re.escape(part) for part in term.split()) + r"s?"
    return bool(
        re.search(
            rf"\b(?:no|not|without|never|denies?)\s+(?:[a-z0-9-]+\s+){{0,2}}{term_pattern}\b",
            text,
        )
    )


def deterministic_risk_override(text: str, model_risk: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in SAFETY_TERMS):
        return "safety_review"
    if any(term in lowered and not _is_negated(lowered, term) for term in PRIORITY_TERMS):
        return "priority"
    if model_risk == "safety_review":
        return model_risk
    # Do not let an LLM-only priority label create review friction when the
    # customer language contains no deterministic priority signal. This keeps
    # routine maintenance concerns such as slow A/C cooling routine while
    # preserving the safety-first override above.
    return "routine"
