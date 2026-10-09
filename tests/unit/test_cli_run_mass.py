import json
from pathlib import Path

import pytest

from budget_cli.main import main
from tests.helpers import edit, write_valid_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "proj")
    return tmp_path / "proj"


def names(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def test_mass_only(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["run", str(root), "--budget", "mass", "--out", str(out), *FIXED]) == 0
    assert names(out) == [
        "mass_static.docx",
        "mass_static.json",
        "mass_static.pdf",
        "mass_static.xlsx",
        "mass_static_eol.csv",
        "mass_static_launch.csv",
    ]


def test_power_only(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["run", str(root), "--budget", "power", "--report", "json", "--out", str(out)]) == 0
    assert names(out) == ["power_static.json"]


def test_default_is_all_budgets(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["run", str(root), "--report", "json", "--out", str(out), *FIXED]) == 0
    assert names(out) == ["mass_static.json", "power_static.json", "thermal_static.json"]


def test_mass_outputs_are_byte_identical_on_rerun(root: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        assert main(["run", str(root), "--budget", "mass", "--out", str(out), *FIXED]) == 0
    for p in sorted(a.iterdir()):
        assert p.read_bytes() == (b / p.name).read_bytes(), p.name


def test_exceeded_limit_writes_reports_but_exits_one(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "config/mass_limits.yaml", "value: 100.0", "value: 0.5")
    out = tmp_path / "out"
    assert main(["run", str(root), "--budget", "mass", "--out", str(out), *FIXED]) == 1
    assert (out / "mass_static.xlsx").exists()
    text = capsys.readouterr().out
    assert "MASS_LIMIT_EXCEEDED" in text and "launch" in text
    data = json.loads((out / "mass_static.json").read_text(encoding="utf-8"))
    assert data["phases"][0]["limits"][0]["status"] == "exceeded"


def test_placeholders_on_the_examples_warn_and_strict_fails(tmp_path: Path) -> None:
    out = tmp_path / "out"
    args = ["run", str(EXAMPLES / "microsat_150kg"), "--budget", "mass", "--out", str(out), *FIXED]
    assert main(args) == 0
    assert main([*args, "--strict"]) == 1
