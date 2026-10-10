# Environment inputs and the interim SpaceMissionStudio format

This page describes the files that define a scenario's orbit, ground stations and timeline, and the interim CSV format for importing orbit data from SpaceMissionStudio.

## Scenario files (`scenarios/<id>.yaml`, kind `scenario`)

```
name, description
environment_source: elements | spacemissionstudio
orbit: <orbit id>                 # for elements
import_dir: imports/run1          # for spacemissionstudio, relative to the project folder
start_utc: '2026-06-01T00:00:00Z' # UTC only
duration_s, step_s                # grid of the results; step_s <= duration_s
shadow_model: cylindrical | conical
sites: [<ground station or target ids>]
default_mode: <spacecraft mode id>
rules:                            # applied in order, later rules win
  - {kind: during_pass, site: <id>, mode: <mode id>, lead_s: 0, lag_s: 0}
  - {kind: in_eclipse, mode: <mode id>}
  - {kind: in_sunlight, mode: <mode id>}
segments:                         # hand-built, applied last, must not overlap
  - {start_s: 0, duration_s: 1800, mode: <mode id>}
```

Timeline layering (D-056): default mode over the whole scenario, then each rule in order, then the manual segments. Segments are half-open [start, end). Results (eclipses, passes, timeline) are computed, never stored in the project.

## Orbits, ground stations, targets

- `orbits/<id>.yaml` (kind `orbit`): either `tle: [line1, line2]` (69-character lines, checksums verified) or `elements:` with `epoch_utc`, `semi_major_axis_m`, `eccentricity_ratio`, `inclination_deg`, `raan_deg`, `arg_perigee_deg`, `mean_anomaly_deg`. Elements are used as SGP4 mean elements without drag (DEVIATIONS DV-E2).
- `ground_stations/<id>.yaml` and `targets/<id>.yaml`: `name`, `latitude_deg`, `longitude_deg`, `altitude_m`, `min_elevation_deg` (required, no default). A target is a ground point imaged when the satellite is above its minimum elevation. Ids are unique across both folders.

## Conventions

Inertial positions are SGP4 TEME in metres; time in seconds from the scenario start; the Sun uses the Astronomical Almanac low-precision formulae; Earth rotation uses GMST only (DEVIATIONS DV-E1). Passes and eclipse edges are refined by bisection to about 1 ms, so they do not depend on `step_s`.

## Interim SpaceMissionStudio format (decision D-055)

No real export was available, so the importer reads these CSV files from `import_dir`. **Replace this format when sample files arrive.** `export_spacemissionstudio` writes the same files from any environment (used for tests).

| File | Columns | Notes |
|---|---|---|
| `orbit.csv` | `time_utc,x_m,y_m,z_m,vx_mps,vy_mps,vz_mps` | inertial frame used as given; must cover the scenario from start to start + duration; cubic Hermite interpolation |
| `eclipse.csv` | `start_utc,end_utc` | shadow intervals; no penumbra information |
| `passes_<site id>.csv` | `aos_utc,los_utc,max_elevation_deg` | one file per site of the scenario |
| `profile_<site id>.csv` | `time_utc,elevation_deg,azimuth_deg,range_m` | optional; samples inside passes; without it the profile arrays are NaN and a note is printed |

Times are UTC (`2026-06-01T00:00:00Z`, fractional seconds allowed). Errors name the file and line and never echo content (`ENV_INPUT_INVALID`).

## Commands

```
budget scenario PROJECT [--scenario ID] [--out DIR]
```
writes `<id>_environment.json`, `<id>_eclipses.csv`, `<id>_passes.csv`, `<id>_timeline.csv` and `<id>_provenance.csv`.

Next: [Scenarios (user manual)](user-manual/scenarios.md) · [Project file format](FILE_FORMAT.md) · [Docs index](README.md).
