from __future__ import annotations

from pathlib import Path

import pytest

from budget_cli.main import main

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_guide_writes_html_and_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide", "--out", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "system-budget-studio-guide.html",
        "system-budget-studio-guide.pdf",
    ]
    html = (tmp_path / "system-budget-studio-guide.html").read_text(encoding="utf-8")
    assert "Equations and sources" in html
    assert "Wrote" in capsys.readouterr().out


def test_guide_format_and_project(tmp_path: Path) -> None:
    code = main(
        [
            "guide",
            "--out",
            str(tmp_path),
            "--format",
            "html",
            "--project",
            str(EXAMPLES / "cubesat_3u"),
        ]
    )
    assert code == 0
    files = [p.name for p in tmp_path.iterdir()]
    assert files == ["system-budget-studio-guide.html"]
    html = (tmp_path / files[0]).read_text(encoding="utf-8")
    assert "Numbers in the configuration of" in html and "PLACEHOLDER" in html


def test_guide_is_byte_identical(tmp_path: Path) -> None:
    for name in ("a", "b"):
        main(["guide", "--out", str(tmp_path / name)])
    for file in ("system-budget-studio-guide.html", "system-budget-studio-guide.pdf"):
        assert (tmp_path / "a" / file).read_bytes() == (tmp_path / "b" / file).read_bytes()


def test_guide_with_a_broken_project_stops(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["guide", "--out", str(tmp_path / "o"), "--project", str(tmp_path / "missing")])
    assert code == 1
    assert "nothing was written" in capsys.readouterr().out
