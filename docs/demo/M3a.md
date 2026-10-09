# M3a Environment — demo note

```
budget export-examples demo
budget scenario demo/cubesat_3u --out out --user "Your Name"
```

Prints how many eclipses and passes the day has and writes `one_day_environment.json`, `one_day_eclipses.csv`, `one_day_passes.csv` and `one_day_timeline.csv`. In the 3U example the mode timeline shows the layering: `charging` by default, `nominal` during eclipse, `imaging` over the target and `downlink` over the station (later rules win; manual segments win last).

How it is checked:
- **Eclipse duration** against the closed-form circular-orbit formula, 16 hand-calculated orbit geometries; the beta angle from the propagated state is compared with `asin(sin i sin RAAN)`.
- **Pass duration** against the analytic equatorial-orbit formula for 10 altitude and minimum-elevation combinations; pass edges sit on the minimum elevation; results do not depend on the grid step.
- The Sun is checked against the published 2000 equinox and solstice instants, sidereal time against the sgp4 library, shadow geometry against umbra, penumbra and annular cases.
- Timeline: Hypothesis property that the timeline always covers the scenario without gaps or overlaps (it found a sliver-gap bug at an interval starting a hair after 0, now fixed).
- SpaceMissionStudio import (interim format) round-trips against the propagator.
- A week at 1 s with three sites and the conical shadow takes about 4 s.

Open for the owner: SpaceMissionStudio sample files (the import format is interim); confirm D-054 (definitional constants and low-precision Sun shipped with sources, not as TBD); the GUI timeline editor is M3b.
