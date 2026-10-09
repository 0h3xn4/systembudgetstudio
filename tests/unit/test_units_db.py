import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from budget_core.units import db


def test_known_values() -> None:
    assert db.watt_to_dbw(10.0) == pytest.approx(10.0)
    assert db.watt_to_dbw(1.0) == 0.0
    assert db.watt_to_dbm(1.0) == pytest.approx(30.0)
    assert db.db_to_ratio(3.0) == pytest.approx(1.9952623149688795)
    assert db.ratio_to_db(100.0) == pytest.approx(20.0)
    assert db.dbw_to_dbm(0.0) == 30.0
    assert db.dbm_to_dbw(30.0) == 0.0


@pytest.mark.parametrize("fn", [db.ratio_to_db, db.watt_to_dbw, db.watt_to_dbm])
@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_non_positive_linear_values_rejected(fn, bad: float) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="positive"):
        fn(bad)


pos = st.floats(min_value=1e-12, max_value=1e12, allow_nan=False)
dbs = st.floats(min_value=-200.0, max_value=200.0, allow_nan=False)


@given(pos)
def test_ratio_round_trip(x: float) -> None:
    assert math.isclose(db.db_to_ratio(db.ratio_to_db(x)), x, rel_tol=1e-12)


@given(dbs)
def test_db_round_trip(x: float) -> None:
    assert math.isclose(db.ratio_to_db(db.db_to_ratio(x)), x, rel_tol=1e-12, abs_tol=1e-12)


@given(pos)
def test_watt_dbw_round_trip(w: float) -> None:
    assert math.isclose(db.dbw_to_watt(db.watt_to_dbw(w)), w, rel_tol=1e-12)


@given(pos)
def test_watt_dbm_round_trip(w: float) -> None:
    assert math.isclose(db.dbm_to_watt(db.watt_to_dbm(w)), w, rel_tol=1e-12)


@given(dbs)
def test_dbw_dbm_offset_is_exactly_30(x: float) -> None:
    assert math.isclose(db.dbw_to_dbm(x) - x, 30.0, abs_tol=1e-9)
    assert math.isclose(db.dbm_to_dbw(db.dbw_to_dbm(x)), x, abs_tol=1e-9)
