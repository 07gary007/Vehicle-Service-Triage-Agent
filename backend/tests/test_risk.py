from app.services.risk import deterministic_risk_override


def test_brake_is_safety_review():
    assert deterministic_risk_override("Grinding noise when braking", "routine") == "safety_review"


def test_airbag_is_safety_review():
    assert deterministic_risk_override("Airbag warning light is on", "priority") == "safety_review"


def test_routine_stays_routine():
    assert deterministic_risk_override("Due for an oil change", "routine") == "routine"
