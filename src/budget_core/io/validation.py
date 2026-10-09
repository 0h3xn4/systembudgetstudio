"""Cross-file checks: references between files, and configuration gaps (placeholders)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from budget_core.io.yamlio import LineMap, Path, format_path
from budget_core.model import BudgetModel, Project, Sourced
from budget_core.problems import Problem, Severity


def iter_sourced(value: Any, path: Path = ()) -> Iterator[tuple[Path, Sourced]]:
    """Every `Sourced` number inside a config model, with its path."""
    if isinstance(value, Sourced):
        yield path, value
    elif isinstance(value, BudgetModel):
        for name in type(value).model_fields:
            yield from iter_sourced(getattr(value, name), path + (name,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_sourced(item, path + (index,))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_sourced(item, path + (key,))


def _p(
    sev: Severity,
    code: str,
    msg: str,
    file: str,
    path: Path,
    lines: dict[str, LineMap],
    hint: str = "",
) -> Problem:
    line = lines[file].lookup(path) if file in lines else None
    return Problem(sev, code, msg, file=file, path=format_path(path), line=line, hint=hint)


def validate_references(project: Project, lines: dict[str, LineMap]) -> list[Problem]:
    out: list[Problem] = []
    err, warn = Severity.ERROR, Severity.WARNING
    buses = sorted(b.name for b in project.spacecraft.buses)
    policy = project.config.margin_policy

    for uid, unit in project.units.items():
        file = f"units/{uid}.yaml"
        if unit.bus not in buses:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_BUS",
                    "The unit's supply bus is not defined in spacecraft.yaml.",
                    file,
                    ("bus",),
                    lines,
                    "Defined buses: " + ", ".join(buses) + ".",
                )
            )
        if policy is not None and unit.maturity not in policy.classes:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_MATURITY",
                    "The unit's maturity class is not defined in config/margin_policy.yaml.",
                    file,
                    ("maturity",),
                    lines,
                    "Defined classes: " + ", ".join(policy.classes) + ".",
                )
            )

    for mid, mode in project.modes.items():
        file = f"modes/{mid}.yaml"
        for uid, unit_mode in mode.assignments.items():
            target = project.units.get(uid)
            if target is None:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_UNIT",
                        f"Unit '{uid}' does not exist in units/.",
                        file,
                        ("assignments", uid),
                        lines,
                        "Use the file name (without .yaml) of a unit.",
                    )
                )
            elif unit_mode not in {m.name for m in target.modes}:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_UNIT_MODE",
                        f"Unit '{uid}' has no power mode with this name.",
                        file,
                        ("assignments", uid),
                        lines,
                        "Defined modes: " + ", ".join(m.name for m in target.modes) + ".",
                    )
                )
        for uid in sorted(set(project.units) - set(mode.assignments)):
            out.append(
                _p(
                    err,
                    "UNIT_NOT_MAPPED",
                    f"Unit '{uid}' is not assigned a power mode.",
                    file,
                    ("assignments",),
                    lines,
                    f"Add '{uid}: <power mode name>' under assignments.",
                )
            )

    power = project.config.power_config
    if power is not None:
        for bus in power.converter_efficiency_ratio:
            if bus not in buses:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_BUS",
                        f"Converter efficiency given for unknown bus '{bus}'.",
                        "config/power_config.yaml",
                        ("converter_efficiency_ratio", bus),
                        lines,
                        "Defined buses: " + ", ".join(buses) + ".",
                    )
                )

    out.extend(_mass_references(project, lines))
    out.extend(_value_ranges(project, lines))

    for kind in ("margin_policy", "power_config", "ebn0_table", "attenuation_table", "mass_limits"):
        model = getattr(project.config, kind)
        if model is None:
            continue
        file = f"config/{kind}.yaml"
        for path, sourced in iter_sourced(model):
            if sourced.is_placeholder:
                out.append(
                    _p(
                        warn,
                        "CONFIG_PLACEHOLDER",
                        "This number is a placeholder (no value or source 'TBD'); results "
                        "that use it are not trustworthy.",
                        file,
                        path,
                        lines,
                        "Replace it with a value from your margin policy, standard or data "
                        "sheet and cite the source.",
                    )
                )
        if kind == "mass_limits" and not model.limits:
            out.append(
                _p(
                    Severity.WARNING,
                    "CONFIG_EMPTY_TABLE",
                    "The table has no entries.",
                    file,
                    ("limits",),
                    lines,
                    "Add mass limits with their sources (for example launch mass).",
                )
            )
        if kind in ("ebn0_table", "attenuation_table") and not model.entries:
            out.append(
                _p(
                    warn,
                    "CONFIG_EMPTY_TABLE",
                    "The table has no entries.",
                    file,
                    ("entries",),
                    lines,
                    "Add entries from a cited source, or import them from a file.",
                )
            )
    return out


def _range_problem(
    file: str, path: Path, lines: dict[str, LineMap], what: str, allowed: str
) -> Problem:
    line = lines[file].lookup(path + ("value",)) if file in lines else None
    return Problem(
        Severity.ERROR,
        "CONFIG_VALUE_INVALID",
        f"{what} is outside the allowed range {allowed}.",
        file=file,
        path=format_path(path + ("value",)),
        line=line,
        hint="Check the value and its unit; ratios are written as fractions (0.1 means 10 %).",
    )


def _value_ranges(project: Project, lines: dict[str, LineMap]) -> list[Problem]:
    """Placeholders are skipped; real values must be physically meaningful."""
    out: list[Problem] = []

    def check(
        file: str,
        path: Path,
        item: Sourced,
        what: str,
        lo: float,
        hi: float,
        lo_open: bool = False,
        hi_open: bool = False,
    ) -> None:
        v = item.value
        if v is None or item.is_placeholder:
            return
        below = v <= lo if lo_open else v < lo
        above = v >= hi if hi_open else v > hi
        if below or above:
            allowed = ("(" if lo_open else "[") + f"{lo:g}, {hi:g}" + (")" if hi_open else "]")
            out.append(_range_problem(file, path, lines, what, allowed))

    policy = project.config.margin_policy
    if policy is not None:
        f = "config/margin_policy.yaml"
        for name, cls in policy.classes.items():
            for field in ("power_margin_ratio", "mass_margin_ratio"):
                check(f, ("classes", name, field), getattr(cls, field), "A margin ratio", 0.0, 10.0)
        for field in ("system_power_margin_ratio", "system_mass_margin_ratio"):
            check(f, (field,), getattr(policy, field), "The system margin", 0.0, 10.0)
    limits = project.config.mass_limits
    if limits is not None:
        for index, limit in enumerate(limits.limits):
            check(
                "config/mass_limits.yaml",
                ("limits", index, "limit_kg"),
                limit.limit_kg,
                "A mass limit",
                0.0,
                1e9,
                lo_open=True,
            )
    power = project.config.power_config
    if power is not None:
        f = "config/power_config.yaml"
        check(
            f,
            ("distribution_loss_ratio",),
            power.distribution_loss_ratio,
            "The distribution loss",
            0.0,
            1.0,
            hi_open=True,
        )
        for bus, item in power.converter_efficiency_ratio.items():
            check(
                f,
                ("converter_efficiency_ratio", bus),
                item,
                "A converter efficiency",
                0.0,
                1.0,
                lo_open=True,
            )
    return out


def _mass_references(project: Project, lines: dict[str, LineMap]) -> list[Problem]:
    out: list[Problem] = []
    err = Severity.ERROR
    phases = project.phases
    known = ", ".join(phases)
    policy = project.config.margin_policy

    for uid, unit in project.units.items():
        for index, name in enumerate(unit.phases or []):
            if name not in phases:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_PHASE",
                        f"Phase '{name}' is not a mission phase.",
                        f"units/{uid}.yaml",
                        ("phases", index),
                        lines,
                        f"Defined phases: {known}.",
                    )
                )

    for eid, exp in project.expendables.items():
        file = f"expendables/{eid}.yaml"
        if policy is not None and exp.maturity not in policy.classes:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_MATURITY",
                    "The maturity class is not defined in config/margin_policy.yaml.",
                    file,
                    ("maturity",),
                    lines,
                    "Defined classes: " + ", ".join(policy.classes) + ".",
                )
            )
        for phase in phases:
            if phase not in exp.masses_kg:
                out.append(
                    _p(
                        err,
                        "PHASE_MASS_MISSING",
                        f"No mass is given for phase '{phase}'.",
                        file,
                        ("masses_kg",),
                        lines,
                        f"Add '{phase}: <mass in kg>' (write 0.0 if it is not present).",
                    )
                )
        for phase in exp.masses_kg:
            if phase not in phases:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_PHASE",
                        f"Phase '{phase}' is not a mission phase.",
                        file,
                        ("masses_kg", phase),
                        lines,
                        f"Defined phases: {known}.",
                    )
                )

    limits = project.config.mass_limits
    for index, limit in enumerate(limits.limits if limits else []):
        if limit.phase is not None and limit.phase not in phases:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_PHASE",
                    f"Phase '{limit.phase}' is not a mission phase.",
                    "config/mass_limits.yaml",
                    ("limits", index, "phase"),
                    lines,
                    f"Defined phases: {known}.",
                )
            )

    uses_positions = any(u.mass_properties for u in project.units.values()) or any(
        e.mass_properties for e in project.expendables.values()
    )
    if uses_positions and not project.spacecraft.body_frame.strip():
        out.append(
            _p(
                Severity.WARNING,
                "MASS_FRAME_UNDEFINED",
                "Positions are given but the body frame is not described.",
                "spacecraft.yaml",
                ("body_frame",),
                lines,
                "Describe the axes and origin in 'body_frame' (for example: origin at the "
                "centre of the launch interface plane, +Z along the launch axis).",
            )
        )
    return out
