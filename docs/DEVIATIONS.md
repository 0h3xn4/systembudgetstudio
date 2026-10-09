# Deviations (physics simplifications)

Each entry: what is simplified, why, expected error, and the milestone that may remove it.

_None yet. Planned (to be confirmed when implemented):_

- **DV-P1 (M3):** conical/cylindrical shadow model only; no Earth oblateness or atmospheric refraction in eclipse timing.
- **DV-P2 (M4):** array temperature treated as a configured constant per mode/phase, not a thermal model (thermal is out of scope for v1).
- **DV-P3 (M5):** rain and gas attenuation come only from user-supplied tables; no built-in ITU-R P.618 implementation until a source is approved.
- **DV-M1 (M2b):** margin mass is not given a position, so the centre of gravity and inertia use nominal (unmargined) masses; the margin appears only in the mass totals. Inertia margins are not applied.
- **DV-M2 (M2b):** units are rigid bodies described by a mass, a position and an inertia tensor; flexible appendages, deployed configurations and moving parts (reaction wheel angular momentum) are not modelled; deployed and stowed states are handled only as separate phases.

