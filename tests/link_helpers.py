"""A project with one downlink and one uplink, and a synthetic pass (source: test fixture).

Round numbers so that every expected value can be worked out by hand:

* downlink at 2 GHz: 2 W transmitter (3.0103 dBW), 1 dB line loss, 6 dBi spacecraft antenna;
  ground G/T given as 20 dBi - 0.5 dB feed loss - 10 log10(500 K) = -7.4897 dB/K
* losses: pointing 1 dB, polarisation 0.5 dB, implementation 0.5 dB (2 dB in total)
* required Eb/N0 10 dB (modulation TEST, coding NONE), required margin 3 dB
* data rates 10 kbit/s, 100 kbit/s, 1 Mbit/s
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from budget_core.environment.data import EnvironmentData, Pass, SiteDef, SiteVisibility
from budget_core.model import (
    Antenna,
    AttenuationEntry,
    AttenuationTable,
    Ebn0Entry,
    Ebn0Table,
    GroundStation,
    Link,
    Receiver,
    ScenarioRule,
    StaticPoint,
    Transmitter,
)
from budget_core.scenario.run import ScenarioRun
from tests.power_helpers import START, sv, synthetic_env, synthetic_run, td_project


def downlink(**changes: object) -> Link:
    link = Link(
        name="Test downlink",
        direction="downlink",
        peer="gs",
        frequency_hz=2.0e9,
        transmitter=Transmitter(
            power_w=sv(2.0), line_loss_db=sv(1.0), antenna=Antenna(gain_dbi=sv(6.0))
        ),
        receiver=Receiver(g_over_t_dbk=sv(-7.4897)),
        modulation="TEST",
        coding="NONE",
        data_rates_bps=[10e3, 100e3, 1e6],
        required_margin_db=sv(3.0),
        pointing_loss_db=sv(1.0),
        polarisation_loss_db=sv(0.5),
        implementation_loss_db=sv(0.5),
        static_points=[StaticPoint(name="slant", elevation_deg=10.0, range_m=1.0e6)],
    )
    return link.model_copy(update=changes)


def link_project(
    root: Path = Path("."), links: dict[str, Link] | None = None, ebn0: float | None = 10.0
):  # type: ignore[no-untyped-def]
    base = td_project(root)
    config = replace(
        base.config,
        ebn0_table=Ebn0Table(
            entries=[Ebn0Entry(modulation="TEST", coding="NONE", required_ebn0_db=sv(ebn0))]
        ),
        attenuation_table=AttenuationTable(
            entries=[
                AttenuationEntry(
                    name="rain",
                    attenuation_kind="rain",
                    freq_hz=2.0e9,
                    elevation_deg=5.0,
                    loss_db=sv(3.0),
                ),
                AttenuationEntry(
                    name="rain",
                    attenuation_kind="rain",
                    freq_hz=2.0e9,
                    elevation_deg=20.0,
                    loss_db=sv(1.0),
                ),
                AttenuationEntry(
                    name="gas", attenuation_kind="gas", freq_hz=2.0e9, loss_db=sv(0.4)
                ),
            ]
        ),
    )
    return replace(
        base,
        config=config,
        ground_stations={
            "gs": GroundStation(
                name="Station",
                latitude_deg=60.0,
                longitude_deg=10.0,
                altitude_m=100.0,
                min_elevation_deg=5.0,
            )
        },
        links=links if links is not None else {"dl": downlink()},
    )


def pass_run(
    *,
    aos_s: float = 100.0,
    los_s: float = 400.0,
    duration_s: float = 1000.0,
    step_s: float = 10.0,
    elevation_deg: float = 30.0,
    range_m: float = 1.0e6,
    rules: list[ScenarioRule] | None = None,
    default_mode: str = "a",
) -> ScenarioRun:
    """One pass of the station 'gs' with constant elevation and range."""
    env = synthetic_env(duration_s, step_s)
    n = len(env.grid.times_s)
    site = SiteDef("gs", "ground_station", 60.0, 10.0, 100.0, 5.0)
    vis = SiteVisibility(
        site=site,
        passes=(Pass(aos_s, los_s, elevation_deg, (aos_s + los_s) / 2.0),),
        elevation_deg=np.full(n, elevation_deg),
        azimuth_deg=np.zeros(n),
        range_m=np.full(n, range_m),
    )
    env = EnvironmentData(
        grid=env.grid,
        source=env.source,
        shadow_model=env.shadow_model,
        position_m=env.position_m,
        sun_direction=env.sun_direction,
        sunlight_ratio=env.sunlight_ratio,
        eclipses=env.eclipses,
        umbras=env.umbras,
        sites={"gs": vis},
    )
    run = synthetic_run(env, rules=rules, default_mode=default_mode)
    return ScenarioRun(run.scenario_id, run.scenario, env, run.timeline, run.notes)


__all__ = ["START", "downlink", "link_project", "pass_run"]
