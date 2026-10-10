from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.environment.constants import EARTH_RADIUS
from budget_core.io.project_loader import load_project
from budget_core.power.static_budget import static_power_budget
from budget_core.problems import Severity
from budget_core.scenario.run import run_scenario
from budget_core.wizard import (
    SAMPLES,
    WizardAnswers,
    WizardError,
    check_answers,
    create_project,
    folder_name,
)


def answers(**kw: object) -> WizardAnswers:
    base = {"project_name": "My first satellite", "sample": "cubesat_3u_eps"}
    return WizardAnswers(**{**base, **kw})  # type: ignore[arg-type]


def test_defaults_are_valid() -> None:
    assert check_answers(answers()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_name", "   "),
        ("sample", "nope"),
        ("altitude_km", 50.0),
        ("altitude_km", 5000.0),
        ("inclination_deg", 181.0),
        ("raan_deg", 360.0),
        ("duration_days", 0.0),
        ("duration_days", 60.0),
        ("start_utc", "yesterday"),
    ],
)
def test_out_of_range_answers_are_named_by_field(field: str, value: object) -> None:
    issues = check_answers(answers(**{field: value}))
    assert issues and any(field in issue.field for issue in issues)
    assert all(not isinstance(i.message, float) for i in issues)


def test_folder_name_is_a_safe_slug() -> None:
    assert folder_name("My first satellite!") == "my-first-satellite"
    assert folder_name("../../etc") == "etc"
    assert folder_name("   ") == "project"
    assert folder_name("Ünïcode ✓ name") == "unicode-name"


@pytest.mark.parametrize("sample", sorted(SAMPLES))
def test_every_sample_gives_a_loadable_project_with_a_runnable_scenario(
    sample: str, tmp_path: Path
) -> None:
    folder = create_project(answers(sample=sample), tmp_path)
    loaded = load_project(folder)
    assert loaded.project is not None
    assert [p for p in loaded.problems if p.severity is Severity.ERROR] == []
    project = loaded.project
    assert project.meta.name == "My first satellite"
    assert project.meta.revision == "1"
    assert "invented" in project.meta.description
    result = static_power_budget(project)
    assert result.modes
    run = run_scenario(project, sorted(project.scenarios)[0])
    assert len(run.timeline) > 0


def test_orbit_follows_the_answers(tmp_path: Path) -> None:
    folder = create_project(
        answers(altitude_km=700.0, inclination_deg=51.6, raan_deg=33.0, duration_days=2.0),
        tmp_path,
    )
    project = load_project(folder).project
    assert project is not None
    (orbit,) = project.orbits.values()
    assert orbit.elements is not None
    assert orbit.elements.semi_major_axis_m == pytest.approx(EARTH_RADIUS.value + 700_000.0)
    assert orbit.elements.inclination_deg == 51.6
    assert orbit.elements.raan_deg == 33.0
    scenario = next(iter(project.scenarios.values()))
    assert scenario.duration_s == 2 * 86400.0
    assert scenario.orbit is not None and scenario.orbit in project.orbits


def test_long_scenarios_get_a_coarser_step(tmp_path: Path) -> None:
    folder = create_project(answers(duration_days=14.0), tmp_path)
    project = load_project(folder).project
    assert project is not None
    scenario = next(iter(project.scenarios.values()))
    assert scenario.duration_s / scenario.step_s <= 9000


def test_existing_folder_is_never_overwritten(tmp_path: Path) -> None:
    create_project(answers(), tmp_path)
    with pytest.raises(WizardError) as info:
        create_project(answers(), tmp_path)
    assert "already exists" in str(info.value)


def test_invalid_answers_raise_before_writing(tmp_path: Path) -> None:
    with pytest.raises(WizardError):
        create_project(answers(altitude_km=1.0), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_creation_is_deterministic(tmp_path: Path) -> None:
    one = create_project(answers(), tmp_path / "a")
    two = create_project(answers(), tmp_path / "b")
    files = sorted(p.relative_to(one) for p in one.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(two) for p in two.rglob("*") if p.is_file())
    for rel in files:
        assert (one / rel).read_bytes() == (two / rel).read_bytes()
