"""Hostile or sloppy project input must give a located, plain Problem, never a hang, a crash or
an echo of the project's own text (spec constraints 11 and 20)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import YamlSyntaxError, load_yaml_text
from budget_core.problems import Severity
from budget_core.units.quantity import UnitError, parse_quantity
from tests.helpers import edit, write_valid_project

FAST_S = 2.0


def errors_of(root: Path) -> list[str]:
    result = load_project(root)
    return [p.code for p in result.problems if p.severity is Severity.ERROR]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "p")
    return tmp_path / "p"


# ---- unit tokens ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "1 (9**9**9) W",
        "1 W**9**9",
        "1 W^99^99",
        "1 (W)",
        "1 W " + "x" * 40,
        "1 W**100000",
    ],
)
def test_expression_tokens_are_rejected_quickly(text: str) -> None:
    started = time.perf_counter()
    with pytest.raises(UnitError):
        parse_quantity(text, "power_w")
    assert time.perf_counter() - started < FAST_S


@pytest.mark.parametrize(
    ("text", "field", "expected"),
    [
        ("2.5 W", "power_w", 2.5),
        ("2.2 GHz", "freq_hz", 2.2e9),
        ("35 min", "duration_s", 2100.0),
        ("1000 W/m^2", "irradiance_wm2", 1000.0),
        ("25 degC", "temperature_k", 298.15),
        ("2 cm^2", "area_m2", 2e-4),
    ],
)
def test_ordinary_units_still_parse(text: str, field: str, expected: float) -> None:
    assert parse_quantity(text, field) == pytest.approx(expected)


def test_unit_error_does_not_echo_the_token() -> None:
    with pytest.raises(UnitError) as info:
        parse_quantity("1 SECRETUNIT", "power_w")
    assert "SECRETUNIT" not in str(info.value)


def test_huge_magnitudes_are_rejected() -> None:
    with pytest.raises(UnitError):
        parse_quantity("1e305 kW", "power_w")


def test_a_hang_in_a_project_file_becomes_a_problem(root: Path) -> None:
    started = time.perf_counter()
    edit(root, "units/obc.yaml", "avg_power_w: 1.0", "avg_power_w: '1 (9**9**9) W'")
    assert "FIELD_INVALID" in errors_of(root) or "UNIT_INVALID" in errors_of(root)
    assert time.perf_counter() - started < 10.0


# ---- YAML ------------------------------------------------------------------------------------
def bomb(levels: int) -> str:
    lines = ["a0: &a0 [x,x,x,x,x,x,x,x,x,x,x,x,x]"]
    for i in range(1, levels):
        refs = ",".join([f"*a{i - 1}"] * 13)
        lines.append(f"a{i}: &a{i} [{refs}]")
    return "\n".join(lines) + "\n"


def test_alias_bomb_is_rejected_quickly() -> None:
    started = time.perf_counter()
    with pytest.raises(YamlSyntaxError):
        load_yaml_text(bomb(7))
    assert time.perf_counter() - started < FAST_S


def test_merge_key_gives_a_clear_error_not_a_crash() -> None:
    with pytest.raises(YamlSyntaxError) as info:
        load_yaml_text("base: &b {x: 1}\nother:\n  <<: *b\n  y: 2\n")
    assert "alias" in str(info.value).lower()


def test_deep_nesting_is_an_error_not_a_recursion_error() -> None:
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("a: " + "[" * 600 + "]" * 600 + "\n")


def test_invalid_date_is_an_error() -> None:
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("start: 2020-13-45\n")


def test_overlong_integer_is_an_error() -> None:
    with pytest.raises(YamlSyntaxError):
        load_yaml_text("n: " + "9" * 5000 + "\n")


def test_oversized_file_is_refused(root: Path) -> None:
    path = root / "units" / "obc.yaml"
    path.write_text("name: x\n" + "# " + "pad" * 800_000 + "\n", encoding="utf-8")
    result = load_project(root)
    problem = next(p for p in result.problems if p.file == "units/obc.yaml")
    assert problem.code == "FILE_INVALID" and "too large" in problem.message


def test_alias_in_a_project_file_is_a_located_problem(root: Path) -> None:
    path = root / "units" / "obc.yaml"
    path.write_text(
        path.read_text(encoding="utf-8") + "extra: &x [1]\nmore: *x\n", encoding="utf-8"
    )
    result = load_project(root)
    problem = next(p for p in result.problems if p.file == "units/obc.yaml")
    assert problem.code == "YAML_SYNTAX"


# ---- model validation never raises ----------------------------------------------------------
def test_overflowing_inertia_is_a_problem_not_an_exception(root: Path) -> None:
    path = root / "units" / "obc.yaml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "  inertia:\n    ixx_kgm2: 1.0\n    iyy_kgm2: 1.0\n    izz_kgm2: 1.0\n"
        "    ixy_kgm2: 1.0e200\n",
        encoding="utf-8",
    )
    assert errors_of(root)  # a Problem; OverflowError must not escape


def test_huge_number_in_a_field_is_an_error(root: Path) -> None:
    edit(root, "units/obc.yaml", "mass_kg: 0.2", "mass_kg: 1.0e308")
    assert errors_of(root)


# ---- scenario limits -------------------------------------------------------------------------
def test_scenario_sample_limit_is_about_a_million() -> None:
    from budget_core.model import environment

    assert environment.MAX_SAMPLES <= 2_000_000
    # a week at one second (the documented performance case) must still be allowed
    assert environment.MAX_SAMPLES >= 604_800 + 1
