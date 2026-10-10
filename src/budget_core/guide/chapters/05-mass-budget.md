# Mass budget

Units and expendables carry a mass and a maturity class. The tool applies the mass margin of the class, then the system mass margin, and checks the total against the mass limits.

## Phases

`mission_phases` in `spacecraft.yaml` lists the phases you choose (for example launch, BOL, EOL); none are assumed. A unit may list the phases it is present in. An expendable gives its mass for **every** phase, with `0.0` written explicitly where it is gone.

## Centre of gravity and inertia

Positions are the centres of mass of items in metres in one right-handed body frame described in words in `spacecraft.yaml`. An item can also give its inertia tensor about its own centre of mass (axes parallel to the body frame). Items without a position are excluded from the centre of gravity and reported with `MASS_PROPS_MISSING`; an item without inertia is treated as a point mass.

## Limits

`config/mass_limits.yaml` lists limits per phase. A total above its limit is reported as `MASS_LIMIT_EXCEEDED` with the margin still available.
