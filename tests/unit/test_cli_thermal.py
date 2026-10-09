"""`budget run --budget thermal`: files, findings, exit codes, determinism."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.io.project_loader import write_project
from tests.thermal_helpers import SIGMA, thermal_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def two_nodes(tmp_path: Path) -> Path:
    write_project(thermal_project(tmp_path / "p"), tmp_path / "p")
    return tmp_path / "p"


def test_json_has_the_hand_calculated_temperatures(two_nodes: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    code = main(
        [
            "run",
            str(two_nodes),
            "--budget",
            "thermal",
            "--report",
            "json",
            "--out",
            str(out),
            *FIXED,
        ]
    )
    assert code == 0
    data = json.loads((out / "thermal_static.json").read_text(encoding="utf-8"))
    hot = next(c for c in data["cases"] if c["case"] == "hot")
    t_a = (291.0 / (0.8 * SIGMA) + 4.0**4) ** 0.25
    temps = {n["node"]: n["temperature_k"] for n in hot["nodes"]}
    assert temps["A"] == pytest.approx(t_a, abs=1e-6) and temps["B"] == pytest.approx(
        t_a + 3.0, abs=1e-6
    )
    assert data["provenance"]["user"] == "Test User"


def test_all_report_kinds_are_written(two_nodes: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    main(["run", str(two_nodes), "--budget", "thermal", "--out", str(out), *FIXED])
    assert sorted(p.name for p in out.iterdir()) == [
        "thermal_case_cold.csv",
        "thermal_case_hot.csv",
        "thermal_static.docx",
        "thermal_static.json",
        "thermal_static.pdf",
        "thermal_static.xlsx",
        "thermal_static_cold.csv",
        "thermal_static_hot.csv",
    ]


def test_outputs_are_byte_identical(two_nodes: Path, tmp_path: Path) -> None:
    for name in ("a", "b"):
        main(["run", str(two_nodes), "--budget", "thermal", "--out", str(tmp_path / name), *FIXED])
    for path in sorted((tmp_path / "a").iterdir()):
        assert path.read_bytes() == (tmp_path / "b" / path.name).read_bytes(), path.name


def test_a_limit_finding_writes_the_reports_but_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    code = main(
        [
            "run",
            str(tmp_path / "p"),
            "--budget",
            "thermal",
            "--report",
            "json",
            "--out",
            str(tmp_path / "out"),
            *FIXED,
        ]
    )
    text = capsys.readouterr().out
    assert code == 1 and "THERMAL_MARGIN_INSUFFICIENT" in text and "units/radio.yaml" in text
    assert (tmp_path / "out" / "thermal_static.json").exists()


def test_placeholder_examples_warn_and_strict_fails(tmp_path: Path) -> None:
    args = [
        "run",
        str(EXAMPLES / "cubesat_3u"),
        "--budget",
        "thermal",
        "--report",
        "json",
        "--out",
        str(tmp_path / "out"),
        *FIXED,
    ]
    assert main(args) == 0
    assert main([*args, "--strict"]) == 1
    data = json.loads((tmp_path / "out" / "thermal_static.json").read_text(encoding="utf-8"))
    assert all(not c["complete"] for c in data["cases"])
