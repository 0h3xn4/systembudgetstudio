"""The three reference projects: valid, only placeholder warnings, no drift from the generator."""

from pathlib import Path

import pytest

from budget_core.examples import EXAMPLES, export_examples
from budget_core.io.project_loader import load_project

ROOT = Path(__file__).resolve().parents[2] / "examples"
ALLOWED_WARNINGS = {"CONFIG_PLACEHOLDER", "CONFIG_EMPTY_TABLE"}


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_example_has_no_errors_and_only_placeholder_warnings(name: str) -> None:
    result = load_project(ROOT / name)
    assert result.project is not None
    assert {p.code for p in result.problems} <= ALLOWED_WARNINGS
    assert {p.code for p in result.problems} == ALLOWED_WARNINGS  # config is deliberately TBD


def test_committed_examples_match_generator(tmp_path: Path) -> None:
    export_examples(tmp_path)
    expected = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.yaml"))
    committed = sorted(p.relative_to(ROOT) for p in ROOT.rglob("*.yaml"))
    assert expected == committed
    for rel in expected:
        assert (tmp_path / rel).read_bytes() == (ROOT / rel).read_bytes(), rel


def test_example_sizes() -> None:
    assert len(load_project(ROOT / "cubesat_3u").project.units) == 6  # type: ignore[union-attr]
    assert len(load_project(ROOT / "microsat_150kg").project.units) == 17  # type: ignore[union-attr]
    stress = load_project(ROOT / "stress_200_units").project
    assert stress is not None and len(stress.units) == 200 and len(stress.modes) == 5


def test_every_unit_is_mapped_in_every_mode() -> None:
    for name in EXAMPLES:
        project = load_project(ROOT / name).project
        assert project is not None
        for mode in project.modes.values():
            assert set(mode.assignments) == set(project.units)


def test_examples_contain_no_numbers_from_standards() -> None:
    """Config numbers are placeholders: every Sourced value is null with source TBD."""
    from budget_core.io.validation import iter_sourced

    for name in EXAMPLES:
        project = load_project(ROOT / name).project
        assert project is not None
        for model in (
            project.config.margin_policy,
            project.config.power_config,
            project.config.mass_limits,
        ):
            for _, sourced in iter_sourced(model):
                assert sourced.value is None and sourced.source == "TBD"
