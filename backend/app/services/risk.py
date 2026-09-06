SAFETY_TERMS = {
    "brake", "brakes", "braking", "abs", "steering", "airbag", "smoke",
    "fire", "fuel leak", "gas leak", "unintended acceleration", "accelerates by itself",
    "loss of power", "stalls in traffic", "overheating", "overheat", "wheel came off",
}

PRIORITY_TERMS = {
    "warning light", "check engine", "vibration", "grinding", "leak", "won't start",
    "will not start", "battery light", "transmission", "rough idle",
}


def deterministic_risk_override(text: str, model_risk: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in SAFETY_TERMS):
        return "safety_review"
    if model_risk == "safety_review":
        return model_risk
    if any(term in lowered for term in PRIORITY_TERMS):
        return "priority"
    return model_risk
