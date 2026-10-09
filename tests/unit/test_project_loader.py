from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project, write_project
from budget_core.problems import Problem
from tests.helpers import build_project, edit, line_of, write_valid_project


def codes(problems: list[Problem]) -> list[str]:
    return [p.code for p in problems]


def only(problems: list[Problem], code: str) -> Problem:
    found = [p for p in problems if p.code == code]
    assert len(found) == 1, f"expected exactly one {code}, got {codes(problems)}"
    return found[0]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path)
    return tmp_path


def test_valid_project_loads_cleanly(root: Path) -> None:
    result = load_project(root)
    assert result.problems == []
    assert result.project is not None
    assert sorted(result.project.units) == ["obc", "radio"]
    assert result.project.units["radio"].modes[1].name == "tx"
    assert result.project.modes["downlink"].assignments == {"obc": "on", "radio": "tx"}


def test_write_then_load_then_write_is_byte_identical(
    root: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    result = load_project(root)
    assert result.project is not None
    second = tmp_path_factory.mktemp("second")
    write_project(result.project, second)
    first_files = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    second_files = sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
    assert first_files == second_files
    for rel in first_files:
        assert (root / rel).read_bytes() == (second / rel).read_bytes(), rel


def test_files_are_lf_only_and_end_with_newline(root: Path) -> None:
    for path in root.rglob("*.yaml"):
        data = path.read_bytes()
        assert b"\r" not in data and data.endswith(b"\n") and not data.endswith(b"\n\n")


def test_missing_directory(tmp_path: Path) -> None:
    result = load_project(tmp_path / "nope")
    assert codes(result.problems) == ["FILE_NOT_FOUND"] and result.project is None


def test_missing_required_files(root: Path) -> None:
    (root / "project.yaml").unlink()
    (root / "spacecraft.yaml").unlink()
    result = load_project(root)
    found = sorted(p.file or "" for p in result.problems if p.code == "FILE_NOT_FOUND")
    assert found == ["project.yaml", "spacecraft.yaml"]
    assert result.project is None


def test_yaml_syntax_error_is_located(root: Path) -> None:
    edit(root, "units/obc.yaml", "subsystem: TEST", "subsystem: [unclosed")
    p = only(load_project(root).problems, "YAML_SYNTAX")
    assert p.file == "units/obc.yaml" and p.line is not None and p.severity.value == "error"


def test_not_a_mapping(root: Path) -> None:
    (root / "units" / "obc.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    assert only(load_project(root).problems, "FILE_INVALID").file == "units/obc.yaml"


def test_not_utf8(root: Path) -> None:
    (root / "units" / "obc.yaml").write_bytes(b"\xff\xfe\x00bad")
    assert only(load_project(root).problems, "FILE_INVALID").file == "units/obc.yaml"


def test_schema_version_missing_and_too_new(root: Path) -> None:
    edit(root, "units/obc.yaml", "schema_version: 1\n", "")
    edit(root, "units/radio.yaml", "schema_version: 1", "schema_version: 7")
    problems = load_project(root).problems
    assert only(problems, "SCHEMA_VERSION_MISSING").file == "units/obc.yaml"
    assert only(problems, "SCHEMA_TOO_NEW").file == "units/radio.yaml"


def test_kind_mismatch(root: Path) -> None:
    edit(root, "units/obc.yaml", "kind: unit", "kind: spacecraft")
    assert only(load_project(root).problems, "KIND_MISMATCH").file == "units/obc.yaml"


def test_missing_field_is_located_and_actionable(root: Path) -> None:
    edit(root, "units/obc.yaml", "subsystem: TEST\n", "")
    p = only(load_project(root).problems, "FIELD_MISSING")
    assert p.file == "units/obc.yaml" and "subsystem" in p.message and "subsystem" in p.hint


def test_unknown_field_suggests_closest(root: Path) -> None:
    edit(root, "units/obc.yaml", "mass_kg:", "mas_kg:")
    p = only(load_project(root).problems, "FIELD_UNKNOWN")
    assert "mass_kg" in p.hint
    assert p.line == line_of(root, "units/obc.yaml", "mas_kg:")


def test_bad_unit_points_at_the_value_line(root: Path) -> None:
    edit(root, "units/radio.yaml", "avg_power_w: 5.0", "avg_power_w: 3 dBW")
    p = only(load_project(root).problems, "UNIT_INVALID")
    assert p.file == "units/radio.yaml"
    assert p.path == "modes[1].avg_power_w"
    assert p.line == line_of(root, "units/radio.yaml", "avg_power_w: 3 dBW")
    assert "W" in p.hint


def test_unit_strings_are_accepted_and_normalised(root: Path) -> None:
    edit(root, "units/radio.yaml", "avg_power_w: 5.0", "avg_power_w: 5000 mW")
    result = load_project(root)
    assert result.problems == []
    assert result.project is not None
    assert result.project.units["radio"].modes[1].avg_power_w == pytest.approx(5.0)


def test_messages_never_echo_file_values(root: Path) -> None:
    edit(root, "units/obc.yaml", "mass_kg: 0.2", "mass_kg: SECRETVALUE")
    edit(
        root, "units/radio.yaml", "name: Radio", "name: SECRETNAME\nunknownSECRETKEY: SECRETVALUE2"
    )
    for p in load_project(root).problems:
        text = p.format().upper()
        assert "SECRETVALUE" not in text and "SECRETNAME" not in text


def test_range_and_cross_field_rules_are_located(root: Path) -> None:
    edit(root, "units/radio.yaml", "peak_power_w: 8.0", "peak_power_w: 2.0")
    p = only(load_project(root).problems, "FIELD_INVALID")
    assert p.path == "modes[1].peak_power_w"


def test_duplicate_mode_names(root: Path) -> None:
    edit(root, "units/radio.yaml", "name: tx", "name: rx")
    assert only(load_project(root).problems, "DUPLICATE_NAME").path == "modes"


def test_unknown_bus_and_maturity(root: Path) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    edit(root, "units/radio.yaml", "maturity: m1", "maturity: m9")
    problems = load_project(root).problems
    bus = only(problems, "REF_UNKNOWN_BUS")
    assert bus.file == "units/obc.yaml" and bus.line == line_of(root, "units/obc.yaml", "bus: nope")
    assert "main" in bus.hint
    assert only(problems, "REF_UNKNOWN_MATURITY").file == "units/radio.yaml"


def test_mode_references(root: Path) -> None:
    edit(root, "modes/nominal.yaml", "radio: rx", "ghost: on")
    edit(root, "modes/downlink.yaml", "radio: tx", "radio: warp")
    problems = load_project(root).problems
    assert only(problems, "REF_UNKNOWN_UNIT").file == "modes/nominal.yaml"
    assert only(problems, "REF_UNKNOWN_UNIT_MODE").file == "modes/downlink.yaml"
    unmapped = only(problems, "UNIT_NOT_MAPPED")
    assert unmapped.file == "modes/nominal.yaml" and "radio" in unmapped.message


def test_placeholders_are_warnings_with_location(root: Path) -> None:
    edit(root, "config/margin_policy.yaml", "source: test fixture", "source: TBD")
    problems = [p for p in load_project(root).problems if p.code == "CONFIG_PLACEHOLDER"]
    assert problems and all(p.severity.value == "warning" for p in problems)
    assert all(p.file == "config/margin_policy.yaml" for p in problems)
    assert any(p.path.startswith("classes.m1") for p in problems)


def test_null_value_is_a_placeholder(root: Path) -> None:
    edit(
        root,
        "config/power_config.yaml",
        "distribution_loss_ratio:\n  value: 0.02",
        "distribution_loss_ratio:\n  value: null",
    )
    p = only(load_project(root).problems, "CONFIG_PLACEHOLDER")
    assert p.path == "distribution_loss_ratio"


def test_missing_config_and_empty_tables_are_warnings(root: Path) -> None:
    (root / "config" / "margin_policy.yaml").unlink()
    write = root / "config" / "ebn0_table.yaml"
    write.write_text("schema_version: 1\nkind: ebn0_table\nentries: []\n", encoding="utf-8")
    problems = load_project(root).problems
    assert only(problems, "CONFIG_MISSING").file == "config/margin_policy.yaml"
    assert only(problems, "CONFIG_EMPTY_TABLE").file == "config/ebn0_table.yaml"
    assert all(p.severity.value == "warning" for p in problems)


def test_converter_efficiency_must_reference_a_bus(root: Path) -> None:
    edit(root, "config/power_config.yaml", "  main:", "  other:")
    assert only(load_project(root).problems, "REF_UNKNOWN_BUS").file == "config/power_config.yaml"


def test_source_is_required_on_config_numbers(root: Path) -> None:
    edit(root, "config/margin_policy.yaml", "source: test fixture", "source: ''")
    assert "SOURCE_MISSING" in codes(load_project(root).problems)


def test_problems_are_sorted_and_deterministic(root: Path) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    edit(root, "modes/nominal.yaml", "radio: rx", "ghost: on")
    first = load_project(root).problems
    assert first == load_project(root).problems
    assert [p.file for p in first] == sorted(p.file or "" for p in first)


def test_no_project_returned_when_errors(root: Path) -> None:
    edit(root, "units/obc.yaml", "bus: main", "bus: nope")
    assert load_project(root).project is None


def test_build_project_helper_matches_loader(root: Path) -> None:
    loaded = load_project(root).project
    assert loaded is not None
    expected = build_project(root)
    assert loaded.units == expected.units and loaded.config == expected.config


@pytest.mark.parametrize(
    ("file", "old", "new"),
    [
        ("config/power_config.yaml", "value: 0.9", "value: 0.0"),  # efficiency must be > 0
        ("config/power_config.yaml", "value: 0.9", "value: 1.5"),  # efficiency must be <= 1
        ("config/power_config.yaml", "value: 0.02", "value: 1.0"),  # loss must be < 1
        ("config/power_config.yaml", "value: 0.02", "value: -0.1"),
        ("config/margin_policy.yaml", "value: 0.05", "value: -0.5"),  # margin must be >= 0
    ],
)
def test_config_values_must_be_physically_meaningful(
    root: Path, file: str, old: str, new: str
) -> None:
    edit(root, file, old, new)
    p = only(load_project(root).problems, "CONFIG_VALUE_INVALID")
    assert p.file == file and p.severity.value == "error" and p.line is not None


def test_placeholder_values_are_not_range_checked(root: Path) -> None:
    edit(
        root,
        "config/power_config.yaml",
        "value: 0.9\n    source: test fixture",
        "value: 0.0\n    source: TBD",
    )
    assert "CONFIG_VALUE_INVALID" not in codes(load_project(root).problems)


def test_unit_phase_must_exist(root: Path) -> None:
    edit(root, "units/obc.yaml", "mass_properties:", "phases:\n  - warp\nmass_properties:")
    p = only(load_project(root).problems, "REF_UNKNOWN_PHASE")
    assert p.file == "units/obc.yaml" and p.path == "phases[0]" and "launch" in p.hint


def test_expendable_needs_a_mass_for_every_phase_and_only_known_phases(root: Path) -> None:
    edit(root, "expendables/fuel.yaml", "  eol: 0.5\n", "  warp: 0.5\n")
    problems = load_project(root).problems
    assert only(problems, "PHASE_MASS_MISSING").file == "expendables/fuel.yaml"
    assert only(problems, "REF_UNKNOWN_PHASE").path == "masses_kg.warp"


def test_expendable_maturity_must_exist(root: Path) -> None:
    edit(root, "expendables/fuel.yaml", "maturity: m1", "maturity: m9")
    assert only(load_project(root).problems, "REF_UNKNOWN_MATURITY").file == "expendables/fuel.yaml"


def test_mass_limit_phase_must_exist_and_value_must_be_positive(root: Path) -> None:
    edit(root, "config/mass_limits.yaml", "phase: launch", "phase: warp")
    edit(root, "config/mass_limits.yaml", "value: 100.0", "value: 0.0")
    problems = load_project(root).problems
    assert only(problems, "REF_UNKNOWN_PHASE").file == "config/mass_limits.yaml"
    assert only(problems, "CONFIG_VALUE_INVALID").path == "limits[0].limit_kg.value"


def test_positions_without_a_body_frame_warn(root: Path) -> None:
    edit(root, "spacecraft.yaml", "body_frame: test frame\n", "")
    p = only(load_project(root).problems, "MASS_FRAME_UNDEFINED")
    assert p.file == "spacecraft.yaml" and p.severity.value == "warning"


def test_empty_mass_limits_table_is_a_warning(root: Path) -> None:
    (root / "config" / "mass_limits.yaml").write_text(
        "schema_version: 1\nkind: mass_limits\nlimits: []\n", encoding="utf-8"
    )
    assert only(load_project(root).problems, "CONFIG_EMPTY_TABLE").file == "config/mass_limits.yaml"


def test_schema_v1_margin_policy_migrates_with_placeholder_mass_margins(root: Path) -> None:
    (root / "config" / "margin_policy.yaml").write_text(
        "schema_version: 1\nkind: margin_policy\nclasses:\n  m1:\n    margin_ratio:\n"
        "      value: 0.1\n      source: test fixture\n  m2:\n    margin_ratio:\n"
        "      value: 0.2\n      source: test fixture\nsystem_margin_ratio:\n"
        "  value: 0.05\n  source: test fixture\n",
        encoding="utf-8",
    )
    result = load_project(root)
    codes_ = codes(result.problems)
    assert "FILE_MIGRATED" in codes_
    assert not [p for p in result.problems if p.severity.value == "error"]
    assert result.project is not None
    policy = result.project.config.margin_policy
    assert policy is not None
    assert policy.classes["m1"].power_margin_ratio.value == 0.1
    assert policy.classes["m1"].mass_margin_ratio.is_placeholder
    assert policy.system_power_margin_ratio.value == 0.05
    assert policy.system_mass_margin_ratio.is_placeholder
    assert codes_.count("CONFIG_PLACEHOLDER") == 3  # m1, m2 and system mass margins


# ---- environment and scenarios ------------------------------------------------------------------


def test_scenario_must_reference_an_existing_orbit_and_sites(root: Path) -> None:
    edit(root, "scenarios/day.yaml", "orbit: leo", "orbit: nope")
    edit(root, "scenarios/day.yaml", "- tgt1\n", "- ghost\n")
    problems = load_project(root).problems
    assert only(problems, "REF_UNKNOWN_ORBIT").file == "scenarios/day.yaml"
    unknown = [p for p in problems if p.code == "REF_UNKNOWN_SITE"]
    assert unknown and all(p.file == "scenarios/day.yaml" for p in unknown)


def test_rule_site_must_be_listed_in_the_scenario(root: Path) -> None:
    edit(root, "scenarios/day.yaml", "- gs1\n", "")
    p = only(load_project(root).problems, "REF_UNKNOWN_SITE")
    assert "rules" in p.path and "gs1" in p.message


def test_scenario_modes_must_exist(root: Path) -> None:
    edit(root, "scenarios/day.yaml", "default_mode: nominal", "default_mode: warp")
    edit(root, "scenarios/day.yaml", "mode: downlink", "mode: hyperspace")
    problems = [p for p in load_project(root).problems if p.code == "REF_UNKNOWN_MODE"]
    assert {p.path for p in problems} == {"default_mode", "rules[0].mode"}


def test_site_ids_are_unique_across_stations_and_targets(root: Path) -> None:
    (root / "targets" / "gs1.yaml").write_text(
        (root / "targets" / "tgt1.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    p = only(load_project(root).problems, "DUPLICATE_ID")
    assert p.file == "targets/gs1.yaml"


def test_a_missing_import_folder_is_reported(root: Path) -> None:
    edit(
        root,
        "scenarios/day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/run1",
    )
    p = only(load_project(root).problems, "IMPORT_DIR_MISSING")
    assert p.file == "scenarios/day.yaml"


def test_an_orbit_that_cannot_be_propagated_is_reported(root: Path) -> None:
    edit(root, "orbits/leo.yaml", "eccentricity_ratio: 0.001", "eccentricity_ratio: 0.6")
    p = only(load_project(root).problems, "ORBIT_INVALID")
    assert p.file == "orbits/leo.yaml"


def test_scenario_file_errors_are_located(root: Path) -> None:
    edit(root, "scenarios/day.yaml", "duration_s: 86400.0", "duration_s: 0.0")
    assert only(load_project(root).problems, "FIELD_INVALID").file == "scenarios/day.yaml"
    edit(root, "orbits/leo.yaml", "inclination_deg: 97.5", "inclination_deg: 200.0")
    assert "FIELD_INVALID" in codes(load_project(root).problems)


def test_unquoted_iso_times_in_files_are_accepted(root: Path) -> None:
    edit(
        root,
        "scenarios/day.yaml",
        "start_utc: '2026-01-01T00:00:00Z'",
        "start_utc: 2026-01-01T00:00:00Z",
    )
    result = load_project(root)
    assert result.problems == [] and result.project is not None
    assert result.project.scenarios["day"].start_utc == "2026-01-01T00:00:00Z"
