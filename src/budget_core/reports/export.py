"""CSV and JSON exports of budget results (deterministic text, LF line endings)."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any

from budget_core.mass.static_mass import PhaseMass
from budget_core.power.static_budget import ModePowerResult
from budget_core.provenance import Provenance
from budget_core.thermal.static_thermal import CaseThermal, ModeHeat

CSV_COLUMNS = (
    "unit_id",
    "unit_name",
    "subsystem",
    "bus",
    "power_mode",
    "avg_power_w",
    "duty_cycle_ratio",
    "effective_power_w",
    "peak_power_w",
    "margin_ratio",
    "margined_power_w",
    "margined_peak_w",
)


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if hasattr(value, "value") and hasattr(value, "name") and not isinstance(value, str):
        return value.value  # enum
    return value


def result_json(result: Any, provenance: Provenance) -> str:
    data = _plain(asdict(result))
    data["problems"] = [p.to_dict() for p in result.problems]
    data["provenance"] = _plain(asdict(provenance))
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def result_csv(mode: ModePowerResult) -> str:
    """One mode's unit table. Unavailable values (placeholders) are empty cells."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in mode.rows:
        values = asdict(row)
        writer.writerow(["" if values[c] is None else _cell(values[c]) for c in CSV_COLUMNS])
    return buffer.getvalue()


MASS_CSV_COLUMNS = (
    "item_id",
    "name",
    "kind",
    "subsystem",
    "maturity",
    "mass_kg",
    "margin_ratio",
    "margined_mass_kg",
    "x_m",
    "y_m",
    "z_m",
)


def mass_csv(phase: PhaseMass) -> str:
    """One phase's item table. Unavailable values (placeholders, no position) are empty cells."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MASS_CSV_COLUMNS)
    for row in phase.rows:
        x, y, z = row.position_m if row.position_m else (None, None, None)
        values = [
            row.item_id,
            row.name,
            row.kind,
            row.subsystem,
            row.maturity,
            row.mass_kg,
            row.margin_ratio,
            row.margined_mass_kg,
            x,
            y,
            z,
        ]
        writer.writerow(["" if v is None else _cell(v) for v in values])
    return buffer.getvalue()


def _cell(value: Any) -> str:
    return repr(value) if isinstance(value, float) else str(value)


THERMAL_CSV_COLUMNS = (
    "unit_id",
    "unit_name",
    "subsystem",
    "node",
    "power_mode",
    "effective_power_w",
    "heat_dissipation_ratio",
    "dissipation_w",
    "peak_dissipation_w",
)


def thermal_mode_csv(mode: ModeHeat) -> str:
    """One mode's dissipation by unit. Unavailable values are empty cells."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(THERMAL_CSV_COLUMNS)
    for row in mode.rows:
        values = asdict(row)
        writer.writerow(
            ["" if values[c] is None else _cell(values[c]) for c in THERMAL_CSV_COLUMNS]
        )
    return buffer.getvalue()


def thermal_case_csv(case: CaseThermal) -> str:
    """One case's node temperatures; empty when the case could not be computed."""
    columns = (
        "node",
        "temperature_k",
        "dissipation_w",
        "absorbed_w",
        "radiated_w",
        "conducted_out_w",
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for node in case.nodes:
        values = asdict(node)
        writer.writerow([_cell(values[c]) for c in columns])
    return buffer.getvalue()
