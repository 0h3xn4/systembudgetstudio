"""A project file may only make the tool read files inside the project folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from budget_core.io.paths import resolve_inside
from budget_core.io.project_loader import load_project, write_project
from budget_core.link.evaluate import link_static_budget
from budget_core.model import Antenna
from budget_core.problems import Severity
from tests.helpers import write_valid_project
from tests.link_helpers import downlink, link_project

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")


# ---- resolve_inside --------------------------------------------------------------------------
def test_relative_paths_inside_are_resolved(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f.csv").write_text("x", encoding="utf-8")
    assert resolve_inside(tmp_path, "a/f.csv") == (tmp_path / "a" / "f.csv").resolve()
    assert resolve_inside(tmp_path, "a/../a/f.csv") == (tmp_path / "a" / "f.csv").resolve()


@pytest.mark.parametrize(
    "rel", ["../x.csv", "a/../../x.csv", "/etc/hostname", "", "x\x00y", "C:\\x"]
)
def test_paths_that_leave_the_folder_are_refused(tmp_path: Path, rel: str) -> None:
    assert resolve_inside(tmp_path, rel) is None


@POSIX
def test_symlinks_that_leave_the_folder_are_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("x", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    os.symlink(outside, root / "link.csv")
    (root / "real.csv").write_text("y", encoding="utf-8")
    os.symlink(root / "real.csv", root / "inside.csv")
    assert resolve_inside(root, "link.csv") is None
    assert resolve_inside(root, "inside.csv") == (root / "real.csv").resolve()


# ---- pattern files ---------------------------------------------------------------------------
def tx_with_pattern(rel: str):  # type: ignore[no-untyped-def]
    return downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file=rel, pattern_source="test fixture")}
    )


def test_a_pattern_file_outside_the_project_is_not_read(tmp_path: Path) -> None:
    (tmp_path / "secret.csv").write_text("angle_deg,gain_dbi\n0,6\n60,0\n", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    project = link_project(
        root=root, links={"dl": downlink(transmitter=tx_with_pattern("../secret.csv"))}
    )
    result = link_static_budget(project)
    bad = [p for p in result.problems if p.code == "LINK_INPUT_INVALID"]
    assert bad and "inside the project folder" in bad[0].message
    assert result.rows[0].cn0_dbhz is None


def test_validation_reports_a_pattern_path_that_escapes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    write_project(
        link_project(root, links={"dl": downlink(transmitter=tx_with_pattern("../x.csv"))}), root
    )
    problems = load_project(root).problems
    bad = next(p for p in problems if p.code == "LINK_PATTERN_FILE_MISSING")
    assert "inside the project folder" in bad.message


@pytest.mark.parametrize("gain", ["nan", "inf", "-inf"])
def test_non_finite_pattern_gains_are_rejected(tmp_path: Path, gain: str) -> None:
    (tmp_path / "pattern.csv").write_text(f"angle_deg,gain_dbi\n0,{gain}\n60,0\n", encoding="utf-8")
    project = link_project(
        root=tmp_path, links={"dl": downlink(transmitter=tx_with_pattern("pattern.csv"))}
    )
    result = link_static_budget(project)
    assert any(p.code == "LINK_INPUT_INVALID" for p in result.problems)
    assert result.rows[0].cn0_dbhz is None


# ---- project files ---------------------------------------------------------------------------
@POSIX
def test_a_project_file_symlinked_outside_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "p"
    write_valid_project(root)
    outside = tmp_path / "evil.yaml"
    outside.write_text((root / "units" / "obc.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    os.symlink(outside, root / "units" / "zz.yaml")
    problems = load_project(root).problems
    bad = next(p for p in problems if p.file == "units/zz.yaml")
    assert bad.severity is Severity.ERROR and "inside the project folder" in bad.message


# ---- import folder ---------------------------------------------------------------------------
def test_an_import_folder_outside_the_project_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "p"
    write_valid_project(root)
    scenario = root / "scenarios" / "day.yaml"
    text = scenario.read_text(encoding="utf-8")
    text = text.replace("environment_source: elements", "environment_source: spacemissionstudio")
    text += "import_dir: ../elsewhere\n"
    scenario.write_text(text, encoding="utf-8")
    (tmp_path / "elsewhere").mkdir()
    problems = load_project(root).problems
    bad = next(p for p in problems if p.code == "IMPORT_DIR_MISSING")
    assert "inside the project folder" in bad.message
