from typing import Any

import pytest
from pydantic import ValidationError

from budget_core.model import (
    MarginPolicy,
    PowerMode,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    Unit,
)


def mode(**kw: Any) -> dict[str, Any]:
    base = {"name": "on", "avg_power_w": 2.0, "peak_power_w": 3.0}
    return {**base, **kw}


def unit(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "OBC",
        "subsystem": "DH",
        "mass_kg": 0.2,
        "bus": "main",
        "maturity": "m1",
        "modes": [mode()],
    }
    return {**base, **kw}


def errors(exc: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple[Any, ...], str]]:
    return [(tuple(e["loc"]), e["type"]) for e in exc.value.errors()]


def test_valid_unit_defaults() -> None:
    u = Unit.model_validate(unit())
    assert u.kind == "unit" and u.schema_version == 1
    assert u.modes[0].duty_cycle_ratio == 1.0
    assert u.catalogue_ref is None


def test_strings_with_units_are_normalised() -> None:
    u = Unit.model_validate(
        unit(mass_kg="200 g", modes=[mode(avg_power_w="500 mW", peak_power_w="1 W")])
    )
    assert u.mass_kg == pytest.approx(0.2)
    assert u.modes[0].avg_power_w == pytest.approx(0.5)


def test_unit_error_is_located_on_the_field() -> None:
    with pytest.raises(ValidationError) as exc:
        Unit.model_validate(unit(modes=[mode(avg_power_w="3 dBW")]))
    assert (("modes", 0, "avg_power_w"), "unit_invalid") in errors(exc)


def test_plain_numeric_string_without_unit_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Unit.model_validate(unit(mass_kg="0.2"))
    assert (("mass_kg",), "unit_invalid") in errors(exc)


def test_bool_is_not_a_number() -> None:
    with pytest.raises(ValidationError) as exc:
        Unit.model_validate(unit(mass_kg=True))
    assert (("mass_kg",), "unit_invalid") in errors(exc)


@pytest.mark.parametrize(
    ("kw", "err_type"),
    [
        ({"avg_power_w": -1.0}, "greater_than_equal"),
        ({"duty_cycle_ratio": 1.5}, "less_than_equal"),
        ({"duty_cycle_ratio": -0.1}, "greater_than_equal"),
        ({"avg_power_w": 5.0, "peak_power_w": 3.0}, "peak_below_average"),
        ({"min_duration_s": 10.0, "max_duration_s": 5.0}, "duration_order"),
        ({"max_duration_s": 0.0}, "greater_than"),
    ],
)
def test_power_mode_rules(kw: dict[str, Any], err_type: str) -> None:
    with pytest.raises(ValidationError) as exc:
        PowerMode.model_validate(mode(**kw))
    assert err_type in [t for _, t in errors(exc)]


def test_nan_and_inf_rejected() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            PowerMode.model_validate(mode(avg_power_w=bad))


def test_duplicate_mode_names_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Unit.model_validate(unit(modes=[mode(), mode()]))
    assert (("modes",), "duplicate_name") in errors(exc)


def test_unknown_and_missing_fields() -> None:
    bad = unit(avg_power=1.0)
    del bad["subsystem"]
    with pytest.raises(ValidationError) as exc:
        Unit.model_validate(bad)
    got = errors(exc)
    assert (("avg_power",), "extra_forbidden") in got
    assert (("subsystem",), "missing") in got


def test_models_are_frozen() -> None:
    u = Unit.model_validate(unit())
    with pytest.raises(ValidationError):
        u.name = "x"  # type: ignore[misc]


def test_assignments_sorted_by_unit_id() -> None:
    m = SpacecraftMode.model_validate(
        {"name": "nominal", "assignments": {"zeta": "on", "alpha": "off"}}
    )
    assert list(m.assignments) == ["alpha", "zeta"]


def test_spacecraft_bus_names_unique() -> None:
    bus = {"name": "main", "nominal_voltage_v": 28.0}
    with pytest.raises(ValidationError) as exc:
        Spacecraft.model_validate({"name": "SAT", "buses": [bus, bus]})
    assert (("buses",), "duplicate_name") in errors(exc)


@pytest.mark.parametrize(
    ("value", "source", "placeholder"),
    [
        (None, "anything", True),
        (0.1, "TBD", True),
        (0.1, " tbd ", True),
        (0.1, "Company margin table rev A, table 3", False),
    ],
)
def test_sourced_placeholder_detection(value: float | None, source: str, placeholder: bool) -> None:
    assert Sourced(value=value, source=source).is_placeholder is placeholder


def test_sourced_requires_a_source() -> None:
    with pytest.raises(ValidationError) as exc:
        Sourced.model_validate({"value": 0.1, "source": ""})
    assert (("source",), "string_too_short") in errors(exc)
    with pytest.raises(ValidationError) as exc2:
        Sourced.model_validate({"value": 0.1})
    assert (("source",), "missing") in errors(exc2)


def test_margin_policy_classes_sorted() -> None:
    s = {"value": None, "source": "TBD"}
    cls = {"power_margin_ratio": s, "mass_margin_ratio": s}
    p = MarginPolicy.model_validate(
        {
            "classes": {"b": cls, "a": cls},
            "system_power_margin_ratio": s,
            "system_mass_margin_ratio": s,
        }
    )
    assert list(p.classes) == ["a", "b"]


def test_mass_properties_accept_units_and_validate_inertia() -> None:
    from budget_core.model import MassProperties

    props = MassProperties.model_validate(
        {
            "position_m": ["10 cm", "0 m", 0.2],
            "inertia": {"ixx_kgm2": "5 kg*m^2", "iyy_kgm2": 5.0, "izz_kgm2": 5.0},
        }
    )
    assert props.position_m == [pytest.approx(0.1), 0.0, 0.2]
    assert props.inertia is not None and props.inertia.ixx_kgm2 == 5.0


@pytest.mark.parametrize(
    "bad",
    [
        {"position_m": [0.0, 0.0]},  # needs three coordinates
        {"position_m": [0.0, 0.0, 0.0, 0.0]},
        {"position_m": [0.0, 0.0, "3 kg"]},  # wrong unit kind
        {"position_m": [0.0, 0.0, 0.0], "inertia": {"ixx_kgm2": 1, "iyy_kgm2": 1, "izz_kgm2": 3}},
        {"position_m": [0.0, 0.0, 0.0], "inertia": {"ixx_kgm2": -1, "iyy_kgm2": 1, "izz_kgm2": 1}},
        {
            "position_m": [0.0, 0.0, 0.0],
            "inertia": {"ixx_kgm2": 1, "iyy_kgm2": 1, "izz_kgm2": 1, "ixy_kgm2": 0.9},
        },
    ],
)
def test_invalid_mass_properties_are_rejected(bad: dict[str, Any]) -> None:
    from budget_core.model import MassProperties

    with pytest.raises(ValidationError):
        MassProperties.model_validate(bad)


def test_expendable_masses_sorted_and_non_negative() -> None:
    from budget_core.model import Expendable

    base = {"name": "Fuel", "subsystem": "PROP", "maturity": "m1"}
    e = Expendable.model_validate({**base, "masses_kg": {"launch": 5.0, "bol": 4.0}})
    assert list(e.masses_kg) == ["bol", "launch"]
    with pytest.raises(ValidationError):
        Expendable.model_validate({**base, "masses_kg": {"launch": -1.0}})


def test_phase_lists_must_be_unique() -> None:
    bus = {"name": "main", "nominal_voltage_v": 28.0}
    with pytest.raises(ValidationError):
        Spacecraft.model_validate({"name": "S", "buses": [bus], "mission_phases": ["a", "a"]})
    with pytest.raises(ValidationError):
        Unit.model_validate(unit(phases=["a", "a"]))


def test_kgm2_suffix_parses() -> None:
    from budget_core.units.quantity import canonical_unit, parse_quantity

    assert parse_quantity("2 kg*m^2", "ixx_kgm2") == pytest.approx(2.0)
    assert canonical_unit("ixx_kgm2") == "kg m2"
