import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from budget_core.units.quantity import UnitError, canonical_unit, format_quantity, parse_quantity


@pytest.mark.parametrize(
    ("text", "field", "expected"),
    [
        ("2.2 GHz", "freq_hz", 2.2e9),
        ("2200 MHz", "freq_hz", 2.2e9),
        ("500 mW", "avg_power_w", 0.5),
        ("1.5 kg", "mass_kg", 1.5),
        ("1500 g", "mass_kg", 1.5),
        ("35 min", "max_duration_s", 2100.0),
        ("100 Wh", "capacity_wh", 100.0),
        ("0.1 kWh", "capacity_wh", 100.0),
        ("50 %", "margin_ratio", 0.5),
        ("1000 km", "range_m", 1.0e6),
        ("500 kbit/s", "data_rate_bps", 5.0e5),
        ("10 dB", "loss_db", 10.0),
        ("5 dBi", "gain_dbi", 5.0),
        ("30 dBm", "tx_power_dbw", 0.0),
        ("10 dBW", "tx_power_dbw", 10.0),
        ("0 dBW", "tx_power_dbm", 30.0),
        ("290 K", "system_temp_k", 290.0),
        ("90 deg", "elevation_deg", 90.0),
        ("28 V", "nominal_voltage_v", 28.0),
    ],
)
def test_parse_converts_to_canonical(text: str, field: str, expected: float) -> None:
    assert parse_quantity(text, field) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("text", "field", "needle"),
    [
        ("10 dBW", "avg_power_w", "logarithmic"),
        ("10 W", "tx_power_dbw", "linear"),
        ("5 kg", "avg_power_w", "power"),
        ("5", "avg_power_w", "unit"),
        ("abc", "avg_power_w", "number"),
        ("3 dBi", "loss_db", "dBi"),
        ("", "avg_power_w", "number"),
        ("1 W", "something_unknown", "suffix"),
        ("nan W", "avg_power_w", "finite"),
        ("5 blargs", "range_m", "unit"),
    ],
)
def test_parse_rejects_with_plain_message(text: str, field: str, needle: str) -> None:
    with pytest.raises(UnitError) as exc:
        parse_quantity(text, field)
    assert needle in str(exc.value)


def test_canonical_unit_labels() -> None:
    assert canonical_unit("avg_power_w") == "W"
    assert canonical_unit("freq_hz") == "Hz"
    assert canonical_unit("tx_power_dbw") == "dBW"
    assert canonical_unit("margin_ratio") == "ratio"
    assert canonical_unit("name") is None


def test_error_messages_do_not_echo_the_input_value() -> None:
    with pytest.raises(UnitError) as exc:
        parse_quantity("SECRET-123 W", "avg_power_w")
    assert "SECRET" not in str(exc.value)


@given(st.floats(min_value=1e-9, max_value=1e12, allow_nan=False))
def test_format_parse_round_trip(x: float) -> None:
    assert math.isclose(parse_quantity(format_quantity(x, "freq_hz"), "freq_hz"), x, rel_tol=1e-12)
