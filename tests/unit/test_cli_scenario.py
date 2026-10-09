import json
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.environment.elements import ElementsPropagator
from budget_core.environment.spacemissionstudio import export_spacemissionstudio
from budget_core.io.project_loader import load_project
from tests.helpers import edit, write_valid_project

FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "proj")
    return tmp_path / "proj"


def run(root: Path, out: Path, *extra: str) -> int:
    return main(["scenario", str(root), "--out", str(out), *FIXED, *extra])


def test_writes_environment_eclipses_passes_and_timeline(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert run(root, out) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "day_eclipses.csv",
        "day_environment.json",
        "day_passes.csv",
        "day_timeline.csv",
    ]
    text = capsys.readouterr().out
    assert "Traceback" not in text and "eclipse" in text.lower() and "gs1" in text

    data = json.loads((out / "day_environment.json").read_text(encoding="utf-8"))
    assert data["source"] == "elements" and data["shadow_model"] == "cylindrical"
    assert data["grid"]["samples"] == 2881 and data["provenance"]["user"] == "Test User"
    assert len(data["eclipses"]) >= 10  # about 15 orbits per day, all with an eclipse at this beta
    assert 0.1 < data["eclipse_fraction"] < 0.45
    assert len(data["sites"]["gs1"]["passes"]) >= 3
    modes = {s["mode"] for s in data["timeline"]}
    assert modes == {"nominal", "downlink"}  # tgt1 passes map to nominal and merge away
    assert data["timeline"][0]["start_s"] == 0.0 and data["timeline"][-1]["end_s"] == 86400.0


def test_csv_files_have_documented_headers(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    run(root, out)
    head = lambda name: (out / name).read_text(encoding="utf-8").splitlines()[0]  # noqa: E731
    assert head("day_eclipses.csv") == "start_s,end_s,duration_s,start_utc,end_utc"
    assert head("day_passes.csv") == (
        "site,kind,aos_s,los_s,duration_s,max_elevation_deg,time_of_max_s,aos_utc,los_utc,"
        "partial_start,partial_end"
    )
    assert head("day_timeline.csv") == "start_s,end_s,duration_s,mode,start_utc,end_utc"
    rows = (out / "day_passes.csv").read_text(encoding="utf-8").splitlines()[1:]
    assert any(r.startswith("gs1,ground_station,") for r in rows)


def test_outputs_are_byte_identical_on_rerun(root: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    assert run(root, a) == 0 and run(root, b) == 0
    for p in sorted(a.iterdir()):
        assert p.read_bytes() == (b / p.name).read_bytes(), p.name
        assert b"\r" not in p.read_bytes()


def test_default_output_folder_is_results_inside_the_project(root: Path) -> None:
    assert main(["scenario", str(root), *FIXED]) == 0
    assert (root / "results" / "day_environment.json").is_file()


def test_the_only_scenario_is_chosen_without_a_name(root: Path, tmp_path: Path) -> None:
    assert main(["scenario", str(root), "--out", str(tmp_path / "o"), *FIXED]) == 0


def test_unknown_scenario_is_a_plain_error(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(root, tmp_path / "o", "--scenario", "nope") == 1
    out = capsys.readouterr().out
    assert "SCENARIO_UNKNOWN" in out and "day" in out and "Traceback" not in out


def test_project_errors_stop_the_run(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "scenarios/day.yaml", "orbit: leo", "orbit: nope")
    out = tmp_path / "o"
    assert run(root, out) == 1
    assert not out.exists() and "REF_UNKNOWN_ORBIT" in capsys.readouterr().out


def test_conical_shadow_is_used_when_asked(root: Path, tmp_path: Path) -> None:
    edit(root, "scenarios/day.yaml", "shadow_model: cylindrical", "shadow_model: conical")
    out = tmp_path / "o"
    assert run(root, out) == 0
    data = json.loads((out / "day_environment.json").read_text(encoding="utf-8"))
    assert data["shadow_model"] == "conical" and len(data["umbras"]) == len(data["eclipses"])


def test_spacemissionstudio_scenario_runs_from_imported_files(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = load_project(root).project
    assert project is not None
    sc = project.scenarios["day"]
    from budget_core.scenario.run import grid_for, sites_for

    env = ElementsPropagator(project.orbits["leo"]).compute(
        grid_for(sc), sites_for(project, sc), sc.shadow_model
    )
    export_spacemissionstudio(env, root / "imports" / "run1")
    edit(
        root,
        "scenarios/day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/run1",
    )
    out = tmp_path / "o"
    assert run(root, out) == 0
    data = json.loads((out / "day_environment.json").read_text(encoding="utf-8"))
    assert data["source"] == "spacemissionstudio"
    assert len(data["eclipses"]) == len(env.eclipses)


def test_broken_import_files_name_the_file_and_line(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = root / "imports" / "run1"
    folder.mkdir(parents=True)
    (folder / "orbit.csv").write_text(
        "time_utc,x_m,y_m,z_m,vx_mps,vy_mps,vz_mps\nSECRET,1,2,3,4,5,6\nx\n", encoding="utf-8"
    )
    edit(
        root,
        "scenarios/day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/run1",
    )
    assert run(root, tmp_path / "o") == 1
    text = capsys.readouterr().out
    assert "ENV_INPUT_INVALID" in text and "orbit.csv" in text and "SECRET" not in text
