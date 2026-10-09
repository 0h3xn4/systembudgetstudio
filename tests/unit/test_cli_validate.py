import json
from pathlib import Path

import pytest

from budget_cli.main import main
from tests.helpers import edit, write_valid_project


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path)
    return tmp_path


def test_valid_project_exit_zero(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(root)]) == 0
    assert "No problems found" in capsys.readouterr().out


def test_errors_exit_one_and_print_location(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    assert main(["validate", str(root)]) == 1
    out = capsys.readouterr().out
    assert "units/obc.yaml:" in out and "REF_UNKNOWN_BUS" in out and "1 error" in out


def test_warnings_exit_zero_unless_strict(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit(root, "config/margin_policy.yaml", "source: test fixture", "source: TBD")
    assert main(["validate", str(root)]) == 0
    assert "CONFIG_PLACEHOLDER" in capsys.readouterr().out
    assert main(["validate", str(root), "--strict"]) == 1


def test_json_output_is_deterministic(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    main(["validate", str(root), "--format", "json"])
    first = capsys.readouterr().out
    main(["validate", str(root), "--format", "json"])
    assert capsys.readouterr().out == first
    data = json.loads(first)
    assert data["errors"] == 1 and data["problems"][0]["code"] == "REF_UNKNOWN_BUS"


def test_missing_project_is_reported_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(tmp_path / "missing")]) == 1
    captured = capsys.readouterr()
    assert "FILE_NOT_FOUND" in captured.out and "Traceback" not in captured.out + captured.err


def test_export_schemas(tmp_path: Path) -> None:
    assert main(["export-schemas", str(tmp_path)]) == 0
    assert (tmp_path / "unit.schema.json").is_file()
