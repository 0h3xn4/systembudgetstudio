"""Thermal files: loading, references, ranges, placeholders, unit schema 2, unit suffixes."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project, write_project
from budget_core.problems import Problem, Severity
from budget_core.units.quantity import UnitError, parse_quantity
from tests.helpers import edit
from tests.thermal_helpers import thermal_project

MODEL, ENV = "config/thermal_model.yaml", "config/thermal_environment.yaml"


def relevant(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.code != "CONFIG_MISSING"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_project(thermal_project(tmp_path), tmp_path)
    return tmp_path


def test_a_complete_thermal_project_loads_cleanly(root: Path) -> None:
    result = load_project(root)
    assert relevant(result.problems) == [] and result.project is not None
    assert set(result.project.config.thermal_model.nodes) == {"A", "B"}  # type: ignore[union-attr]
    assert result.project.units["u2"].modes[0].heat_dissipation_ratio == 0.6


def test_the_thermal_files_are_optional(root: Path) -> None:
    (root / MODEL).unlink()
    (root / ENV).unlink()
    result = load_project(root)
    assert not [p for p in result.problems if p.file in (MODEL, ENV)]


@pytest.mark.parametrize(
    ("field", "text", "expected"),
    [("conductance_wk", "2 W/K", 2.0), ("heat_capacity_jperk", "0.5 kJ/K", 500.0)],
)
def test_new_suffixes(field: str, text: str, expected: float) -> None:
    assert parse_quantity(text, field) == pytest.approx(expected)


def test_new_suffix_rejects_other_dimensions() -> None:
    with pytest.raises(UnitError):
        parse_quantity("2 W", "conductance_wk")


def test_unknown_node_in_a_conductance_and_a_surface(root: Path) -> None:
    edit(root, MODEL, "second_node: B", "second_node: Z")
    edit(root, MODEL, "node: A\n    area_m2", "node: Y\n    area_m2")
    problems = [p for p in load_project(root).problems if p.code == "THERMAL_NODE_UNKNOWN"]
    assert {(p.file, p.path) for p in problems} == {
        (MODEL, "conductances[0].second_node"),
        (MODEL, "surfaces[0].node"),
    }
    assert all(p.line is not None and "A, B" in p.hint for p in problems)


def test_unit_on_a_node_that_does_not_exist(root: Path) -> None:
    edit(root, "units/u2.yaml", "subsystem: B", "subsystem: C")
    bad = next(p for p in load_project(root).problems if p.code == "THERMAL_NODE_UNKNOWN")
    assert bad.file == "units/u2.yaml" and "thermal_node" in bad.hint


def test_explicit_thermal_node_overrides_the_subsystem(root: Path) -> None:
    edit(root, "units/u2.yaml", "subsystem: B", "subsystem: C\nthermal_node: A")
    path = root / "units" / "u2.yaml"
    text = path.read_text(encoding="utf-8").replace("subsystem: C\nthermal_node: A", "subsystem: C")
    path.write_text(text.rstrip("\n") + "\nthermal_node: A\n", encoding="utf-8", newline="\n")
    assert not [p for p in load_project(root).problems if p.code == "THERMAL_NODE_UNKNOWN"]


def test_unknown_case_in_an_exposure_and_unknown_mode_in_a_case(root: Path) -> None:
    edit(root, MODEL, "    hot:\n", "    warm:\n")
    edit(root, ENV, "spacecraft_mode: cold", "spacecraft_mode: nope")
    problems = load_project(root).problems
    codes = {(p.code, p.file) for p in problems}
    assert ("REF_UNKNOWN_CASE", MODEL) in codes and ("REF_UNKNOWN_MODE", ENV) in codes


def test_range_errors_name_the_field(root: Path) -> None:
    edit(root, ENV, "albedo_ratio:\n      value: 0.3", "albedo_ratio:\n      value: 1.5")
    edit(root, MODEL, "emissivity_ratio:\n      value: 0.8", "emissivity_ratio:\n      value: 0.0")
    bad = {p.path for p in load_project(root).problems if p.code == "CONFIG_VALUE_INVALID"}
    assert bad == {
        "cases.hot.albedo_ratio.value",
        "surfaces[0].emissivity_ratio.value",
    }


def test_placeholders_are_reported(tmp_path: Path) -> None:
    write_project(thermal_project(tmp_path, conductance=None, margin=None), tmp_path)
    found = {
        (p.file, p.path)
        for p in load_project(tmp_path).problems
        if p.code == "CONFIG_PLACEHOLDER" and p.file in (MODEL, ENV)
    }
    assert found == {(MODEL, "conductances[0].conductance_wk"), (ENV, "temperature_margin_k")}


def test_temperature_limits_must_be_ordered(root: Path) -> None:
    path = root / "units" / "u1.yaml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "temperature_limits:\n  operating_min_k: 300.0\n  operating_max_k: 280.0\n",
        encoding="utf-8",
        newline="\n",
    )
    problems = load_project(root).problems
    assert any(p.severity is Severity.ERROR and p.file == "units/u1.yaml" for p in problems)


def test_unit_version_1_migrates_in_memory(root: Path) -> None:
    edit(root, "units/u1.yaml", "schema_version: 2", "schema_version: 1")
    result = load_project(root)
    assert result.project is not None
    migrated = [p for p in result.problems if p.code == "FILE_MIGRATED"]
    assert [p.file for p in migrated] == ["units/u1.yaml"]
    assert migrated[0].severity is Severity.INFO
