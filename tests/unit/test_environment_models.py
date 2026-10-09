"""Orbit, site and scenario models, time parsing and the scenario file layer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from budget_core.model import GroundStation, Orbit, Scenario, Target
from budget_core.timeutil import format_utc, normalise_utc, parse_utc

# International Space Station element set from the sgp4 library documentation (public).
TLE = [
    "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
    "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
]
ELEMENTS = {
    "epoch_utc": "2026-01-01T00:00:00Z",
    "semi_major_axis_m": 6878137.0,
    "eccentricity_ratio": 0.001,
    "inclination_deg": 51.6,
    "raan_deg": 10.0,
    "arg_perigee_deg": 20.0,
    "mean_anomaly_deg": 30.0,
}


def scenario(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Day",
        "orbit": "leo",
        "start_utc": "2026-01-01T00:00:00Z",
        "duration_s": 86400,
        "step_s": 10,
        "default_mode": "nominal",
    }
    return {**base, **kw}


def errors(exc: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple[Any, ...], str]]:
    out = []
    for e in exc.value.errors():
        loc = tuple(e["loc"]) + ((e["ctx"]["field"],) if "field" in (e.get("ctx") or {}) else ())
        out.append((loc, e["type"]))
    return out


# ---- time -------------------------------------------------------------------------------------


def test_utc_parsing_and_formatting() -> None:
    assert parse_utc("2026-01-02T03:04:05Z") == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert parse_utc("2026-01-02 03:04:05") == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert parse_utc("2026-01-02T03:04:05.250Z").microsecond == 250000
    assert format_utc(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == "2026-01-02T03:04:05Z"
    assert normalise_utc("2026-01-02 03:04:05") == "2026-01-02T03:04:05Z"


@pytest.mark.parametrize(
    "bad", ["yesterday", "2026-13-01T00:00:00Z", "2026-01-01T00:00:00+02:00", ""]
)
def test_utc_rejects_garbage_and_other_time_zones(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_utc(bad)


# ---- orbit ------------------------------------------------------------------------------------


def test_orbit_from_tle_or_elements() -> None:
    assert Orbit.model_validate({"name": "ISS", "tle": TLE}).tle == TLE
    o = Orbit.model_validate({"name": "LEO", "elements": ELEMENTS})
    assert o.elements is not None and o.elements.epoch_utc == "2026-01-01T00:00:00Z"


def test_orbit_needs_exactly_one_source() -> None:
    with pytest.raises(ValidationError) as exc:
        Orbit.model_validate({"name": "X"})
    assert (("tle",), "orbit_source") in errors(exc)
    with pytest.raises(ValidationError):
        Orbit.model_validate({"name": "X", "tle": TLE, "elements": ELEMENTS})


@pytest.mark.parametrize(
    "tle",
    [
        [TLE[0]],  # one line
        [TLE[0], TLE[1][:-1]],  # short line
        [TLE[0][:-1] + "0", TLE[1]],  # bad checksum
        [TLE[1], TLE[0]],  # swapped
    ],
)
def test_tle_lines_are_checked(tle: list[str]) -> None:
    with pytest.raises(ValidationError):
        Orbit.model_validate({"name": "X", "tle": tle})


@pytest.mark.parametrize(
    "change",
    [
        {"semi_major_axis_m": 0},
        {"eccentricity_ratio": 1.0},
        {"eccentricity_ratio": -0.1},
        {"inclination_deg": 181},
        {"raan_deg": 360},
        {"epoch_utc": "never"},
        {"semi_major_axis_m": "3 dBW"},
    ],
)
def test_element_ranges(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Orbit.model_validate({"name": "X", "elements": {**ELEMENTS, **change}})


def test_elements_accept_units() -> None:
    o = Orbit.model_validate(
        {"name": "X", "elements": {**ELEMENTS, "semi_major_axis_m": "6878.137 km"}}
    )
    assert o.elements is not None and o.elements.semi_major_axis_m == pytest.approx(6878137.0)


# ---- sites ------------------------------------------------------------------------------------

SITE = {
    "name": "GS",
    "latitude_deg": 60.0,
    "longitude_deg": 10.0,
    "altitude_m": 100.0,
    "min_elevation_deg": 5.0,
}


def test_sites() -> None:
    assert GroundStation.model_validate(SITE).kind == "ground_station"
    assert Target.model_validate(SITE).kind == "target"


@pytest.mark.parametrize(
    "change",
    [
        {"latitude_deg": 91},
        {"longitude_deg": 181},
        {"min_elevation_deg": 90},
        {"min_elevation_deg": -1},
        {"altitude_m": -5000},
    ],
)
def test_site_ranges(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GroundStation.model_validate({**SITE, **change})


def test_site_needs_a_minimum_elevation() -> None:
    bad = {k: v for k, v in SITE.items() if k != "min_elevation_deg"}
    with pytest.raises(ValidationError) as exc:
        GroundStation.model_validate(bad)
    assert (("min_elevation_deg",), "missing") in errors(exc)


# ---- scenario ---------------------------------------------------------------------------------


def test_scenario_defaults_and_normalised_start() -> None:
    s = Scenario.model_validate(scenario(start_utc="2026-01-01 00:00:00"))
    assert s.start_utc == "2026-01-01T00:00:00Z" and s.shadow_model == "cylindrical"
    assert s.environment_source == "elements" and s.rules == [] and s.segments == []


def test_scenario_source_rules() -> None:
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate({k: v for k, v in scenario().items() if k != "orbit"})
    assert (("orbit",), "scenario_source") in errors(exc)
    ok = Scenario.model_validate(
        {
            **{k: v for k, v in scenario().items() if k != "orbit"},
            "environment_source": "spacemissionstudio",
            "import_dir": "imports/run1",
        }
    )
    assert ok.import_dir == "imports/run1"
    with pytest.raises(ValidationError):
        Scenario.model_validate({**scenario(), "environment_source": "spacemissionstudio"})


def test_scenario_step_and_size_limits() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario(step_s=100000))  # step longer than the scenario
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(scenario(duration_s=86400 * 400, step_s=1))
    assert (("step_s",), "scenario_too_large") in errors(exc)
    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario(duration_s=0))


def test_rules() -> None:
    s = Scenario.model_validate(
        scenario(
            sites=["gs"],
            rules=[
                {
                    "kind": "during_pass",
                    "site": "gs",
                    "mode": "downlink",
                    "lead_s": 30,
                    "lag_s": 10,
                },
                {"kind": "in_eclipse", "mode": "safe"},
                {"kind": "in_sunlight", "mode": "charging"},
            ],
        )
    )
    assert [r.kind for r in s.rules] == ["during_pass", "in_eclipse", "in_sunlight"]
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(scenario(rules=[{"kind": "during_pass", "mode": "downlink"}]))
    assert any(t == "rule_site" for _, t in errors(exc))
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            scenario(rules=[{"kind": "in_eclipse", "site": "gs", "mode": "safe"}])
        )
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            scenario(rules=[{"kind": "in_eclipse", "mode": "safe", "lead_s": -1}])
        )
    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario(rules=[{"kind": "bogus", "mode": "safe"}]))


def test_segments_must_fit_and_not_overlap() -> None:
    ok = Scenario.model_validate(
        scenario(
            segments=[
                {"start_s": 0, "duration_s": 100, "mode": "safe"},
                {"start_s": 100, "duration_s": 50, "mode": "imaging"},
            ]
        )
    )
    assert len(ok.segments) == 2
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(
            scenario(
                segments=[
                    {"start_s": 0, "duration_s": 100, "mode": "safe"},
                    {"start_s": 50, "duration_s": 100, "mode": "imaging"},
                ]
            )
        )
    assert (("segments",), "segments_overlap") in errors(exc)
    with pytest.raises(ValidationError) as exc2:
        Scenario.model_validate(
            scenario(segments=[{"start_s": 86000, "duration_s": 1000, "mode": "x"}])
        )
    assert (("segments",), "segment_outside") in errors(exc2)
    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario(segments=[{"start_s": -1, "duration_s": 10, "mode": "x"}]))


def test_site_list_unique() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate(scenario(sites=["a", "a"]))
