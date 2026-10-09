"""Spacecraft, units, power modes and spacecraft modes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, duplicate_names
from budget_core.model.versions import CURRENT_VERSIONS


class PowerMode(BudgetModel):
    """One power mode of a unit.

    `avg_power_w` is the average power drawn while the unit is in this mode and switched on;
    the effective average is `avg_power_w * duty_cycle_ratio` (decision D-024).
    """

    name: str = Field(min_length=1)
    avg_power_w: float = Field(ge=0)
    peak_power_w: float = Field(ge=0)
    duty_cycle_ratio: float = Field(default=1.0, ge=0, le=1)
    min_duration_s: float | None = Field(default=None, gt=0)
    max_duration_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check(self) -> PowerMode:
        if self.peak_power_w < self.avg_power_w:
            raise PydanticCustomError(
                "peak_below_average",
                "peak power must not be below average power",
                {"field": "peak_power_w"},
            )
        if (
            self.min_duration_s is not None
            and self.max_duration_s is not None
            and self.min_duration_s > self.max_duration_s
        ):
            raise PydanticCustomError(
                "duration_order",
                "minimum duration must not exceed maximum duration",
                {"field": "min_duration_s"},
            )
        return self


class Unit(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["unit"]
    kind: Literal["unit"] = "unit"
    name: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    mass_kg: float = Field(ge=0)
    bus: str = Field(min_length=1)
    maturity: str = Field(min_length=1)
    catalogue_ref: str | None = None  # reserved for the shared catalogue (decision D-009)
    modes: list[PowerMode] = Field(min_length=1)

    @field_validator("modes")
    @classmethod
    def _unique_modes(cls, modes: list[PowerMode]) -> list[PowerMode]:
        if duplicate_names([m.name for m in modes]):
            raise PydanticCustomError("duplicate_name", "mode names must be unique within a unit")
        return modes


class SpacecraftMode(BudgetModel):
    """A spacecraft mode maps unit ids (file names in units/) to one of their power modes."""

    schema_version: int = CURRENT_VERSIONS["spacecraft_mode"]
    kind: Literal["spacecraft_mode"] = "spacecraft_mode"
    name: str = Field(min_length=1)
    description: str = ""
    assignments: dict[str, str] = Field(min_length=1)

    @field_validator("assignments")
    @classmethod
    def _sorted(cls, value: dict[str, str]) -> dict[str, str]:
        return dict(sorted(value.items()))


class Bus(BudgetModel):
    name: str = Field(min_length=1)
    nominal_voltage_v: float = Field(gt=0)


class Spacecraft(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["spacecraft"]
    kind: Literal["spacecraft"] = "spacecraft"
    name: str = Field(min_length=1)
    buses: list[Bus] = Field(min_length=1)

    @field_validator("buses")
    @classmethod
    def _unique_buses(cls, buses: list[Bus]) -> list[Bus]:
        if duplicate_names([b.name for b in buses]):
            raise PydanticCustomError("duplicate_name", "bus names must be unique")
        return buses
