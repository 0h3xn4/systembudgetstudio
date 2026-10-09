"""Static mass budget per mission phase: roll-up with margins, limits, centre of gravity, inertia.

Conventions are in docs/DECISIONS.md (D-048 to D-050) and `budget_core.equations`. A placeholder
or missing number gives `None` (n/a) in every result that needs it, never zero. CG and inertia use
nominal masses of items that have a position; the others are excluded and reported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from budget_core.assumptions import Assumption, incomplete
from budget_core.mass.mass_properties import (
    MassItem,
    Tensor,
    Vec3,
    center_of_gravity,
    inertia_about,
)
from budget_core.model import MassLimits, MassProperties, Project, Sourced
from budget_core.problems import Problem, Severity

LimitStatus = Literal["ok", "exceeded", "n/a"]


def margined_mass_kg(mass_kg: float, margin_ratio: float | None) -> float | None:
    """MASS-MARGIN; None when the margin is unavailable."""
    return None if margin_ratio is None else mass_kg * (1.0 + margin_ratio)


@dataclass(frozen=True)
class MassRow:
    item_id: str
    name: str
    kind: Literal["unit", "expendable"]
    subsystem: str
    maturity: str
    mass_kg: float
    margin_ratio: float | None
    margined_mass_kg: float | None
    position_m: Vec3 | None
    own_inertia: Tensor | None

    @property
    def has_inertia(self) -> bool:
        return self.own_inertia is not None

    @property
    def file(self) -> str:
        return f"{'units' if self.kind == 'unit' else 'expendables'}/{self.item_id}.yaml"


@dataclass(frozen=True)
class SubsystemMass:
    subsystem: str
    mass_kg: float
    margined_kg: float | None


@dataclass(frozen=True)
class LimitCheck:
    name: str
    limit_kg: float | None
    total_kg: float | None  # the system-margined total the limit is checked against
    margin_kg: float | None
    status: LimitStatus


@dataclass(frozen=True)
class CogResult:
    position_m: Vec3
    mass_kg: float  # nominal mass of the items that entered the calculation
    coverage_ratio: float  # that mass over the phase's nominal total
    excluded_ids: tuple[str, ...]  # items without a position
    point_mass_ids: tuple[str, ...]  # items with a position but no own inertia
    inertia_cg: Tensor
    inertia_origin: Tensor


@dataclass(frozen=True)
class PhaseMass:
    phase: str
    rows: tuple[MassRow, ...]
    subsystems: tuple[SubsystemMass, ...]
    total_kg: float
    unit_margined_kg: float | None
    system_margined_kg: float | None
    limits: tuple[LimitCheck, ...]
    cog: CogResult | None


@dataclass(frozen=True)
class StaticMassResult:
    phases: tuple[PhaseMass, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def _sum_opt(values: list[float | None]) -> float | None:
    return None if any(v is None for v in values) else math.fsum(v for v in values if v is not None)


def _position(props: MassProperties | None) -> Vec3 | None:
    if props is None:
        return None
    x, y, z = props.position_m
    return (x, y, z)


def _tensor(props: MassProperties | None) -> Tensor | None:
    if props is None or props.inertia is None:
        return None
    i = props.inertia
    return Tensor(i.ixx_kgm2, i.iyy_kgm2, i.izz_kgm2, i.ixy_kgm2, i.ixz_kgm2, i.iyz_kgm2)


def static_mass_budget(project: Project) -> StaticMassResult:
    """Compute mass, CG and inertia for every mission phase. The project must be valid."""
    policy = project.config.margin_policy
    system_margin = _value(policy.system_mass_margin_ratio) if policy else None

    def class_margin(maturity: str) -> float | None:
        if policy is None or maturity not in policy.classes:
            return None
        return _value(policy.classes[maturity].mass_margin_ratio)

    phases: list[PhaseMass] = []
    for phase in project.phases:
        rows: list[MassRow] = []
        for uid in sorted(project.units):
            unit = project.units[uid]
            if unit.phases is not None and phase not in unit.phases:
                continue
            margin = class_margin(unit.maturity)
            props = unit.mass_properties
            rows.append(
                MassRow(
                    uid,
                    unit.name,
                    "unit",
                    unit.subsystem,
                    unit.maturity,
                    unit.mass_kg,
                    margin,
                    margined_mass_kg(unit.mass_kg, margin),
                    _position(props),
                    _tensor(props),
                )
            )
        for eid in sorted(project.expendables):
            exp = project.expendables[eid]
            mass = exp.masses_kg[phase]
            margin = class_margin(exp.maturity)
            props = exp.mass_properties
            rows.append(
                MassRow(
                    eid,
                    exp.name,
                    "expendable",
                    exp.subsystem,
                    exp.maturity,
                    mass,
                    margin,
                    margined_mass_kg(mass, margin),
                    _position(props),
                    _tensor(props),
                )
            )

        total = math.fsum(r.mass_kg for r in rows)
        unit_margined = _sum_opt([r.margined_mass_kg for r in rows])
        system_margined = (
            None
            if unit_margined is None or system_margin is None
            else unit_margined * (1.0 + system_margin)
        )
        subsystems = tuple(
            SubsystemMass(
                name,
                math.fsum(r.mass_kg for r in rows if r.subsystem == name),
                _sum_opt([r.margined_mass_kg for r in rows if r.subsystem == name]),
            )
            for name in sorted({r.subsystem for r in rows})
        )
        phases.append(
            PhaseMass(
                phase=phase,
                rows=tuple(rows),
                subsystems=subsystems,
                total_kg=total,
                unit_margined_kg=unit_margined,
                system_margined_kg=system_margined,
                limits=_limit_checks(project.config.mass_limits, phase, system_margined),
                cog=_cog(rows, total),
            )
        )

    assumptions, problems = _assumptions(project)
    problems += _property_problems(phases)
    problems += _limit_problems(project.config.mass_limits, phases)
    return StaticMassResult(tuple(phases), tuple(assumptions), tuple(problems))


def _cog(rows: list[MassRow], total: float) -> CogResult | None:
    placed = [r for r in rows if r.position_m is not None and r.mass_kg > 0.0]
    items = [MassItem(r.mass_kg, r.position_m, r.own_inertia) for r in placed if r.position_m]
    found = center_of_gravity([(i.mass, i.position) for i in items])
    if found is None:
        return None
    included, centre = found
    return CogResult(
        position_m=centre,
        mass_kg=included,
        coverage_ratio=included / total if total > 0.0 else 0.0,
        excluded_ids=tuple(r.item_id for r in rows if r.position_m is None and r.mass_kg > 0.0),
        point_mass_ids=tuple(r.item_id for r in placed if r.own_inertia is None),
        inertia_cg=inertia_about(centre, items),
        inertia_origin=inertia_about((0.0, 0.0, 0.0), items),
    )


def _limit_checks(
    limits: MassLimits | None, phase: str, system_margined_kg: float | None
) -> tuple[LimitCheck, ...]:
    checks: list[LimitCheck] = []
    for limit in limits.limits if limits else []:
        if limit.phase is not None and limit.phase != phase:
            continue
        value = _value(limit.limit_kg)
        if value is None or system_margined_kg is None:
            checks.append(LimitCheck(limit.name, value, system_margined_kg, None, "n/a"))
            continue
        margin = value - system_margined_kg
        checks.append(
            LimitCheck(
                limit.name, value, system_margined_kg, margin, "ok" if margin >= 0 else "exceeded"
            )
        )
    return tuple(checks)


def _limit_problems(limits: MassLimits | None, phases: list[PhaseMass]) -> list[Problem]:
    out: list[Problem] = []
    names = [lim.name for lim in limits.limits] if limits else []
    for phase in phases:
        for check in phase.limits:
            if check.status == "exceeded":
                index = names.index(check.name)
                out.append(
                    Problem(
                        Severity.ERROR,
                        "MASS_LIMIT_EXCEEDED",
                        f"Mass limit '{check.name}' is exceeded in phase '{phase.phase}'.",
                        file="config/mass_limits.yaml",
                        path=f"limits[{index}]",
                        hint="Reduce mass, change the limit (cite its source) or review margins.",
                    )
                )
    return out


def _property_problems(phases: list[PhaseMass]) -> list[Problem]:
    seen_missing: set[str] = set()
    seen_point: set[str] = set()
    out: list[Problem] = []
    for phase in phases:
        for row in phase.rows:
            if row.mass_kg <= 0.0:
                continue
            if row.position_m is None and row.file not in seen_missing:
                seen_missing.add(row.file)
                out.append(
                    Problem(
                        Severity.WARNING,
                        "MASS_PROPS_MISSING",
                        f"'{row.item_id}' has no position; it is excluded from the centre of "
                        "gravity and inertia (never counted as zero position).",
                        file=row.file,
                        path="mass_properties",
                        hint="Add mass_properties with position_m: [x, y, z] in the body frame.",
                    )
                )
            elif (
                row.position_m is not None
                and row.own_inertia is None
                and row.file not in seen_point
            ):
                seen_point.add(row.file)
                out.append(
                    Problem(
                        Severity.INFO,
                        "MASS_INERTIA_POINT_MASS",
                        f"'{row.item_id}' has no own inertia; it is treated as a point mass.",
                        file=row.file,
                        path="mass_properties",
                    )
                )
    return out


def _assumptions(project: Project) -> tuple[list[Assumption], list[Problem]]:
    policy = project.config.margin_policy
    out: list[Assumption] = []
    problems: list[Problem] = []

    def add(name: str, item: Sourced | None, file: str, path: str, what: str) -> None:
        if item is None:
            out.append(
                Assumption(
                    name, None, "ratio" if "margin" in path else "kg", "missing", file, path, True
                )
            )
            problems.append(incomplete(f"{what} is missing ({file} not provided).", file, path))
            return
        unit = "ratio" if "margin" in path else "kg"
        out.append(Assumption(name, item.value, unit, item.source, file, path, item.is_placeholder))
        if item.is_placeholder:
            problems.append(incomplete(f"{what} is a placeholder.", file, path))

    used = sorted(
        {u.maturity for u in project.units.values()}
        | {e.maturity for e in project.expendables.values()}
    )
    mfile = "config/margin_policy.yaml"
    for cls in used:
        entry = policy.classes.get(cls) if policy else None
        add(
            f"Mass margin, maturity class {cls}",
            entry.mass_margin_ratio if entry else None,
            mfile,
            f"classes.{cls}.mass_margin_ratio",
            f"The mass margin of maturity class '{cls}'",
        )
    add(
        "System mass margin",
        policy.system_mass_margin_ratio if policy else None,
        mfile,
        "system_mass_margin_ratio",
        "The system mass margin",
    )
    limits = project.config.mass_limits
    for index, limit in enumerate(limits.limits if limits else []):
        add(
            f"Mass limit, {limit.name}",
            limit.limit_kg,
            "config/mass_limits.yaml",
            f"limits[{index}].limit_kg",
            f"The mass limit '{limit.name}'",
        )
    return out, problems
