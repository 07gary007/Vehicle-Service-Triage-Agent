from app.services.retrieval import expand_query


def test_hot_ambient_condition_does_not_expand_to_overheating() -> None:
    variants = expand_query("A/C takes a long time to get cold on hot days")

    assert all("overheating" not in variant.lower() for variant in variants)


def test_explicit_temperature_signal_expands_to_thermal_terms() -> None:
    variants = expand_query("temperature gauge went above normal and hot smell")

    assert any("overheating" in variant.lower() for variant in variants)
