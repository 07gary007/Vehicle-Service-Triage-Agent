from app.services.risk import deterministic_risk_override


def test_brake_is_safety_review():
    assert deterministic_risk_override("Grinding noise when braking", "routine") == "safety_review"


def test_airbag_is_safety_review():
    assert deterministic_risk_override("Airbag warning light is on", "priority") == "safety_review"


def test_routine_stays_routine():
    assert deterministic_risk_override("Due for an oil change", "routine") == "routine"


def test_unsubstantiated_priority_is_demoted_to_routine():
    assert deterministic_risk_override("A/C takes a long time to get cold", "priority") == "routine"


def test_negated_warning_light_is_not_a_priority_signal():
    assert deterministic_risk_override("No warning lights", "priority") == "routine"


def test_active_warning_light_is_a_priority_signal():
    assert deterministic_risk_override("The warning light is on", "routine") == "priority"


def test_temperature_gauge_and_hot_smell_are_safety_signals():
    text = "Temperature gauge went above normal and I smelled something hot after driving."

    assert deterministic_risk_override(text, "routine") == "safety_review"
