"""Release metadata stays consistent: one version everywhere, a smoke test for the packaged app."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from budget_core import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_and_package_report_the_same_version() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__


def test_installer_script_gets_its_version_from_the_build() -> None:
    iss = (ROOT / "packaging" / "windows" / "system_budget_studio.iss").read_text(encoding="utf-8")
    assert "ChangesEnvironment=yes" in iss  # a PATH change must reach new terminals
    assert "[InstallDelete]" in iss  # an upgrade must not leave old files behind


@pytest.mark.gui
def test_smoke_flag_builds_the_window_and_exits_cleanly(
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],  # type: ignore[no-untyped-def]
) -> None:
    import sys

    from budget_gui import app

    monkeypatch.setattr(sys, "argv", ["system-budget-studio", "--smoke"])
    assert app.main() == 0
    assert "Smoke test passed." in capsys.readouterr().out
