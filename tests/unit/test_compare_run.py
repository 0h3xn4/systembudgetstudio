from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.compare_run import Side, compare_sides, default_kinds
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from tests.helpers import edit

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = {"user": "Test User"}


def load(path: Path) -> Project:
    project = load_project(path).project
    assert project is not None
    return project


@pytest.fixture
def revisions(tmp_path: Path) -> tuple[Path, Path]:
    a, b = tmp_path / "rev1", tmp_path / "rev2"
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", a)
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", b)
    return a, b


def test_default_kinds() -> None:
    project = load(EXAMPLES / "cubesat_3u_eps")
    a, b = Side(project), Side(project)
    assert default_kinds(a, b, same_project=False) == ("power", "mass", "thermal", "link")
    sa, sb = Side(project, "one_day"), Side(project, "one_day")
    assert default_kinds(sa, sb, same_project=True) == ("timeline", "link-passes")
    assert default_kinds(sa, sb, same_project=False)[-2:] == ("timeline", "link-passes")


def test_identical_revisions_have_no_differences(revisions: tuple[Path, Path]) -> None:
    a, b = revisions
    out, notes = compare_sides(
        Side(load(a)), Side(load(b)), ("power", "mass", "thermal", "link"), **FIXED
    )
    assert notes == []
    assert all(not r.differences for r in out.result)


def test_changed_unit_power_shows_in_power_and_mass_untouched(
    revisions: tuple[Path, Path],
) -> None:
    a, b = revisions
    edit(b, "units/adcs.yaml", "avg_power_w: 0.9", "avg_power_w: 1.3")
    edit(b, "project.yaml", "revision: '1'", "revision: '2'")
    out, _ = compare_sides(Side(load(a)), Side(load(b)), ("power", "mass"), **FIXED)
    power, mass = out.result
    assert power.differences and not mass.differences
    assert any(d.status == "changed" and "W" in d.change for d in power.differences)
    assert "rev 2" in out.document.title


def test_scenario_comparison_within_one_project(tmp_path: Path) -> None:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", root)
    shutil.copy(root / "scenarios/one_day.yaml", root / "scenarios/variant.yaml")
    edit(root, "scenarios/variant.yaml", "name: One day", "name: Variant of one day")
    project = load(root)
    out, notes = compare_sides(
        Side(project, "one_day"), Side(project, "variant"), ("timeline", "link-passes"), **FIXED
    )
    assert notes == []
    assert [r.name for r in out.result] == ["Power timeline", "Link passes"]


def test_missing_links_are_noted_not_hidden(tmp_path: Path) -> None:
    root = tmp_path / "nolinks"
    shutil.copytree(EXAMPLES / "cubesat_3u", root)
    shutil.rmtree(root / "links")
    project = load(root)
    out, notes = compare_sides(Side(project), Side(project), ("link",), **FIXED)
    assert notes and "Link budget" in notes[0]
    assert out.result == []


def test_short_labels_name_only_what_differs(revisions: tuple[Path, Path]) -> None:
    from budget_core.compare_run import short_labels

    a, b = revisions
    edit(b, "project.yaml", "revision: '1'", "revision: '2'")
    pa, pb = load(a), load(b)
    assert short_labels(Side(pa), Side(pb)) == ("rev 1", "rev 2")
    assert short_labels(Side(pa), Side(pa)) == ("A", "B")
    assert short_labels(Side(pa, "x"), Side(pa, "y")) == ("x", "y")
    other = replace(pb, meta=pb.meta.model_copy(update={"name": "Other"}))
    assert short_labels(Side(pa), Side(other)) == (f"{pa.meta.name}, rev 1", "Other, rev 2")
