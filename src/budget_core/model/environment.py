"""Orbit, ground sites and scenarios (decisions D-053 to D-057)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, duplicate_names
from budget_core.model.versions import CURRENT_VERSIONS
from budget_core.timeutil import normalise_utc

MAX_SAMPLES = 1_000_000  # about 11 days at 1 s; a week at 1 s (604,801) is the design case
MAX_RULES = 10_000  # rules and segments per scenario


def _utc(value: str) -> str:
    try:
        return normalise_utc(value)
    except ValueError as exc:
        raise PydanticCustomError("time_invalid", "{reason}", {"reason": str(exc)}) from None


def tle_checksum_ok(line: str) -> bool:
    """TLE checksum: digits summed, each '-' counting 1, modulo 10, over the first 68 characters."""
    total = sum(int(ch) if ch.isdigit() else (1 if ch == "-" else 0) for ch in line[:68])
    return line[68].isdigit() and total % 10 == int(line[68])


class Elements(BudgetModel):
    """Mean orbital elements, used as SGP4 mean elements without drag (DEVIATIONS DV-E2)."""

    epoch_utc: str
    semi_major_axis_m: float = Field(gt=0)
    eccentricity_ratio: float = Field(ge=0, lt=1)
    inclination_deg: float = Field(ge=0, le=180)
    raan_deg: float = Field(ge=0, lt=360)
    arg_perigee_deg: float = Field(ge=0, lt=360)
    mean_anomaly_deg: float = Field(ge=0, lt=360)

    @field_validator("epoch_utc")
    @classmethod
    def _epoch(cls, value: str) -> str:
        return _utc(value)


class Orbit(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["orbit"]
    kind: Literal["orbit"] = "orbit"
    name: str = Field(min_length=1)
    tle: list[str] | None = None
    elements: Elements | None = None

    @field_validator("tle")
    @classmethod
    def _tle(cls, lines: list[str] | None) -> list[str] | None:
        if lines is None:
            return None
        if len(lines) != 2:
            raise PydanticCustomError("tle_invalid", "a TLE has exactly two lines")
        first, second = lines
        if len(first) != 69 or len(second) != 69 or first[0] != "1" or second[0] != "2":
            raise PydanticCustomError(
                "tle_invalid", "TLE lines must be 69 characters, starting with 1 and 2"
            )
        if not (tle_checksum_ok(first) and tle_checksum_ok(second)):
            raise PydanticCustomError("tle_invalid", "a TLE line has a wrong checksum")
        return lines

    @model_validator(mode="after")
    def _one_source(self) -> Orbit:
        if (self.tle is None) == (self.elements is None):
            raise PydanticCustomError(
                "orbit_source",
                "give either 'tle' or 'elements', not both and not neither",
                {"field": "tle"},
            )
        return self


class GroundSite(BudgetModel):
    name: str = Field(min_length=1)
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)
    altitude_m: float = Field(ge=-1000, le=100000)
    min_elevation_deg: float = Field(ge=0, lt=90)  # no default: an operational choice


class GroundStation(GroundSite):
    schema_version: int = CURRENT_VERSIONS["ground_station"]
    kind: Literal["ground_station"] = "ground_station"


class Target(GroundSite):
    """An imaging target: a ground point seen above `min_elevation_deg` counts as a pass."""

    schema_version: int = CURRENT_VERSIONS["target"]
    kind: Literal["target"] = "target"


class ScenarioSegment(BudgetModel):
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    mode: str = Field(min_length=1)


class ScenarioRule(BudgetModel):
    kind: Literal["during_pass", "in_eclipse", "in_sunlight"]
    mode: str = Field(min_length=1)
    site: str | None = None
    lead_s: float = Field(default=0.0, ge=0)  # start the mode this long before a pass
    lag_s: float = Field(default=0.0, ge=0)  # keep it this long after a pass

    @model_validator(mode="after")
    def _site(self) -> ScenarioRule:
        if self.kind == "during_pass" and not self.site:
            raise PydanticCustomError(
                "rule_site", "a during_pass rule needs a site", {"field": "site"}
            )
        if self.kind != "during_pass" and self.site:
            raise PydanticCustomError(
                "rule_site", "only during_pass rules take a site", {"field": "site"}
            )
        if self.kind != "during_pass" and (self.lead_s or self.lag_s):
            raise PydanticCustomError(
                "rule_site", "lead and lag apply only to during_pass rules", {"field": "lead_s"}
            )
        return self


class Scenario(BudgetModel):
    """Parameters of a scenario; computed results are never stored in the project (D-057)."""

    schema_version: int = CURRENT_VERSIONS["scenario"]
    kind: Literal["scenario"] = "scenario"
    name: str = Field(min_length=1)
    description: str = ""
    environment_source: Literal["elements", "spacemissionstudio"] = "elements"
    orbit: str | None = None
    import_dir: str | None = None
    start_utc: str
    duration_s: float = Field(gt=0)
    step_s: float = Field(gt=0)
    shadow_model: Literal["cylindrical", "conical"] = "cylindrical"
    sites: list[str] = Field(default_factory=list)
    mission_phase: str | None = None  # selects the allowed battery depth of discharge
    default_mode: str = Field(min_length=1)
    rules: list[ScenarioRule] = Field(default_factory=list, max_length=MAX_RULES)
    segments: list[ScenarioSegment] = Field(default_factory=list, max_length=MAX_RULES)

    @field_validator("start_utc")
    @classmethod
    def _start(cls, value: str) -> str:
        return _utc(value)

    @field_validator("sites")
    @classmethod
    def _unique_sites(cls, sites: list[str]) -> list[str]:
        if duplicate_names(sites):
            raise PydanticCustomError("duplicate_name", "site ids must be unique")
        return sites

    @model_validator(mode="after")
    def _consistent(self) -> Scenario:
        if self.environment_source == "elements" and not self.orbit:
            raise PydanticCustomError(
                "scenario_source", "an 'elements' environment needs an orbit id", {"field": "orbit"}
            )
        if self.environment_source == "spacemissionstudio" and not self.import_dir:
            raise PydanticCustomError(
                "scenario_source",
                "a spacemissionstudio environment needs import_dir",
                {"field": "import_dir"},
            )
        if self.step_s > self.duration_s:
            raise PydanticCustomError(
                "step_too_long", "the step must not exceed the duration", {"field": "step_s"}
            )
        if self.duration_s / self.step_s + 1 > MAX_SAMPLES:
            raise PydanticCustomError(
                "scenario_too_large", "too many time steps; increase step_s", {"field": "step_s"}
            )
        ordered = sorted(self.segments, key=lambda s: s.start_s)
        for first, second in zip(ordered, ordered[1:], strict=False):
            if first.start_s + first.duration_s > second.start_s + 1e-9:
                raise PydanticCustomError(
                    "segments_overlap", "manual segments must not overlap", {"field": "segments"}
                )
        if any(s.start_s + s.duration_s > self.duration_s + 1e-9 for s in self.segments):
            raise PydanticCustomError(
                "segment_outside",
                "a segment extends beyond the scenario duration",
                {"field": "segments"},
            )
        return self
