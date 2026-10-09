# Deviations (physics simplifications)

Each entry: what is simplified, why, expected error, and the milestone that may remove it.

_None yet. Planned (to be confirmed when implemented):_

- **DV-P1 (M3):** conical/cylindrical shadow model only; no Earth oblateness or atmospheric refraction in eclipse timing.
- **DV-P2 (M4):** array temperature treated as a configured constant per mode/phase, not a thermal model (thermal is out of scope for v1).
- **DV-P3 (M5):** rain and gas attenuation come only from user-supplied tables; no built-in ITU-R P.618 implementation until a source is approved.
- **DV-M1 (M2b):** margin mass is not given a position, so the centre of gravity and inertia use nominal (unmargined) masses; the margin appears only in the mass totals. Inertia margins are not applied.
- **DV-M2 (M2b):** units are rigid bodies described by a mass, a position and an inertia tensor; flexible appendages, deployed configurations and moving parts (reaction wheel angular momentum) are not modelled; deployed and stowed states are handled only as separate phases.
- **DV-T1 (M4b):** lumped, steady-state thermal model: isothermal nodes, linear conductances, radiation to space with user-given radiator areas and optical properties; no radiative view factors between nodes, no orbital transient, no internal convection or fluid loops.
- **DV-T2 (M4b):** environment heat loads are user-supplied constants per case, not computed from orbit geometry (a later milestone may derive them from the M3 environment).
- **DV-M3 (M2b):** items are rigid bodies with a fixed centre of mass; fuel slosh, propellant centre-of-mass shift inside a tank and deployed versus stowed geometry are not modelled (use phases and an expendable position per phase if it matters). Inertia margins are not applied (DV-M1).
- **DV-E1 (M3):** Earth rotation uses GMST only (UTC treated as UT1, error up to 0.9 s, about 400 m on the ground; no polar motion, no nutation of the Earth-fixed frame); the Sun uses low-precision formulae (about 0.01 degree, eclipse edge timing error of a few seconds at most); no atmospheric refraction in elevation. All eclipse and pass times carry these limits.
- **DV-E2 (M3):** elements given by the user are used as SGP4 mean elements; the semi-major axis becomes mean motion by Kepler's third law (the SGP4 initialisation then applies its own mean-element conversion, a difference of order 0.1 percent in period); no drag (B* = 0); Earth orbits only.
- **DV-E3 (M3):** passes are visibility above a site's minimum elevation only; tracking-rate limits and antenna keep-out zones arrive with the link budget (M5).

