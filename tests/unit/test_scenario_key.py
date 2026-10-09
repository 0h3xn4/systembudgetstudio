"""environment_key: what invalidates a computed environment, and what only the timeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.scenario.run import environment_key, rebuild_timeline, run_scenario
from tests.helpers import edit, write_valid_project


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "p")
    return tmp_path / "p"


def key(root: Path) -> str:
    project = load_project(root).project
    assert project is not None
    return environment_key(project, project.scenarios["day"])


def test_key_is_stable(root: Path) -> None:
    assert key(root) == key(root)


@pytest.mark.parametrize(
    ("file", "old", "new"),
    [
        ("scenarios/day.yaml", "name: One day", "name: Renamed"),
        ("scenarios/day.yaml", "default_mode: nominal", "default_mode: downlink"),
        ("scenarios/day.yaml", "mode: downlink", "mode: nominal"),
    ],
)
def test_timeline_only_edits_keep_the_key(root: Path, file: str, old: str, new: str) -> None:
    before = key(root)
    edit(root, file, old, new)
    assert key(root) == before


@pytest.mark.parametrize(
    ("file", "old", "new"),
    [
        ("scenarios/day.yaml", "step_s: 30.0", "step_s: 60.0"),
        ("scenarios/day.yaml", "duration_s: 86400.0", "duration_s: 43200.0"),
        ("scenarios/day.yaml", "shadow_model: cylindrical", "shadow_model: conical"),
        (
            "scenarios/day.yaml",
            "start_utc: '2026-01-01T00:00:00Z'",
            "start_utc: '2026-01-02T00:00:00Z'",
        ),
        ("targets/tgt1.yaml", "longitude_deg: -100.0", "longitude_deg: -90.0"),
        ("orbits/leo.yaml", "inclination_deg: 97.5", "inclination_deg: 98.5"),
        ("ground_stations/gs1.yaml", "latitude_deg: 60.0", "latitude_deg: 61.0"),
        ("ground_stations/gs1.yaml", "min_elevation_deg: 5.0", "min_elevation_deg: 10.0"),
    ],
)
def test_environment_edits_change_the_key(root: Path, file: str, old: str, new: str) -> None:
    before = key(root)
    edit(root, file, old, new)
    assert key(root) != before


def test_import_folder_changes_change_the_key(root: Path) -> None:
    folder = root / "imports" / "r"
    folder.mkdir(parents=True)
    (folder / "orbit.csv").write_text("a\n", encoding="utf-8")
    edit(
        root,
        "scenarios/day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/r",
    )
    before = key(root)
    (folder / "orbit.csv").write_text("a\nb\n", encoding="utf-8")
    assert key(root) != before


def test_rebuild_timeline_reuses_the_environment(root: Path) -> None:
    project = load_project(root).project
    assert project is not None
    run = run_scenario(project, "day")
    edit(root, "scenarios/day.yaml", "default_mode: nominal", "default_mode: downlink")
    changed = load_project(root).project
    assert changed is not None
    again = rebuild_timeline(run, changed.scenarios["day"])
    assert again.env is run.env and again.scenario.default_mode == "downlink"
    fresh = run_scenario(changed, "day")
    assert [(s.start_s, s.end_s, s.mode) for s in again.timeline] == [
        (s.start_s, s.end_s, s.mode) for s in fresh.timeline
    ]
