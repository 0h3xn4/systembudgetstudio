"""The command line never shows a traceback or project text when something unexpected happens."""

from __future__ import annotations

from pathlib import Path

import pytest

import budget_cli.main as cli
from tests.helpers import write_valid_project


def test_unexpected_exception_gives_a_plain_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def boom(_args: object) -> int:
        raise ValueError("SECRETVALUE from the project")

    monkeypatch.setattr(cli, "_validate", boom)
    code = cli.main(["validate", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "ValueError" in captured.out
    assert "SECRETVALUE" not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_unwritable_output_folder_is_a_plain_message(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root = tmp_path / "p"
    write_valid_project(root)
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    code = cli.main(["run", str(root), "--budget", "power", "--out", str(blocker)])
    out = capsys.readouterr()
    assert code == 1
    assert "could not be written" in out.out
    assert "Traceback" not in out.out + out.err


def test_output_errors_are_printed_plainly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from budget_core.reports.files import OutputError

    def refuse(*_a: object, **_k: object) -> list[Path]:
        raise OutputError("Two outputs would be written to the same file name.")

    root = tmp_path / "p"
    write_valid_project(root)
    monkeypatch.setattr(cli, "write_outputs", refuse)
    assert cli.main(["run", str(root), "--budget", "power", "--out", str(tmp_path / "o")]) == 1
    assert "same file name" in capsys.readouterr().out


def test_keyboard_interrupt_exits_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    def stop(_args: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_validate", stop)
    assert cli.main(["validate", "x"]) == 130
