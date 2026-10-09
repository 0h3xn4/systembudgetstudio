"""Dev tooling must stay out of the runtime dependencies (spec constraint 8)."""

import re
import tomllib
from pathlib import Path

DEV_ONLY = {
    "pytest",
    "pytest-qt",
    "hypothesis",
    "mypy",
    "ruff",
    "pyinstaller",
    "cyclonedx-bom",
    "pip-licenses",
    "pip-audit",
    "pip-tools",
    "lxml",
}


def _names(specs: list[str]) -> set[str]:
    return {re.split(r"[<>=!~\[ ;]", s, maxsplit=1)[0].lower() for s in specs}


def test_runtime_dependencies_exclude_dev_tooling() -> None:
    data = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text("utf-8"))
    runtime = _names(data["project"]["dependencies"])
    dev = _names(data["project"]["optional-dependencies"]["dev"])
    assert not runtime & DEV_ONLY
    assert (DEV_ONLY - {"lxml"}) <= dev
