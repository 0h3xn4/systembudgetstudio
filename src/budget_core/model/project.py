"""Project metadata and the loaded project aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field

from budget_core.model.base import BudgetModel
from budget_core.model.config import AttenuationTable, Ebn0Table, MarginPolicy, PowerConfig
from budget_core.model.equipment import Spacecraft, SpacecraftMode, Unit
from budget_core.model.versions import CURRENT_VERSIONS


class ProjectMeta(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["project"]
    kind: Literal["project"] = "project"
    name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    description: str = ""


@dataclass(frozen=True)
class ProjectConfig:
    margin_policy: MarginPolicy | None = None
    power_config: PowerConfig | None = None
    ebn0_table: Ebn0Table | None = None
    attenuation_table: AttenuationTable | None = None


@dataclass(frozen=True)
class Project:
    root: Path
    meta: ProjectMeta
    spacecraft: Spacecraft
    units: dict[str, Unit] = field(default_factory=dict)
    modes: dict[str, SpacecraftMode] = field(default_factory=dict)
    config: ProjectConfig = field(default_factory=ProjectConfig)
