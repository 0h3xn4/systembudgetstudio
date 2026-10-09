"""Configuration files: margin policy, power constants, Eb/N0 and attenuation tables.

Every number is a `Sourced` value. Nothing here ships with plausible-looking defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


class MaturityClass(BudgetModel):
    margin_ratio: Sourced
    description: str = ""


class MarginPolicy(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["margin_policy"]
    kind: Literal["margin_policy"] = "margin_policy"
    classes: dict[str, MaturityClass]
    system_margin_ratio: Sourced

    @field_validator("classes")
    @classmethod
    def _sorted(cls, value: dict[str, MaturityClass]) -> dict[str, MaturityClass]:
        return dict(sorted(value.items()))


class PowerConfig(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["power_config"]
    kind: Literal["power_config"] = "power_config"
    distribution_loss_ratio: Sourced
    converter_efficiency_ratio: dict[str, Sourced] = Field(default_factory=dict)

    @field_validator("converter_efficiency_ratio")
    @classmethod
    def _sorted(cls, value: dict[str, Sourced]) -> dict[str, Sourced]:
        return dict(sorted(value.items()))


class Ebn0Entry(BudgetModel):
    modulation: str = Field(min_length=1)
    coding: str = Field(min_length=1)
    required_ebn0_db: Sourced


class Ebn0Table(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["ebn0_table"]
    kind: Literal["ebn0_table"] = "ebn0_table"
    entries: list[Ebn0Entry] = Field(default_factory=list)


class AttenuationEntry(BudgetModel):
    name: str = Field(min_length=1)
    attenuation_kind: Literal["rain", "gas", "cloud", "scintillation", "other"]
    freq_hz: float = Field(gt=0)
    elevation_deg: float | None = Field(default=None, ge=0, le=90)
    loss_db: Sourced


class AttenuationTable(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["attenuation_table"]
    kind: Literal["attenuation_table"] = "attenuation_table"
    entries: list[AttenuationEntry] = Field(default_factory=list)
