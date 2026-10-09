"""Mass properties: positions, inertia tensors, expendables and mass limits (D-048 to D-050).

Frame: one right-handed spacecraft body frame described in `spacecraft.yaml`. Positions are the
item's centre of mass in metres. Inertia entries are tensor entries (Ixy is the tensor element,
equal to minus the product of inertia) about the item's own centre of mass, axes parallel to the
body frame. An item without an inertia is a point mass.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.versions import CURRENT_VERSIONS


def inertia_is_physical(
    ixx: float, iyy: float, izz: float, ixy: float, ixz: float, iyz: float
) -> bool:
    """A rigid body's inertia tensor I satisfies: C = (trace(I) / 2) E - I is positive
    semi-definite (C is the second-moment matrix of the mass distribution). Checked with the
    principal minors of C and a small relative tolerance."""
    half = 0.5 * (ixx + iyy + izz)
    c = ((half - ixx, -ixy, -ixz), (-ixy, half - iyy, -iyz), (-ixz, -iyz, half - izz))
    scale = max(abs(ixx), abs(iyy), abs(izz), 1e-300)
    tol = 1e-9 * scale
    diag = [c[0][0], c[1][1], c[2][2]]
    if any(d < -tol for d in diag):
        return False
    minors = [
        c[0][0] * c[1][1] - c[0][1] ** 2,
        c[0][0] * c[2][2] - c[0][2] ** 2,
        c[1][1] * c[2][2] - c[1][2] ** 2,
    ]
    if any(m < -tol * scale for m in minors):
        return False
    det = (
        c[0][0] * (c[1][1] * c[2][2] - c[1][2] ** 2)
        - c[0][1] * (c[0][1] * c[2][2] - c[1][2] * c[0][2])
        + c[0][2] * (c[0][1] * c[1][2] - c[1][1] * c[0][2])
    )
    return det >= -tol * scale * scale


class Inertia(BudgetModel):
    ixx_kgm2: float = Field(ge=0)
    iyy_kgm2: float = Field(ge=0)
    izz_kgm2: float = Field(ge=0)
    ixy_kgm2: float = 0.0
    ixz_kgm2: float = 0.0
    iyz_kgm2: float = 0.0

    @model_validator(mode="after")
    def _physical(self) -> Inertia:
        if not inertia_is_physical(
            self.ixx_kgm2,
            self.iyy_kgm2,
            self.izz_kgm2,
            self.ixy_kgm2,
            self.ixz_kgm2,
            self.iyz_kgm2,
        ):
            raise PydanticCustomError(
                "inertia_not_physical",
                "these inertia entries cannot belong to a rigid body "
                "(check the diagonal entries against the triangle inequality and the products)",
                {"field": "ixx_kgm2"},
            )
        return self


class MassProperties(BudgetModel):
    """Centre-of-mass position (body frame, metres) and optional own inertia of one item."""

    position_m: list[float] = Field(min_length=3, max_length=3)
    inertia: Inertia | None = None


def _unique_phases(phases: list[str]) -> list[str]:
    if len(set(phases)) != len(phases):
        raise PydanticCustomError("duplicate_name", "phase names must be unique")
    return phases


class Expendable(BudgetModel):
    """Propellant, consumables or jettisoned equipment: mass differs per mission phase."""

    schema_version: int = CURRENT_VERSIONS["expendable"]
    kind: Literal["expendable"] = "expendable"
    name: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    maturity: str = Field(min_length=1)
    masses_kg: dict[str, float]
    mass_properties: MassProperties | None = None

    @field_validator("masses_kg")
    @classmethod
    def _non_negative(cls, value: dict[str, float]) -> dict[str, float]:
        if any(m < 0 for m in value.values()):
            raise PydanticCustomError("negative_mass", "masses must not be negative")
        return dict(sorted(value.items()))


class MassLimit(BudgetModel):
    name: str = Field(min_length=1)
    phase: str | None = None  # None: applies to every phase
    limit_kg: Sourced


class MassLimits(BudgetModel):
    schema_version: int = CURRENT_VERSIONS["mass_limits"]
    kind: Literal["mass_limits"] = "mass_limits"
    limits: list[MassLimit] = Field(default_factory=list)
