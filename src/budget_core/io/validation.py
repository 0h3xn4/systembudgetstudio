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

    for kind in ("margin_policy", "power_config", "ebn0_table", "attenuation_table"):
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
