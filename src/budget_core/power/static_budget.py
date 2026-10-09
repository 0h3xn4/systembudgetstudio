"""Static (orbit-less) power budget per spacecraft mode with margins and losses.

Conventions are listed in docs/DECISIONS.md D-040 and in `budget_core.equations`. A number that
is a placeholder (null value or source TBD) or missing makes every result that needs it `None`
("n/a"); it is never replaced by zero.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from budget_core.model import Project, Sourced
from budget_core.problems import Problem, Severity

# ---- scalar building blocks (pure) ----------------------------------------------------------


def effective_power_w(avg_power_w: float, duty_cycle_ratio: float) -> float:
    """PWR-EFF."""
    return avg_power_w * duty_cycle_ratio


def with_margin_w(power_w: float, margin_ratio: float | None) -> float | None:
    """PWR-MARGIN; None when the margin is unavailable."""
    return None if margin_ratio is None else power_w * (1.0 + margin_ratio)


def source_power_w(
    load_w: float | None, efficiency_ratio: float | None, distribution_loss_ratio: float | None
) -> float | None:
    """PWR-SOURCE; None when any input is unavailable."""
    if load_w is None or efficiency_ratio is None or distribution_loss_ratio is None:
        return None
    if not 0.0 < efficiency_ratio <= 1.0 or not 0.0 <= distribution_loss_ratio < 1.0:
        raise ValueError("efficiency must be in (0, 1] and distribution loss in [0, 1)")
    return load_w / (efficiency_ratio * (1.0 - distribution_loss_ratio))


def _sum(values: Iterable[float]) -> float:
    return math.fsum(values)


def _sum_opt(values: Iterable[float | None]) -> float | None:
    items = list(values)
    return None if any(v is None for v in items) else math.fsum(v for v in items if v is not None)


# ---- result types --------------------------------------------------------------------------


@dataclass(frozen=True)
class Flow:
    """One power quantity (average or peak) along the chain unit -> margins -> source."""

    load_w: float
    unit_margined_w: float | None
    system_margined_w: float | None
    source_w: float | None
    source_margined_w: float | None


@dataclass(frozen=True)
class UnitPowerRow:
    unit_id: str
    unit_name: str
    subsystem: str
    bus: str
    maturity: str
    power_mode: str
    avg_power_w: float
    duty_cycle_ratio: float
    effective_power_w: float
    peak_power_w: float
    margin_ratio: float | None
    margined_power_w: float | None
    margined_peak_w: float | None


@dataclass(frozen=True)
class SubsystemPower:
    subsystem: str
    effective_w: float
    margined_w: float | None
    peak_w: float
    margined_peak_w: float | None


@dataclass(frozen=True)
class BusPower:
    bus: str
    converter_efficiency_ratio: float | None
    average: Flow
    peak: Flow


@dataclass(frozen=True)
class ModePowerResult:
    mode_id: str
    mode_name: str
    rows: tuple[UnitPowerRow, ...]
    subsystems: tuple[SubsystemPower, ...]
    buses: tuple[BusPower, ...]
    average: Flow
    peak: Flow


@dataclass(frozen=True)
class Assumption:
    """A configuration number used by the budget, with its source and placeholder status."""

    name: str
    value: float | None
    unit: str
    source: str
    file: str
    path: str
    placeholder: bool


@dataclass(frozen=True)
class StaticPowerResult:
    modes: tuple[ModePowerResult, ...]
    assumptions: tuple[Assumption, ...]
    problems: tuple[Problem, ...]


# ---- inputs from the project ----------------------------------------------------------------


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def _flow(
    load: float,
    unit_margined: float | None,
    system_margin: float | None,
    efficiency: float | None,
    loss: float | None,
) -> Flow:
    system_margined = (
        None
        if unit_margined is None or system_margin is None
        else unit_margined * (1.0 + system_margin)
    )
    return Flow(
        load_w=load,
        unit_margined_w=unit_margined,
        system_margined_w=system_margined,
        source_w=source_power_w(load, efficiency, loss),
        source_margined_w=source_power_w(system_margined, efficiency, loss),
    )


def _combine(flows: list[Flow]) -> Flow:
    return Flow(
        load_w=_sum(f.load_w for f in flows),
        unit_margined_w=_sum_opt(f.unit_margined_w for f in flows),
        system_margined_w=_sum_opt(f.system_margined_w for f in flows),
        source_w=_sum_opt(f.source_w for f in flows),
        source_margined_w=_sum_opt(f.source_margined_w for f in flows),
    )


def _incomplete(message: str, file: str, path: str) -> Problem:
    return Problem(
        Severity.WARNING,
        "RESULT_INCOMPLETE",
        message,
        file=file,
        path=path,
        hint="Replace the placeholder with a sourced value; results that need it show n/a.",
    )


def static_power_budget(project: Project) -> StaticPowerResult:
    """Compute the power table of every spacecraft mode. The project must be valid."""
    policy = project.config.margin_policy
    power = project.config.power_config
    system_margin = _value(policy.system_margin_ratio) if policy else None
    loss = _value(power.distribution_loss_ratio) if power else None

    def class_margin(maturity: str) -> float | None:
        if policy is None or maturity not in policy.classes:
            return None
        return _value(policy.classes[maturity].margin_ratio)

    def efficiency(bus: str) -> float | None:
        if power is None or bus not in power.converter_efficiency_ratio:
            return None
        return _value(power.converter_efficiency_ratio[bus])

    modes: list[ModePowerResult] = []
    for mode_id in sorted(project.modes):
        mode = project.modes[mode_id]
        rows: list[UnitPowerRow] = []
        for uid in sorted(project.units):
            unit = project.units[uid]
            pm = next(m for m in unit.modes if m.name == mode.assignments[uid])
            margin = class_margin(unit.maturity)
            eff = effective_power_w(pm.avg_power_w, pm.duty_cycle_ratio)
            rows.append(
                UnitPowerRow(
                    unit_id=uid,
                    unit_name=unit.name,
                    subsystem=unit.subsystem,
                    bus=unit.bus,
                    maturity=unit.maturity,
                    power_mode=pm.name,
                    avg_power_w=pm.avg_power_w,
                    duty_cycle_ratio=pm.duty_cycle_ratio,
                    effective_power_w=eff,
                    peak_power_w=pm.peak_power_w,
                    margin_ratio=margin,
                    margined_power_w=with_margin_w(eff, margin),
                    margined_peak_w=with_margin_w(pm.peak_power_w, margin),
                )
            )

        subsystems = tuple(
            SubsystemPower(
                subsystem=name,
                effective_w=_sum(r.effective_power_w for r in rows if r.subsystem == name),
                margined_w=_sum_opt(r.margined_power_w for r in rows if r.subsystem == name),
                peak_w=_sum(r.peak_power_w for r in rows if r.subsystem == name),
                margined_peak_w=_sum_opt(r.margined_peak_w for r in rows if r.subsystem == name),
            )
            for name in sorted({r.subsystem for r in rows})
        )

        buses: list[BusPower] = []
        for bus in sorted({r.bus for r in rows}):
            members = [r for r in rows if r.bus == bus]
            eta = efficiency(bus)
            buses.append(
                BusPower(
                    bus=bus,
                    converter_efficiency_ratio=eta,
                    average=_flow(
                        _sum(r.effective_power_w for r in members),
                        _sum_opt(r.margined_power_w for r in members),
                        system_margin,
                        eta,
                        loss,
                    ),
                    peak=_flow(
                        _sum(r.peak_power_w for r in members),
                        _sum_opt(r.margined_peak_w for r in members),
                        system_margin,
                        eta,
                        loss,
                    ),
                )
            )
        modes.append(
            ModePowerResult(
                mode_id=mode_id,
                mode_name=mode.name,
                rows=tuple(rows),
                subsystems=subsystems,
                buses=tuple(buses),
                average=_combine([b.average for b in buses]),
                peak=_combine([b.peak for b in buses]),
            )
        )

    assumptions, problems = _assumptions(project)
    return StaticPowerResult(tuple(modes), tuple(assumptions), tuple(problems))


def _assumptions(project: Project) -> tuple[list[Assumption], list[Problem]]:
    policy = project.config.margin_policy
    power = project.config.power_config
    out: list[Assumption] = []
    problems: list[Problem] = []

    def add(name: str, item: Sourced | None, unit: str, file: str, path: str, what: str) -> None:
        if item is None:
            out.append(Assumption(name, None, unit, "missing", file, path, True))
            problems.append(_incomplete(f"{what} is missing ({file} not provided).", file, path))
            return
        out.append(Assumption(name, item.value, unit, item.source, file, path, item.is_placeholder))
        if item.is_placeholder:
            problems.append(_incomplete(f"{what} is a placeholder.", file, path))

    used_classes = sorted({u.maturity for u in project.units.values()})
    used_buses = sorted({u.bus for u in project.units.values()})
    mfile, pfile = "config/margin_policy.yaml", "config/power_config.yaml"
    for cls in used_classes:
        item = policy.classes.get(cls) if policy else None
        add(
            f"Margin, maturity class {cls}",
            item.margin_ratio if item else None,
            "ratio",
            mfile,
            f"classes.{cls}.margin_ratio",
            f"The margin of maturity class '{cls}'",
        )
    add(
        "System margin",
        policy.system_margin_ratio if policy else None,
        "ratio",
        mfile,
        "system_margin_ratio",
        "The system margin",
    )
    add(
        "Distribution loss",
        power.distribution_loss_ratio if power else None,
        "ratio",
        pfile,
        "distribution_loss_ratio",
        "The distribution loss",
    )
    for bus in used_buses:
        converter = power.converter_efficiency_ratio.get(bus) if power else None
        add(
            f"Converter efficiency, bus {bus}",
            converter,
            "ratio",
            pfile,
            f"converter_efficiency_ratio.{bus}",
            f"The converter efficiency of bus '{bus}'",
        )
    return out, problems
