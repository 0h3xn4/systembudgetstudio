"""Typed project model (pydantic)."""

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.config import (
    AttenuationEntry,
    AttenuationTable,
    Ebn0Entry,
    Ebn0Table,
    MarginPolicy,
    MaturityClass,
    PowerConfig,
)
from budget_core.model.equipment import Bus, PowerMode, Spacecraft, SpacecraftMode, Unit
from budget_core.model.mass import (
    Expendable,
    Inertia,
    MassLimit,
    MassLimits,
    MassProperties,
    inertia_is_physical,
)
from budget_core.model.project import Project, ProjectConfig, ProjectMeta
from budget_core.model.versions import CURRENT_VERSIONS

__all__ = [
    "CURRENT_VERSIONS",
    "AttenuationEntry",
    "AttenuationTable",
    "BudgetModel",
    "Bus",
    "Ebn0Entry",
    "Ebn0Table",
    "Expendable",
    "Inertia",
    "MassLimit",
    "MassLimits",
    "MassProperties",
    "MarginPolicy",
    "MaturityClass",
    "PowerConfig",
    "PowerMode",
    "Project",
    "ProjectConfig",
    "ProjectMeta",
    "Sourced",
    "Spacecraft",
    "SpacecraftMode",
    "Unit",
    "inertia_is_physical",
]
