"""RF link definitions (decisions D-077 to D-083).

A link joins the spacecraft and one ground station in one direction. Every number from a data
sheet, policy or standard is a `Sourced` value; a placeholder makes the results that need it n/a.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class AntennaPattern(BudgetModel):
    """Gain by angle from the boresight, linearly interpolated (`source: TBD` is a placeholder)."""

    source: str = Field(min_length=1)
    note: str = ""
    angles_deg: list[float] = Field(min_length=2)
    gains_dbi: list[float] = Field(min_length=2)

    @model_validator(mode="after")
    def _table(self) -> AntennaPattern:
        if len(self.angles_deg) != len(self.gains_dbi):
            raise PydanticCustomError(
                "pattern_length", "angles and gains need the same number of entries"
            )
        pairs = list(zip(self.angles_deg, self.angles_deg[1:], strict=False))
        if any(b <= a for a, b in pairs):
            raise PydanticCustomError("pattern_order", "angles must be strictly increasing")
        if self.angles_deg[0] < 0.0 or self.angles_deg[-1] > 180.0:
            raise PydanticCustomError("pattern_range", "angles must lie between 0 and 180 degrees")
        return self

    @property
    def is_placeholder(self) -> bool:
        return self.source.strip().upper() == "TBD"


class Antenna(BudgetModel):
    """Constant gain, a pattern table, or a pattern file (CSV with angle_deg and gain_dbi).

    On the spacecraft the angle is measured from nadir (the boresight points at the Earth's
    centre, DEVIATIONS DV-L2); a ground antenna tracks and has a constant gain."""

    gain_dbi: Sourced | None = None
    pattern: AntennaPattern | None = None
    pattern_file: str | None = None
    pattern_source: str | None = None  # source of the numbers in pattern_file

    @model_validator(mode="after")
    def _one(self) -> Antenna:
        given = [self.gain_dbi is not None, self.pattern is not None, self.pattern_file is not None]
        if sum(given) != 1:
            raise PydanticCustomError(
                "antenna_model",
                "give exactly one of gain_dbi, pattern or pattern_file",
                {"field": "gain_dbi"},
            )
        if self.pattern_file is not None and not self.pattern_source:
            raise PydanticCustomError(
                "antenna_model",
                "a pattern file needs pattern_source (or TBD)",
                {"field": "pattern_source"},
            )
        return self


class Transmitter(BudgetModel):
    power_w: Sourced  # RF output power
    line_loss_db: Sourced  # between the amplifier and the antenna
    antenna: Antenna
    polarisation: str = ""


class Receiver(BudgetModel):
    """Either a given G/T, or an antenna with the system noise temperature and feed loss."""

    antenna: Antenna | None = None
    g_over_t_dbk: Sourced | None = None
    system_noise_temperature_k: Sourced | None = None
    feed_loss_db: Sourced | None = None
    polarisation: str = ""

    @model_validator(mode="after")
    def _figure_of_merit(self) -> Receiver:
        direct = self.g_over_t_dbk is not None
        built = (
            self.antenna is not None
            and self.system_noise_temperature_k is not None
            and self.feed_loss_db is not None
        )
        parts = [self.antenna, self.system_noise_temperature_k, self.feed_loss_db]
        if direct == built or (direct and any(p is not None for p in parts)):
            raise PydanticCustomError(
                "receiver_model",
                "give g_over_t_dbk, or an antenna with system_noise_temperature_k and "
                "feed_loss_db (not both)",
                {"field": "g_over_t_dbk"},
            )
        return self


class StaticPoint(BudgetModel):
    """A chosen elevation and range at which the static link table is evaluated."""

    name: str = Field(min_length=1)
    elevation_deg: float = Field(ge=0, le=90)
    range_m: float = Field(gt=0)


class Link(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["link"]
    kind: Literal["link"] = "link"
    name: str = Field(min_length=1)
    direction: Literal["downlink", "uplink"]
    peer: str | None = None  # ground station id; None: only the static points are evaluated
    frequency_hz: float = Field(gt=0)
    transmitter: Transmitter
    receiver: Receiver
    modulation: str = Field(min_length=1)
    coding: str = Field(min_length=1)
    data_rates_bps: list[float] = Field(min_length=1)
    required_margin_db: Sourced
    pointing_loss_db: Sourced
    polarisation_loss_db: Sourced
    implementation_loss_db: Sourced
    attenuation: list[str] = Field(default_factory=list)  # names in config/attenuation_table
    active_modes: list[str] = Field(default_factory=list)  # empty: every mode
    max_elevation_deg: float | None = Field(default=None, gt=0, le=90)  # tracking limit
    static_points: list[StaticPoint] = Field(default_factory=list)

    @field_validator("data_rates_bps")
    @classmethod
    def _rates(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(r) or r <= 0.0 for r in value):
            raise PydanticCustomError("rate_invalid", "data rates must be positive")
        return sorted(set(value))

    @field_validator("static_points")
    @classmethod
    def _unique_points(cls, value: list[StaticPoint]) -> list[StaticPoint]:
        names = [p.name for p in value]
        if len(set(names)) != len(names):
            raise PydanticCustomError("duplicate_name", "static point names must be unique")
        return value
