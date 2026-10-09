"""The power_system file: loading, ranges, references, placeholders, unit suffixes."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project, write_project
from budget_core.problems import Problem, Severity
from budget_core.units.quantity import UnitError, parse_quantity
from tests.helpers import edit
from tests.power_helpers import power_system, sv, td_project

FILE = "config/power_system.yaml"


def codes(problems: list[Problem]) -> list[str]:
    return [p.code for p in problems]


def relevant(problems: list[Problem]) -> list[Problem]:
    """The test project has no Eb/N0 table, attenuation table or mass limits: ignore that."""
    return [p for p in problems if p.code != "CONFIG_MISSING"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_project(td_project(tmp_path), tmp_path)
    return tmp_path


def test_a_complete_file_loads_cleanly(root: Path) -> None:
    result = load_project(root)
    assert relevant(result.problems) == []
    assert result.project is not None
    assert result.project.config.power_system is not None
    assert len(result.project.config.power_system.solar_array.faces) == 1


def test_a_project_without_the_file_has_no_warning(root: Path) -> None:
    (root / FILE).unlink()
    result = load_project(root)
    assert relevant(result.problems) == [] and result.project is not None
    assert result.project.config.power_system is None
    assert not any(p.file == FILE for p in result.problems)


@pytest.mark.parametrize(
    ("field", "text", "expected"),
    [
        ("cell_area_m2", "30 cm**2", 0.003),
        ("solar_irradiance_wm2", "1360 W/m**2", 1360.0),
        ("cell_capacity_ah", "2600 mAh", 2.6),
        ("design_life_yr", "24 month", 2.0),
        ("efficiency_temp_coeff_perk", "-0.002 1/K", -0.002),
    ],
)
def test_new_unit_suffixes(field: str, text: str, expected: float) -> None:
    assert parse_quantity(text, field) == pytest.approx(expected, rel=1e-3)


def test_wrong_dimension_for_a_new_suffix_is_rejected() -> None:
    with pytest.raises(UnitError):
        parse_quantity("30 W", "cell_area_m2")


def test_range_errors_name_the_field(root: Path) -> None:
    edit(
        root,
        FILE,
        "charge_efficiency_ratio:\n    value: 1.0",
        "charge_efficiency_ratio:\n    value: 1.2",
    )
    result = load_project(root)
    problem = next(p for p in result.problems if p.code == "CONFIG_VALUE_INVALID")
    assert problem.file == FILE and problem.path == "battery.charge_efficiency_ratio.value"
    assert problem.line is not None and result.project is None
    assert "1.2" not in problem.message  # no project values in messages


def test_unknown_phase_in_the_depth_of_discharge_table(root: Path) -> None:
    edit(root, FILE, "    eol:\n", "    eoll:\n")
    problems = load_project(root).problems
    bad = next(p for p in problems if p.code == "REF_UNKNOWN_PHASE")
    assert bad.file == FILE and bad.path == "battery.max_dod_ratio.eoll" and bad.line is not None
    assert "launch, eol" in bad.hint


def test_unknown_mode_in_the_attitude_table(root: Path) -> None:
    system = power_system().model_copy(
        update={"attitude": power_system().attitude.model_copy(update={"by_mode": {"zzz": "sun"}})}
    )
    write_project(td_project(root, system=system), root)
    bad = next(p for p in load_project(root).problems if p.code == "REF_UNKNOWN_MODE")
    assert bad.path == "attitude.by_mode.zzz" and "a, b" in bad.hint


def test_unknown_mission_phase_in_a_scenario(root: Path) -> None:
    project = td_project(root)
    from budget_core.model import Orbit, Scenario
    from tests.helpers import build_project

    helper = build_project(root)
    scenario = Scenario(
        name="S",
        orbit="leo",
        start_utc="2026-01-01T00:00:00Z",
        duration_s=600.0,
        step_s=60.0,
        default_mode="a",
        mission_phase="nonexistent",
    )
    orbit: Orbit = helper.orbits["leo"]
    project = type(project)(
        **{**project.__dict__, "orbits": {"leo": orbit}, "scenarios": {"s": scenario}}
    )
    write_project(project, root)
    bad = next(p for p in load_project(root).problems if p.code == "REF_UNKNOWN_PHASE")
    assert bad.file == "scenarios/s.yaml" and bad.path == "mission_phase"


def test_zero_direction_vector_is_rejected(root: Path) -> None:
    path = root / FILE
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    index = next(i for i, line in enumerate(lines) if line.strip() == "normal_body:")
    lines[index + 3] = lines[index + 3].replace("1.0", "0.0")  # normal (0, 0, 1) -> (0, 0, 0)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    problems = load_project(root).problems
    assert any(p.severity is Severity.ERROR and p.file == FILE for p in problems)


def test_placeholders_are_reported(tmp_path: Path) -> None:
    system = power_system()
    array = system.solar_array.model_copy(update={"cell_efficiency_ratio": sv(None)})
    write_project(
        td_project(tmp_path, system=system.model_copy(update={"solar_array": array})), tmp_path
    )
    found = [p for p in load_project(tmp_path).problems if p.code == "CONFIG_PLACEHOLDER"]
    assert [p.path for p in found] == ["solar_array.cell_efficiency_ratio"]


def test_scenario_version_1_migrates_in_memory(tmp_path: Path) -> None:
    from tests.helpers import write_valid_project

    write_valid_project(tmp_path)
    path = tmp_path / "scenarios" / "day.yaml"
    path.write_text(
        path.read_text().replace("schema_version: 2", "schema_version: 1"), newline="\n"
    )
    result = load_project(tmp_path)
    assert result.project is not None
    assert [p.code for p in result.problems] == ["FILE_MIGRATED"]
    assert result.problems[0].severity is Severity.INFO
