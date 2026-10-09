"""SpaceMissionStudio import (interim format, decision D-055): round trip against the propagator."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from budget_core.environment import geometry as geo
from budget_core.environment.data import Environment, EnvironmentData, SiteDef, TimeGrid
from budget_core.environment.elements import ElementsPropagator
from budget_core.environment.spacemissionstudio import (
    EnvironmentInputError,
    SpaceMissionStudioImport,
    export_spacemissionstudio,
)
from budget_core.model import Elements, Orbit

START = datetime(2026, 3, 20, 14, 46, tzinfo=UTC)
RE = geo.EARTH_RADIUS_M
SITE = SiteDef("gs", "ground_station", 55.0, 10.0, 100.0, 5.0)


def reference() -> tuple[EnvironmentData, TimeGrid]:
    orbit = Orbit(
        name="o",
        elements=Elements(
            epoch_utc="2026-03-20T14:46:00Z",
            semi_major_axis_m=RE + 550e3,
            eccentricity_ratio=0.001,
            inclination_deg=97.5,
            raan_deg=20.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
        ),
    )
    grid = TimeGrid(START, 86400.0, 10.0)
    return ElementsPropagator(orbit).compute(grid, [SITE], "cylindrical"), grid


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, EnvironmentData, TimeGrid]:
    env, grid = reference()
    folder = tmp_path_factory.mktemp("sms")
    export_spacemissionstudio(env, folder)
    return folder, env, grid


def test_both_adapters_satisfy_the_environment_interface(exported) -> None:  # type: ignore[no-untyped-def]
    folder, _, _ = exported
    adapters: list[Environment] = [SpaceMissionStudioImport(folder)]
    assert adapters[0].name == "spacemissionstudio"


def test_exported_files_have_the_documented_names(exported) -> None:  # type: ignore[no-untyped-def]
    folder, _, _ = exported
    assert sorted(p.name for p in folder.iterdir()) == [
        "eclipse.csv",
        "orbit.csv",
        "passes_gs.csv",
        "profile_gs.csv",
    ]
    header = (folder / "orbit.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "time_utc,x_m,y_m,z_m,vx_mps,vy_mps,vz_mps"
    assert (folder / "eclipse.csv").read_text(encoding="utf-8").startswith("start_utc,end_utc\n")


def test_round_trip_reproduces_eclipses_and_passes(exported) -> None:  # type: ignore[no-untyped-def]
    folder, env, grid = exported
    back = SpaceMissionStudioImport(folder).compute(grid, [SITE], "cylindrical")
    assert len(back.eclipses) == len(env.eclipses) >= 2
    for a, b in zip(env.eclipses, back.eclipses, strict=True):
        assert a.start_s == pytest.approx(b.start_s, abs=1e-3)
        assert a.end_s == pytest.approx(b.end_s, abs=1e-3)
    ours, theirs = env.sites["gs"].passes, back.sites["gs"].passes
    assert len(ours) == len(theirs) >= 2
    for a, b in zip(ours, theirs, strict=True):
        assert a.aos_s == pytest.approx(b.aos_s, abs=1e-3) and a.los_s == pytest.approx(
            b.los_s, abs=1e-3
        )
        assert a.max_elevation_deg == pytest.approx(b.max_elevation_deg, abs=1e-3)
    assert back.source == "spacemissionstudio"


def test_round_trip_positions_and_sunlight(exported) -> None:  # type: ignore[no-untyped-def]
    folder, env, grid = exported
    back = SpaceMissionStudioImport(folder).compute(grid, [SITE], "cylindrical")
    assert np.max(np.linalg.norm(back.position_m - env.position_m, axis=1)) < 50.0
    assert np.array_equal(back.sunlight_ratio, env.sunlight_ratio)
    assert np.max(np.linalg.norm(back.sun_direction - env.sun_direction, axis=1)) < 1e-6


def test_elevation_profile_is_restored_inside_passes_and_nan_outside(exported) -> None:  # type: ignore[no-untyped-def]
    folder, env, grid = exported
    back = SpaceMissionStudioImport(folder).compute(grid, [SITE], "cylindrical").sites["gs"]
    ref = env.sites["gs"]
    times = grid.times_s
    inside = np.zeros(len(times), dtype=bool)
    for p in ref.passes:
        inside |= (times >= p.aos_s) & (times <= p.los_s)
    assert np.max(np.abs(back.elevation_deg[inside] - ref.elevation_deg[inside])) < 0.01
    assert np.all(np.isnan(back.elevation_deg[~inside]))


def test_a_different_grid_step_on_import_works(exported) -> None:  # type: ignore[no-untyped-def]
    folder, env, grid = exported
    coarse = TimeGrid(grid.start, grid.duration_s, 60.0)
    back = SpaceMissionStudioImport(folder).compute(coarse, [SITE], "cylindrical")
    assert back.position_m.shape == (coarse.count, 3)
    ref = env.position_m[::6][: coarse.count]
    assert np.max(np.linalg.norm(back.position_m - ref, axis=1)) < 50.0


def test_missing_files_are_reported_with_the_file_name(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentInputError) as exc:
        SpaceMissionStudioImport(tmp_path).compute(TimeGrid(START, 100.0, 10.0), [], "cylindrical")
    assert exc.value.file == "orbit.csv"


def test_a_site_without_a_pass_file_is_reported(exported) -> None:  # type: ignore[no-untyped-def]
    folder, _, grid = exported
    other = SiteDef("elsewhere", "target", 0.0, 0.0, 0.0, 10.0)
    with pytest.raises(EnvironmentInputError) as exc:
        SpaceMissionStudioImport(folder).compute(grid, [other], "cylindrical")
    assert exc.value.file == "passes_elsewhere.csv"


def test_malformed_rows_name_file_and_line(exported, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    folder, _, grid = exported
    bad = tmp_path / "bad"
    bad.mkdir()
    for p in folder.iterdir():
        (bad / p.name).write_bytes(p.read_bytes())
    lines = (bad / "orbit.csv").read_text(encoding="utf-8").splitlines()
    lines[5] = "SECRETVALUE,1,2"
    (bad / "orbit.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(EnvironmentInputError) as exc:
        SpaceMissionStudioImport(bad).compute(grid, [SITE], "cylindrical")
    assert exc.value.file == "orbit.csv" and exc.value.line == 6
    assert "SECRETVALUE" not in str(exc.value)


def test_a_scenario_longer_than_the_files_is_reported(exported) -> None:  # type: ignore[no-untyped-def]
    folder, _, grid = exported
    long = TimeGrid(grid.start, grid.duration_s + 5000.0, 10.0)
    with pytest.raises(EnvironmentInputError) as exc:
        SpaceMissionStudioImport(folder).compute(long, [SITE], "cylindrical")
    assert exc.value.file == "orbit.csv" and "time range" in str(exc.value)


def test_the_export_is_deterministic(tmp_path: Path) -> None:
    env, _ = reference()
    export_spacemissionstudio(env, tmp_path / "a")
    export_spacemissionstudio(env, tmp_path / "b")
    for p in sorted((tmp_path / "a").iterdir()):
        assert p.read_bytes() == (tmp_path / "b" / p.name).read_bytes()
