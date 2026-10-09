"""Centre of gravity and inertia of a set of rigid items (pure functions, plain floats).

Conventions (decision D-048): positions in metres in one body frame; inertia entries are tensor
entries (Ixy is the tensor element = minus the product of inertia). Sums use `math.fsum` so
results do not depend on summation order noise.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Tensor:
    """Symmetric inertia tensor entries in kg m2."""

    ixx: float
    iyy: float
    izz: float
    ixy: float
    ixz: float
    iyz: float

    def entries(self) -> tuple[float, float, float, float, float, float]:
        return (self.ixx, self.iyy, self.izz, self.ixy, self.ixz, self.iyz)


ZERO = Tensor(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class MassItem:
    mass: float
    position: Vec3
    inertia: Tensor | None  # about the item's own centre of mass; None means a point mass


def center_of_gravity(items: Sequence[tuple[float, Vec3]]) -> tuple[float, Vec3] | None:
    """MASS-COG: (total mass, centre of gravity) of (mass, position) pairs, None for zero mass."""
    total = math.fsum(m for m, _ in items)
    if total <= 0.0:
        return None
    centre = (
        math.fsum(m * p[0] for m, p in items) / total,
        math.fsum(m * p[1] for m, p in items) / total,
        math.fsum(m * p[2] for m, p in items) / total,
    )
    return total, centre


def parallel_axis(own: Tensor, mass: float, d: Vec3) -> Tensor:
    """MASS-PARALLEL: inertia of an item about a point offset by d from its own centre of mass,
    I = I_own + m (|d|^2 E - d d^T) (Huygens-Steiner theorem)."""
    dx, dy, dz = d
    d2 = dx * dx + dy * dy + dz * dz
    return Tensor(
        own.ixx + mass * (d2 - dx * dx),
        own.iyy + mass * (d2 - dy * dy),
        own.izz + mass * (d2 - dz * dz),
        own.ixy - mass * dx * dy,
        own.ixz - mass * dx * dz,
        own.iyz - mass * dy * dz,
    )


def inertia_about(point: Vec3, items: Sequence[MassItem]) -> Tensor:
    """Total inertia tensor of all items about `point`."""
    parts = [
        parallel_axis(
            item.inertia or ZERO,
            item.mass,
            (item.position[0] - point[0], item.position[1] - point[1], item.position[2] - point[2]),
        )
        for item in items
    ]
    columns = list(zip(*(t.entries() for t in parts), strict=True)) if parts else [()] * 6
    ixx, iyy, izz, ixy, ixz, iyz = (math.fsum(c) for c in columns)
    return Tensor(ixx, iyy, izz, ixy, ixz, iyz)
