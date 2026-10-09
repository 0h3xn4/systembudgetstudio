"""Thermal model and environment cases for the steady-state budget (decisions D-071 to D-075).

Every number that comes from a source (optical properties, fluxes, conductances, margins) is a
`Sourced` value; nothing here has a default that looks like data. A node is an isothermal lump;
units sit on nodes (`Unit.thermal_node`, default: the node named like the unit's subsystem).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class ThermalNode(BudgetModel):
    name: str = Field(min_length=1)
    heat_capacity_jperk: float | None = Field(default=None, gt=0)  # reserved for transient work


class Conductance(BudgetModel):
    """Linear conduction between two nodes: heat flow = conductance * (T_a - T_b)."""

    first_node: str = Field(min_length=1)
    second_node: str = Field(min_length=1)
    conductance_wk: Sourced

    @model_validator(mode="after")
    def _two_nodes(self) -> Conductance:
        if self.first_node == self.second_node:
            raise PydanticCustomError(
                "conductance_nodes", "a conductance connects two different nodes"
            )
        return self


class Exposure(BudgetModel):
    """The share of a surface that sees the Sun, and the share that sees the Earth, in one case."""

    solar_view_ratio: Sourced
    earth_view_ratio: Sourced


class Surface(BudgetModel):
    """An outer surface of a node: radiates to space, absorbs sunlight, albedo, Earth infrared."""

    name: str = Field(min_length=1)
    node: str = Field(min_length=1)
    area_m2: float = Field(gt=0)
    emissivity_ratio: Sourced  # infrared
    absorptivity_ratio: Sourced  # solar
    exposure: dict[str, Exposure] = Field(default_factory=dict)  # by case name

    @field_validator("exposure")
    @classmethod
    def _sorted(cls, value: dict[str, Exposure]) -> dict[str, Exposure]:
        return dict(sorted(value.items()))


class ThermalModel(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["thermal_model"]
    kind: Literal["thermal_model"] = "thermal_model"
    nodes: dict[str, ThermalNode] = Field(min_length=1)
    conductances: list[Conductance] = Field(default_factory=list)
    surfaces: list[Surface] = Field(default_factory=list)

    @field_validator("nodes")
    @classmethod
    def _sorted_nodes(cls, value: dict[str, ThermalNode]) -> dict[str, ThermalNode]:
        return dict(sorted(value.items()))


class ThermalCase(BudgetModel):
    """A named load case (for example hot or cold): which spacecraft mode dissipates, and the
    environment. `limit_set` chooses the unit temperature limits the result is checked against."""

    description: str = ""
    spacecraft_mode: str = Field(min_length=1)
    limit_set: Literal["operating", "survival"] = "operating"
    solar_flux_wm2: Sourced
    albedo_ratio: Sourced
    earth_ir_wm2: Sourced


class ThermalEnvironment(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["thermal_environment"]
    kind: Literal["thermal_environment"] = "thermal_environment"
    space_temperature_k: Sourced
    temperature_margin_k: Sourced  # required headroom to the unit limits
    cases: dict[str, ThermalCase] = Field(default_factory=dict)

    @field_validator("cases")
    @classmethod
    def _sorted_cases(cls, value: dict[str, ThermalCase]) -> dict[str, ThermalCase]:
        return dict(sorted(value.items()))
