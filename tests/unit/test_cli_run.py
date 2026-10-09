import json
from pathlib import Path

import pytest

from budget_cli.main import main
from tests.helpers import edit, write_valid_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FIXED = ["--user", "Test User", "--date", "2026-01-02T03:04:05Z"]


def run(*args: str) -> int:
    return main(["run", "--budget", "power", *args])


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "proj")
    return tmp_path / "proj"


def test_default_writes_all_reports_into_results(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(root), *FIXED]) == 0  # default: every budget
    out = root / "results"
    names = sorted(p.name for p in out.iterdir())
    assert [n for n in names if n.startswith("power_")] == [
        "power_static.docx",
        "power_static.json",
        "power_static.pdf",
        "power_static.xlsx",
        "power_static_downlink.csv",
        "power_static_nominal.csv",
    ]
    assert [n for n in names if n.startswith("mass_")] == [
        "mass_static.docx",
        "mass_static.json",
        "mass_static.pdf",
        "mass_static.xlsx",
        "mass_static_eol.csv",
        "mass_static_launch.csv",
    ]
    text = capsys.readouterr().out
    assert "Wrote" in text and "Traceback" not in text
    data = json.loads((out / "power_static.json").read_text(encoding="utf-8"))
    assert data["provenance"]["user"] == "Test User"
    assert data["provenance"]["generated"] == "2026-01-02T03:04:05Z"


def test_selected_reports_only(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert run(str(root), "--report", "xlsx", "--out", str(out), *FIXED) == 0
    assert [p.name for p in out.iterdir()] == ["power_static.xlsx"]


def test_regeneration_is_byte_identical(root: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    assert run(str(root), "--out", str(a), *FIXED) == 0
    assert run(str(root), "--out", str(b), *FIXED) == 0
    for p in sorted(a.iterdir()):
        assert p.read_bytes() == (b / p.name).read_bytes(), p.name


def test_source_date_epoch_is_used(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "86400")
    out = tmp_path / "out"
    assert run(str(root), "--report", "json", "--out", str(out), "--user", "U") == 0
    assert "1970-01-02T00:00:00Z" in (out / "power_static.json").read_text(encoding="utf-8")


def test_errors_stop_the_run_and_write_nothing(
    root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    out = tmp_path / "out"
    assert run(str(root), "--out", str(out), *FIXED) == 1
    assert not out.exists()
    assert "REF_UNKNOWN_BUS" in capsys.readouterr().out


def test_placeholders_warn_but_succeed_unless_strict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert run(str(EXAMPLES / "cubesat_3u"), "--out", str(out), *FIXED) == 0
    text = capsys.readouterr().out
    assert "INCOMPLETE" in text and "n/a" in text
    assert run(str(EXAMPLES / "cubesat_3u"), "--out", str(out), "--strict", *FIXED) == 1


def test_invalid_date_is_a_usage_error(root: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        run(str(root), "--date", "yesterday")
    assert exc.value.code == 2


def test_missing_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(str(tmp_path / "nope")) == 1
    assert "FILE_NOT_FOUND" in capsys.readouterr().out
