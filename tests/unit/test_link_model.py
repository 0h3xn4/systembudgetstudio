"""Link files: loading, references, ranges, placeholders, antenna and receiver rules, suffixes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from budget_core.io.project_loader import load_project, write_project
from budget_core.model import Antenna, AntennaPattern, Receiver
from budget_core.problems import Problem
from budget_core.units.quantity import UnitError, parse_quantity
from tests.helpers import edit
from tests.link_helpers import downlink, link_project
from tests.power_helpers import sv

LINK = "links/dl.yaml"


def relevant(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.code != "CONFIG_MISSING"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_project(link_project(tmp_path), tmp_path)
    return tmp_path


def test_a_complete_link_project_loads_cleanly(root: Path) -> None:
    result = load_project(root)
    assert relevant(result.problems) == [] and result.project is not None
    link = result.project.links["dl"]
    assert link.data_rates_bps == [10e3, 100e3, 1e6] and link.peer == "gs"


def test_new_db_per_kelvin_suffix() -> None:
    assert parse_quantity("-7.5 dB/K", "g_over_t_dbk") == -7.5
    assert parse_quantity("3 dBK", "g_over_t_dbk") == 3.0
    with pytest.raises(UnitError):
        parse_quantity("3 dBW", "g_over_t_dbk")  # W and dB/K are not converted implicitly


def test_values_with_units_in_a_link_file(root: Path) -> None:
    edit(root, LINK, "frequency_hz: 2000000000.0", "frequency_hz: 2.0 GHz")
    result = load_project(root)
    assert result.project is not None and result.project.links["dl"].frequency_hz == 2.0e9


def test_unknown_station_mode_attenuation_and_modulation(root: Path) -> None:
    edit(root, LINK, "peer: gs", "peer: nowhere")
    edit(root, LINK, "modulation: TEST", "modulation: OTHER")
    path = root / LINK
    path.write_text(
        path.read_text(encoding="utf-8").replace("attenuation: []\nactive_modes: []\n", "")
        + "attenuation:\n  - fog\nactive_modes:\n  - zzz\n",
        encoding="utf-8",
        newline="\n",
    )
    codes = {(p.code, p.path) for p in load_project(root).problems}
    assert ("REF_UNKNOWN_STATION", "peer") in codes
    assert ("REF_UNKNOWN_MODULATION", "modulation") in codes
    assert ("REF_UNKNOWN_ATTENUATION", "attenuation[0]") in codes
    assert ("REF_UNKNOWN_MODE", "active_modes[0]") in codes


def test_a_ground_antenna_must_have_a_constant_gain(tmp_path: Path) -> None:
    pattern = AntennaPattern(source="fixture", angles_deg=[0.0, 90.0], gains_dbi=[10.0, 0.0])
    link = downlink(
        receiver=Receiver(
            antenna=Antenna(pattern=pattern),
            system_noise_temperature_k=sv(300.0),
            feed_loss_db=sv(0.5),
        )
    )
    write_project(link_project(tmp_path, links={"dl": link}), tmp_path)
    bad = next(
        p for p in load_project(tmp_path).problems if p.code == "LINK_ANTENNA_PATTERN_GROUND"
    )
    assert bad.file == LINK and bad.path == "receiver.antenna" and bad.line is not None


def test_a_missing_pattern_file_is_reported(tmp_path: Path) -> None:
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="patterns/none.csv", pattern_source="fixture")}
    )
    write_project(link_project(tmp_path, links={"dl": downlink(transmitter=tx)}), tmp_path)
    bad = next(p for p in load_project(tmp_path).problems if p.code == "LINK_PATTERN_FILE_MISSING")
    assert bad.path == "transmitter.antenna.pattern_file" and "project folder" in bad.hint


def test_range_errors_name_the_field(root: Path) -> None:
    edit(root, LINK, "power_w:\n    value: 2.0", "power_w:\n    value: 0.0")
    edit(root, LINK, "pointing_loss_db:\n  value: 1.0", "pointing_loss_db:\n  value: -1.0")
    bad = {p.path for p in load_project(root).problems if p.code == "CONFIG_VALUE_INVALID"}
    assert bad == {"transmitter.power_w.value", "pointing_loss_db.value"}


def test_placeholders_are_reported(tmp_path: Path) -> None:
    tx = downlink().transmitter.model_copy(update={"power_w": sv(None)})
    write_project(link_project(tmp_path, links={"dl": downlink(transmitter=tx)}), tmp_path)
    found = [
        p
        for p in load_project(tmp_path).problems
        if p.code == "CONFIG_PLACEHOLDER" and p.file == LINK
    ]
    assert [p.path for p in found] == ["transmitter.power_w"]


def test_a_placeholder_pattern_is_reported(tmp_path: Path) -> None:
    pattern = AntennaPattern(source="TBD", angles_deg=[0.0, 90.0], gains_dbi=[10.0, 0.0])
    tx = downlink().transmitter.model_copy(update={"antenna": Antenna(pattern=pattern)})
    write_project(link_project(tmp_path, links={"dl": downlink(transmitter=tx)}), tmp_path)
    found = [p for p in load_project(tmp_path).problems if p.code == "CONFIG_PLACEHOLDER"]
    assert any(p.path == "transmitter.antenna.pattern.source" for p in found)


# ---- model rules ---------------------------------------------------------------------------


def test_an_antenna_needs_exactly_one_gain_model() -> None:
    with pytest.raises(ValidationError):
        Antenna()
    with pytest.raises(ValidationError):
        Antenna(gain_dbi=sv(3.0), pattern_file="x.csv", pattern_source="s")
    with pytest.raises(ValidationError):
        Antenna(pattern_file="x.csv")  # no source


def test_a_pattern_table_must_increase() -> None:
    with pytest.raises(ValidationError):
        AntennaPattern(source="s", angles_deg=[0.0, 0.0], gains_dbi=[1.0, 2.0])
    with pytest.raises(ValidationError):
        AntennaPattern(source="s", angles_deg=[0.0, 200.0], gains_dbi=[1.0, 2.0])
    with pytest.raises(ValidationError):
        AntennaPattern(source="s", angles_deg=[0.0, 10.0], gains_dbi=[1.0])


def test_a_receiver_gives_g_over_t_or_the_parts_not_both() -> None:
    antenna = Antenna(gain_dbi=sv(10.0))
    Receiver(g_over_t_dbk=sv(-5.0))
    Receiver(antenna=antenna, system_noise_temperature_k=sv(300.0), feed_loss_db=sv(0.5))
    with pytest.raises(ValidationError):
        Receiver()
    with pytest.raises(ValidationError):
        Receiver(g_over_t_dbk=sv(-5.0), antenna=antenna)
    with pytest.raises(ValidationError):
        Receiver(antenna=antenna, system_noise_temperature_k=sv(300.0))


def test_data_rates_are_sorted_and_must_be_positive() -> None:
    assert downlink(data_rates_bps=[1e6, 1e3, 1e3]).model_copy().data_rates_bps == [1e6, 1e3, 1e3]
    with pytest.raises(ValidationError):
        type(downlink()).model_validate({**downlink().model_dump(), "data_rates_bps": [0.0]})
    sorted_link = type(downlink()).model_validate(
        {**downlink().model_dump(), "data_rates_bps": [1e6, 1e3, 1e3]}
    )
    assert sorted_link.data_rates_bps == [1e3, 1e6]
