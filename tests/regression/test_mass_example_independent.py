"""Cross-check the solver against a plain-Python recomputation straight from the example files.

The recomputation shares no code with budget_core's solver: it reads the YAML, sums masses,
takes the mass-weighted mean position and applies the parallel-axis theorem itself.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from budget_core.io.project_loader import load_project
from budget_core.mass.static_mass import static_mass_budget

ROOT = Path(__file__).resolve().parents[2] / "examples"


def read(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return YAML(typ="safe").load(handle)


def items_for(example: str, phase: str) -> list[tuple[float, list[float], dict[str, float]]]:
    items = []
    for f in sorted(glob.glob(str(ROOT / example / "units" / "*.yaml"))):
        d = read(f)
        if d.get("phases") is not None and phase not in d["phases"]:
            continue
        mp = d.get("mass_properties")
        if mp:
            items.append((d["mass_kg"], mp["position_m"], mp.get("inertia") or {}))
    for f in sorted(glob.glob(str(ROOT / example / "expendables" / "*.yaml"))):
        d = read(f)
        mp = d.get("mass_properties")
        if mp:
            items.append((d["masses_kg"][phase], mp["position_m"], {}))
    return items


@pytest.mark.parametrize(
    ("example", "phase"),
    [
        ("microsat_150kg", "launch"),
        ("microsat_150kg", "bol"),
        ("microsat_150kg", "eol"),
        ("cubesat_3u", "launch"),
        ("stress_200_units", "eol"),
    ],
)
def test_solver_matches_independent_recomputation(example: str, phase: str) -> None:
    items = items_for(example, phase)
    total = sum(m for m, _, _ in items)
    cg = [sum(m * p[k] for m, p, _ in items) / total for k in range(3)]
    inertia = [0.0] * 6  # ixx iyy izz ixy ixz iyz about the CG
    for m, p, own in items:
        d = [p[k] - cg[k] for k in range(3)]
        d2 = sum(x * x for x in d)
        inertia[0] += own.get("ixx_kgm2", 0.0) + m * (d2 - d[0] ** 2)
        inertia[1] += own.get("iyy_kgm2", 0.0) + m * (d2 - d[1] ** 2)
        inertia[2] += own.get("izz_kgm2", 0.0) + m * (d2 - d[2] ** 2)
        inertia[3] += own.get("ixy_kgm2", 0.0) - m * d[0] * d[1]
        inertia[4] += own.get("ixz_kgm2", 0.0) - m * d[0] * d[2]
        inertia[5] += own.get("iyz_kgm2", 0.0) - m * d[1] * d[2]

    project = load_project(ROOT / example).project
    assert project is not None
    result = static_mass_budget(project)
    solved = next(p for p in result.phases if p.phase == phase)
    assert solved.cog is not None
    assert solved.total_kg == pytest.approx(total, rel=1e-12)
    assert solved.cog.position_m == pytest.approx(tuple(cg), rel=1e-10, abs=1e-12)
    assert solved.cog.inertia_cg.entries() == pytest.approx(tuple(inertia), rel=1e-9, abs=1e-9)
