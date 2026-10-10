# Scenarios and environment

A scenario places the spacecraft in an orbit for a time span and decides which spacecraft mode is active when.

## Orbit and sites

An orbit is given as a two-line element set (TLE) or as mean orbital elements. Ground stations and imaging targets have a latitude, longitude, altitude and minimum elevation. The tool computes eclipses (cylindrical or conical shadow) and the passes over every site listed in the scenario.

## Mode timeline

`default_mode` is active unless a rule or a segment says otherwise. Rules switch modes automatically (`in_eclipse`, `during_pass` of a site, with a lead and lag time); segments set a mode for a fixed interval. The **Scenario** tab shows the resulting timeline and lets you edit rules and segments.

## Time grid

`start_utc`, `duration_s` and `step_s` define the grid on which the time-domain budgets are evaluated. Eclipses and mode segments are overlapped exactly with each step, not sampled. A week at 1 s resolution with 200 units is computed in about 10 seconds.

## Imported environments

Instead of the built-in propagator a scenario can read orbit, eclipse and pass files exported by SpaceMissionStudio (`environment_source: spacemissionstudio`). The format is described in `docs/ENVIRONMENT_FORMAT.md`.
