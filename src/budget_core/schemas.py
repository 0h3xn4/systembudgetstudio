"""JSON Schemas for every file kind, generated from the pydantic models.

The committed copies in `budget_core/schemas/` are checked by a test and give editors
completion and validation. They describe the canonical form (numbers in canonical units); the
loader additionally accepts "<number> <unit>" strings for unit-suffixed fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from budget_core.model import (
    AttenuationTable,
    BudgetModel,
    Ebn0Table,
    Expendable,
    GroundStation,
    MarginPolicy,
    MassLimits,
    Orbit,
    PowerConfig,
    PowerSystem,
    ProjectMeta,
    Scenario,
    Spacecraft,
    SpacecraftMode,
    Target,
    Unit,
)

SCHEMA_DIR = Path(__file__).parent / "schemas"

SCHEMA_MODELS: dict[str, type[BudgetModel]] = {
    "project": ProjectMeta,
    "spacecraft": Spacecraft,
    "unit": Unit,
    "expendable": Expendable,
    "mass_limits": MassLimits,
    "orbit": Orbit,
    "ground_station": GroundStation,
    "target": Target,
    "scenario": Scenario,
    "spacecraft_mode": SpacecraftMode,
    "margin_policy": MarginPolicy,
    "power_config": PowerConfig,
    "power_system": PowerSystem,
    "ebn0_table": Ebn0Table,
    "attenuation_table": AttenuationTable,
}


def json_schema(kind: str) -> dict[str, Any]:
    schema = SCHEMA_MODELS[kind].model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"System Budget Studio {kind}"
    schema["required"] = sorted(set(schema.get("required", [])) | {"schema_version", "kind"})
    return schema


def schema_text(kind: str) -> str:
    return json.dumps(json_schema(kind), indent=2, sort_keys=True) + "\n"


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for kind in sorted(SCHEMA_MODELS):
        path = out_dir / f"{kind}.schema.json"
        path.write_bytes(schema_text(kind).encode("utf-8"))
        written.append(path)
    return written
