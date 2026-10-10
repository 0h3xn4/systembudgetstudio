# Scenarios

This page shows how to place the spacecraft in an orbit for a span of time and decide which spacecraft mode is active when; the time-domain power budget and the link passes need a scenario.

**Contents:** [Orbit](#how-do-i-define-an-orbit) · [Ground stations and targets](#how-do-i-add-a-ground-station-or-an-imaging-target) · [The scenario file](#how-do-i-write-a-scenario) · [Mode rules](#how-do-i-switch-modes-automatically) · [Compute and look](#how-do-i-see-eclipses-passes-and-the-timeline) · [SpaceMissionStudio](#how-do-i-use-orbit-data-from-spacemissionstudio)

## How do I define an orbit?

`orbits/<id>.yaml` takes either a two-line element set (a [**TLE**](../glossary.md#tle): two 69-character lines, checksums verified) or mean orbital elements:

```yaml
schema_version: 1
kind: orbit
name: Example sun-synchronous-like orbit, about 550 km
elements:
  epoch_utc: '2026-06-01T00:00:00Z'
  semi_major_axis_m: 6928137.0
  eccentricity_ratio: 0.001
  inclination_deg: 97.6
  raan_deg: 100.0
  arg_perigee_deg: 90.0
  mean_anomaly_deg: 0.0
```

Positions come from the [SGP4](../glossary.md#sgp4) propagator (Earth only; elements are used as SGP4 mean elements, without drag: see [deviation DV-E2](../DEVIATIONS.md)). The guided wizard writes a near-circular orbit for you from altitude, inclination and [RAAN](../glossary.md#raan).

## How do I add a ground station or an imaging target?

```yaml
# ground_stations/gs_north.yaml     (an imaging target is the same, in targets/)
schema_version: 1
kind: ground_station
name: Example station north
latitude_deg: 67.0
longitude_deg: 20.0
altitude_m: 100.0
min_elevation_deg: 5.0
```

A [**pass**](../glossary.md#pass) is a time during which the satellite is above `min_elevation_deg`. Ids are unique across stations and targets.

## How do I write a scenario?

`scenarios/<id>.yaml`:

```yaml
schema_version: 2
kind: scenario
name: One day
environment_source: elements      # or spacemissionstudio
orbit: leo
start_utc: '2026-06-01T00:00:00Z' # UTC only
duration_s: 86400.0
step_s: 10.0                      # the time grid of the results
shadow_model: cylindrical         # or conical
sites: [gs_north, tgt_plains]     # stations and targets to compute passes for
mission_phase: eol                # selects the allowed depth of discharge
default_mode: charging
rules: []
segments: []
```

A scenario may have up to 1,000,000 steps (a week at 1 s is 604,801). [`shadow_model`](../glossary.md#shadow-model) is the Earth shadow: `cylindrical` (sharp edge) or `conical` (umbra and penumbra).

## How do I switch modes automatically?

`default_mode` is active unless a **rule** or a **segment** says otherwise. Rules are applied in order, later rules win, then the hand-placed segments:

```yaml
rules:
  - {kind: in_eclipse, mode: nominal}
  - {kind: during_pass, site: tgt_plains, mode: imaging, lead_s: 30}
  - {kind: during_pass, site: gs_north, mode: downlink}
  - {kind: in_sunlight, mode: charging}
segments:                         # hand-built, applied last, must not overlap
  - {start_s: 0, duration_s: 1800, mode: safe}
```

`lead_s` and `lag_s` start the mode earlier or end it later around a pass. In the window the **Scenario** tab shows the timeline and lets you edit rules and segments; invalid edits are explained and nothing is written until you save.

## How do I see eclipses, passes and the timeline?

```bash
budget scenario my_satellite --out out
```

```text
Scenario one_day (elements): 15 eclipse(s); passes: gs_north 11, tgt_plains 1; 54 timeline segment(s).
```

It writes `<id>_environment.json`, `<id>_eclipses.csv`, `<id>_passes.csv`, `<id>_timeline.csv` and a provenance file. Pass and eclipse edges are refined to about 1 ms, so they do not depend on `step_s`. The window's **Scenario** tab shows the same tables after **Compute**; to write the files use this command (the window has no menu entry for it).

## How do I use orbit data from SpaceMissionStudio?

Set `environment_source: spacemissionstudio` and `import_dir:` (a folder inside the project) in the scenario. The folder holds CSV files with the orbit, eclipse intervals and passes. The format is an **interim** one, because no real export was available yet: [Environment inputs and the interim format](../ENVIRONMENT_FORMAT.md). Errors name the file and line and never echo content (`ENV_INPUT_INVALID`).

Next: [Reports and exports](reports-and-exports.md).
