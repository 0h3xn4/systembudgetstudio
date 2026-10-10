from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from tests.helpers import edit

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    a, b = tmp_path / "rev1", tmp_path / "rev2"
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", a)
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", b)
    edit(b, "units/adcs.yaml", "avg_power_w: 0.9", "avg_power_w: 1.3")
    edit(b, "project.yaml", "revision: '1'", "revision: '2'")
    return a, b


def test_compare_two_revisions_writes_all_kinds(
    pair: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = pair
    out = tmp_path / "out"
    assert main(["compare", str(a), str(b), "--out", str(out), *FIXED]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "compare.docx",
        "compare.json",
        "compare.pdf",
        "compare.xlsx",
        "compare_differences.csv",
    ]
    data = json.loads((out / "compare.json").read_text(encoding="utf-8"))
    assert data["differences"]
    assert {d["comparison"] for d in data["differences"]} <= {
        "Static power budget",
        "Mass budget",
        "Thermal budget",
        "Link budget",
    }
    text = capsys.readouterr().out
    assert "value(s) differ" in text


def test_compare_is_byte_identical_between_runs(pair: tuple[Path, Path], tmp_path: Path) -> None:
    a, b = pair
    for name in ("one", "two"):
        main(["compare", str(a), str(b), "--out", str(tmp_path / name), "--report", "csv", *FIXED])
        main(["compare", str(a), str(b), "--out", str(tmp_path / name), "--report", "json", *FIXED])
    for file in ("compare_differences.csv", "compare.json"):
        assert (tmp_path / "one" / file).read_bytes() == (tmp_path / "two" / file).read_bytes()


def test_two_scenarios_of_one_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", root)
    shutil.copy(root / "scenarios/one_day.yaml", root / "scenarios/variant.yaml")
    edit(root, "scenarios/variant.yaml", "default_mode: charging", "default_mode: safe")
    code = main(
        [
            "compare",
            str(root),
            "--scenario-a",
            "one_day",
            "--scenario-b",
            "variant",
            "--out",
            str(tmp_path / "out"),
            "--report",
            "json",
            *FIXED,
        ]
    )
    assert code == 0
    data = json.loads((tmp_path / "out/compare.json").read_text(encoding="utf-8"))
    assert {d["comparison"] for d in data["differences"]} <= {"Power timeline", "Link passes"}


def test_single_project_without_two_scenarios_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["compare", str(EXAMPLES / "cubesat_3u_eps")])
    assert code == 2
    assert "second project" in capsys.readouterr().out


def test_invalid_project_stops_with_plain_message(
    pair: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = pair
    edit(b, "units/adcs.yaml", "avg_power_w: 1.3", "avg_power_w: 9.9")
    code = main(["compare", str(a), str(b), "--out", str(tmp_path / "out")])
    assert code == 1
    assert not (tmp_path / "out").exists()
    assert "nothing was written" in capsys.readouterr().out


def test_unknown_scenario_is_reported(
    pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = pair
    code = main(["compare", str(a), str(b), "--scenario", "nope", "--budget", "timeline"])
    assert code == 1
    out = capsys.readouterr().out
    assert "scenario" in out.lower()
