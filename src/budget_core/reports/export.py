"""CSV and JSON exports of budget results (deterministic text, LF line endings)."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any

from budget_core.power.static_budget import ModePowerResult, StaticPowerResult
from budget_core.provenance import Provenance

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


def result_json(result: StaticPowerResult, provenance: Provenance) -> str:
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


def _cell(value: Any) -> str:
    return repr(value) if isinstance(value, float) else str(value)
