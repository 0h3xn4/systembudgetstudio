"""Link budget against hand calculations (round numbers, see link_helpers)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from budget_core.link import budget as lb
from budget_core.link.constants import BOLTZMANN_DBW_HZ_K, EARTH_RADIUS_M
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.model import Antenna, AntennaPattern, Receiver, ScenarioRule
from tests.link_helpers import downlink, link_project, pass_run
from tests.power_helpers import sv

# Hand-worked values of the test link (see link_helpers):
EIRP = 10.0 * math.log10(2.0) - 1.0 + 6.0  # 8.0103 dBW
FSPL_1000KM = 158.4684  # 20 log10(4 pi 1e6 m 2e9 Hz / c)
GT_FILE = -7.4897  # the link file states G/T directly
CN0 = 68.6514  # 8.0103 - 158.4684 - 2 - 7.4897 + 228.5992


# ---- 1-9: equations -------------------------------------------------------------------------


def test_free_space_path_loss_of_the_textbook_s_band_case() -> None:
    # 2 GHz at 1000 km: 20 log10(d km) + 20 log10(f MHz) + 32.4478 = 60 + 66.0206 + 32.4478
    assert float(lb.free_space_path_loss_db(1.0e6, 2.0e9)) == pytest.approx(158.4684, abs=0.005)


def test_free_space_path_loss_grows_6_db_per_doubling_of_range() -> None:
    a, b = lb.free_space_path_loss_db(np.array([1.0e6, 2.0e6]), 2.0e9)
    assert b - a == pytest.approx(20.0 * math.log10(2.0), abs=1e-9)


def test_boltzmann_constant_in_db() -> None:
    assert pytest.approx(-228.5992, abs=1e-3) == BOLTZMANN_DBW_HZ_K


def test_eirp() -> None:
    # 2 W = 3.0103 dBW, minus 1 dB line loss, plus 6 dBi
    assert lb.eirp_dbw(2.0, 1.0, 6.0) == pytest.approx(8.0103, abs=1e-4)


def test_figure_of_merit() -> None:
    # 20 dBi - 0.5 dB feed - 10 log10(500 K) = 20 - 0.5 - 26.9897
    assert lb.g_over_t_dbk(20.0, 0.5, 500.0) == pytest.approx(-7.4897, abs=1e-4)


def test_carrier_to_noise_density_and_eb_n0() -> None:
    cn0 = lb.cn0_dbhz(EIRP, FSPL_1000KM, 2.0, GT_FILE)
    assert cn0 == pytest.approx(CN0, abs=2e-4)
    assert lb.ebn0_db(cn0, 100e3) == pytest.approx(cn0 - 50.0, abs=1e-9)
    assert lb.margin_db(CN0 - 50.0, 10.0) == pytest.approx(8.6514, abs=2e-4)


def test_rate_at_which_the_margin_equals_the_requirement() -> None:
    # C/N0 68.6514 - Eb/N0 10 - margin 3 = 55.6514 dBHz: 10^5.56514 = 367 kbit/s
    assert float(lb.max_rate_for_margin_bps(CN0, 10.0, 3.0)) == pytest.approx(3.672e5, rel=2e-3)


def test_nadir_angle_geometry() -> None:
    assert float(lb.nadir_angle_deg(90.0, 500e3)) == pytest.approx(0.0, abs=1e-9)
    r = EARTH_RADIUS_M + 500e3
    horizon_range = math.sqrt(r * r - EARTH_RADIUS_M**2)
    # at the horizon: sin(eta) = R / r
    assert float(lb.nadir_angle_deg(0.0, horizon_range)) == pytest.approx(
        math.degrees(math.asin(EARTH_RADIUS_M / r)), abs=1e-6
    )


def test_table_interpolation() -> None:
    assert float(lb.interpolate_gain_dbi([0.0, 10.0, 20.0], [10.0, 8.0, 2.0], 15.0)) == 5.0
    assert float(lb.interpolate_gain_dbi([0.0, 10.0], [10.0, 8.0], 50.0)) == 8.0  # clamped
    assert float(lb.interpolate_attenuation_db([5.0, 20.0], [3.0, 1.0], 12.5)) == pytest.approx(2.0)


# ---- 10-14: static table --------------------------------------------------------------------


def test_static_table_of_the_test_link() -> None:
    result = link_static_budget(link_project())
    row = result.rows[0]
    assert (row.point, row.elevation_deg, row.range_m) == ("slant", 10.0, 1.0e6)
    assert row.eirp_dbw == pytest.approx(8.0103, abs=1e-4)
    assert row.path_loss_db == pytest.approx(FSPL_1000KM, abs=0.005)
    assert row.other_losses_db == pytest.approx(2.0)
    assert row.g_over_t_dbk == pytest.approx(-7.4897)
    assert row.cn0_dbhz == pytest.approx(CN0, abs=0.01)
    margins = {r.data_rate_bps: r.margin_db for r in row.rates}
    assert margins[10e3] == pytest.approx(CN0 - 40.0 - 10.0, abs=0.01)
    assert margins[100e3] == pytest.approx(8.65, abs=0.01)
    assert margins[1e6] == pytest.approx(-1.35, abs=0.01)
    assert [r.closes for r in row.rates] == [True, True, False]
    assert row.max_rate_bps == 100e3
    assert row.max_rate_continuous_bps == pytest.approx(3.672e5, rel=3e-3)


def test_attenuation_entries_are_interpolated_by_elevation_and_added() -> None:
    # rain at 12.5 deg: 3 dB at 5 deg to 1 dB at 20 deg -> 2.0; gas has no elevation: 0.4 dB
    link = downlink(attenuation=["rain", "gas"])
    link = link.model_copy(
        update={"static_points": [link.static_points[0].model_copy(update={"elevation_deg": 12.5})]}
    )
    row = link_static_budget(link_project(links={"dl": link})).rows[0]
    assert row.atmospheric_loss_db == pytest.approx(2.4)
    assert row.cn0_dbhz == pytest.approx(CN0 - 2.4, abs=0.01)


def test_spacecraft_antenna_pattern_is_used_by_nadir_angle() -> None:
    # Downlink with a pattern on the spacecraft: gain 6 dBi on boresight, 0 dBi at 60 degrees.
    # At 30 deg elevation and 1000 km the nadir angle follows from the triangle (law of cosines).
    pattern = AntennaPattern(source="test fixture", angles_deg=[0.0, 60.0], gains_dbi=[6.0, 0.0])
    tx = downlink().transmitter.model_copy(update={"antenna": Antenna(pattern=pattern)})
    link = downlink(transmitter=tx)
    link = link.model_copy(
        update={"static_points": [link.static_points[0].model_copy(update={"elevation_deg": 30.0})]}
    )
    d, el = 1.0e6, math.radians(30.0)
    r = math.sqrt(EARTH_RADIUS_M**2 + d * d + 2.0 * EARTH_RADIUS_M * d * math.sin(el))
    eta = math.degrees(math.asin(EARTH_RADIUS_M * math.cos(el) / r))
    gain = 6.0 - 6.0 * eta / 60.0
    row = link_static_budget(link_project(links={"dl": link})).rows[0]
    assert row.eirp_dbw == pytest.approx(10.0 * math.log10(2.0) - 1.0 + gain, abs=1e-6)


def test_uplink_uses_the_spacecraft_receive_pattern_and_noise_temperature() -> None:
    pattern = AntennaPattern(source="test fixture", angles_deg=[0.0, 90.0], gains_dbi=[3.0, -9.0])
    link = downlink(
        direction="uplink",
        transmitter=downlink().transmitter,  # ground transmitter: constant gain
        receiver=Receiver(
            antenna=Antenna(pattern=pattern),
            system_noise_temperature_k=sv(400.0),
            feed_loss_db=sv(0.5),
        ),
    )
    link = link.model_copy(
        update={"static_points": [link.static_points[0].model_copy(update={"elevation_deg": 30.0})]}
    )
    d, el = 1.0e6, math.radians(30.0)
    r = math.sqrt(EARTH_RADIUS_M**2 + d * d + 2.0 * EARTH_RADIUS_M * d * math.sin(el))
    eta = math.degrees(math.asin(EARTH_RADIUS_M * math.cos(el) / r))
    gain = 3.0 - 12.0 * eta / 90.0
    row = link_static_budget(link_project(links={"ul": link})).rows[0]
    assert row.g_over_t_dbk == pytest.approx(gain - 0.5 - 10.0 * math.log10(400.0), abs=1e-6)


def test_placeholder_and_missing_inputs_give_na() -> None:
    # required Eb/N0 is a placeholder
    result = link_static_budget(link_project(ebn0=None))
    row = result.rows[0]
    assert row.cn0_dbhz is None and row.rates == () and row.max_rate_bps is None
    assert any(
        p.code == "RESULT_INCOMPLETE" and p.path == "entries[0].required_ebn0_db"
        for p in result.problems
    )
    # a modulation that has no entry
    result = link_static_budget(link_project(links={"dl": downlink(modulation="OTHER")}))
    assert result.rows[0].cn0_dbhz is None
    assert any(p.file == "config/ebn0_table.yaml" for p in result.problems)
    # a placeholder transmit power
    tx = downlink().transmitter.model_copy(update={"power_w": sv(None)})
    result = link_static_budget(link_project(links={"dl": downlink(transmitter=tx)}))
    assert result.rows[0].eirp_dbw is None
    assert any(p.path == "transmitter.power_w" for p in result.problems)


def test_attenuation_for_another_frequency_warns() -> None:
    project = link_project(links={"dl": downlink(attenuation=["gas"], frequency_hz=3.0e9)})
    result = link_static_budget(project)
    assert any(p.code == "LINK_ATTENUATION_FREQUENCY" for p in result.problems)


# ---- 15-19: pass time series and data volume ------------------------------------------------


def test_pass_series_selects_the_rate_and_integrates_the_volume() -> None:
    result = link_pass_series(link_project(), pass_run())
    s = result.series[0]
    assert s.site == "gs" and len(s.passes) == 1
    # 30 samples of 10 s: C/N0 is the same as in the static case, 100 kbit/s closes, 1 Mbit/s not
    assert len(s.times_s) == 30
    assert set(s.selected_rate_bps) == {100e3}  # type: ignore[arg-type]
    assert s.volume_bits == pytest.approx(100e3 * 300.0)
    assert s.volume_per_day_bits == pytest.approx(100e3 * 300.0 * 86.4)
    assert s.passes[0].usable_s == pytest.approx(300.0)
    assert s.margin_db is not None and s.margin_db.shape == (30, 3)
    assert s.passes[0].minimum_margin_db == pytest.approx(CN0 - 40.0 - 10.0, abs=0.01)


def test_samples_are_weighted_by_the_part_of_the_step_inside_the_pass() -> None:
    # pass from 105 s to 395 s on a 10 s grid: 5 s + 28 * 10 s + 5 s = 290 s
    result = link_pass_series(link_project(), pass_run(aos_s=105.0, los_s=395.0))
    assert result.series[0].volume_bits == pytest.approx(100e3 * 290.0)


def test_a_longer_range_lowers_the_rate() -> None:
    # at 3000 km the path loss is 9.54 dB more: Eb/N0 at 100 kbit/s falls to 9.1 dB, below
    # the required 10 + 3 dB; 10 kbit/s still closes
    result = link_pass_series(link_project(), pass_run(range_m=3.0e6))
    s = result.series[0]
    assert set(s.selected_rate_bps) == {10e3}  # type: ignore[arg-type]
    assert s.volume_bits == pytest.approx(10e3 * 300.0)


def test_active_modes_restrict_the_volume_to_the_modes_in_which_the_link_runs() -> None:
    rules = [ScenarioRule(kind="during_pass", site="gs", mode="b")]
    both = {"a": downlink(active_modes=["a"]), "b": downlink(active_modes=["b"])}
    for lid, expected in (("a", 0.0), ("b", 100e3 * 300.0)):
        project = link_project(links={lid: both[lid]})
        s = link_pass_series(project, pass_run(rules=rules)).series[0]
        assert s.volume_bits == pytest.approx(expected)


def test_the_tracking_limit_switches_the_link_off_above_it() -> None:
    link = downlink(max_elevation_deg=25.0)  # the pass is at 30 degrees
    s = link_pass_series(link_project(links={"dl": link}), pass_run()).series[0]
    assert s.volume_bits == 0.0 and not s.active.any()


def test_a_peer_that_is_not_a_scenario_site_is_reported() -> None:
    run = pass_run()
    env = run.env
    object.__setattr__(env, "sites", {})
    result = link_pass_series(link_project(), run)
    assert result.series == ()
    assert any(p.code == "LINK_SITE_NOT_IN_SCENARIO" for p in result.problems)


def test_a_link_without_a_peer_has_no_series() -> None:
    result = link_pass_series(link_project(links={"dl": downlink(peer=None)}), pass_run())
    assert result.series == ()


def test_pattern_file_is_read_from_the_project_folder(tmp_path: Path) -> None:
    (tmp_path / "pattern.csv").write_text("angle_deg,gain_dbi\n0,6\n60,0\n", encoding="utf-8")
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="pattern.csv", pattern_source="test fixture")}
    )
    project = link_project(root=tmp_path, links={"dl": downlink(transmitter=tx)})
    row = link_static_budget(project).rows[0]
    assert row.eirp_dbw is not None and row.eirp_dbw < 8.0103  # off boresight loses gain


def test_a_bad_pattern_file_is_a_plain_message_without_its_content(tmp_path: Path) -> None:
    (tmp_path / "pattern.csv").write_text("angle_deg,gain_dbi\nSECRET,6\n", encoding="utf-8")
    tx = downlink().transmitter.model_copy(
        update={"antenna": Antenna(pattern_file="pattern.csv", pattern_source="test fixture")}
    )
    result = link_static_budget(link_project(root=tmp_path, links={"dl": downlink(transmitter=tx)}))
    bad = [p for p in result.problems if p.code == "LINK_INPUT_INVALID"]
    assert bad and bad[0].file == "pattern.csv" and "SECRET" not in bad[0].message + bad[0].hint
    assert result.rows[0].cn0_dbhz is None


# ---- audit round N2: overlap weighting, n/a, closure finding ---------------------------------


def test_active_modes_are_weighted_by_the_overlap_with_the_mode_segment() -> None:
    # pass 105..395 s on a 10 s grid, mode b exactly during the pass: the 5 s at each end belong to
    # the samples at 100 s and 390 s, which start in mode a. The overlap is still 290 s.
    rules = [ScenarioRule(kind="during_pass", site="gs", mode="b")]
    project = link_project(links={"dl": downlink(active_modes=["b"])})
    s = link_pass_series(project, pass_run(aos_s=105.0, los_s=395.0, rules=rules)).series[0]
    assert s.volume_bits == pytest.approx(100e3 * 290.0)
    assert s.passes[0].usable_s == pytest.approx(290.0)


def test_usable_time_is_not_available_when_the_link_cannot_be_evaluated() -> None:
    result = link_pass_series(link_project(ebn0=None), pass_run())
    summary = result.series[0].passes[0]
    assert summary.usable_s is None and summary.volume_bits is None


def test_a_link_that_closes_at_no_rate_is_a_finding_in_the_pass_series() -> None:
    result = link_pass_series(link_project(), pass_run(range_m=1.0e9))
    found = [p for p in result.problems if p.code == "LINK_NOT_CLOSED"]
    assert len(found) == 1 and found[0].file == "links/dl.yaml"
    assert result.series[0].volume_bits == 0.0


def test_a_link_that_closes_is_not_reported() -> None:
    result = link_pass_series(link_project(), pass_run())
    assert not [p for p in result.problems if p.code == "LINK_NOT_CLOSED"]


def test_a_static_table_where_nothing_closes_is_a_finding() -> None:
    point = downlink().static_points[0].model_copy(update={"range_m": 1.0e9})
    link = downlink().model_copy(update={"static_points": [point]})
    result = link_static_budget(link_project(links={"dl": link}))
    assert [p.code for p in result.problems if p.code == "LINK_NOT_CLOSED"] == ["LINK_NOT_CLOSED"]
    assert not [
        p for p in link_static_budget(link_project()).problems if p.code == "LINK_NOT_CLOSED"
    ]
