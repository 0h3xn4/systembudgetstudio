# Mass budget

This page shows how to get the spacecraft mass with margins, its [centre of gravity](../glossary.md#cg) and inertia in each mission phase, and how to check it against a limit.

**Contents:** [Run it](#how-do-i-get-the-mass-budget) · [Phases](#how-do-i-handle-mission-phases-and-propellant) · [Centre of gravity and inertia](#how-do-i-get-the-centre-of-gravity-and-inertia) · [Limits](#how-do-i-check-a-mass-limit)

## How do I get the mass budget?

```bash
budget run my_satellite --budget mass --out out
```

Every unit has `mass_kg` and a maturity class; every [expendable](#how-do-i-handle-mission-phases-and-propellant) has a mass. The tool applies the [**mass margin**](../glossary.md#margin-policy) of the class, then the **system mass margin**, and rolls the result up by subsystem and for the whole spacecraft. In the window it is the **Mass budget** tab. The margins come from `config/margin_policy.yaml` (placeholders until you supply them: the totals with margin then show *n/a*).

## How do I handle mission phases and propellant?

List the phases in `spacecraft.yaml` (`mission_phases: [launch, bol, eol]`). A unit may list the `phases` it is present in (default: all phases), for example a deployable that is only there after launch. Consumables and jettisoned equipment go in `expendables/<id>.yaml` and give a mass for **every** phase, writing `0.0` where they are gone:

```yaml
schema_version: 1
kind: expendable
name: Propellant
subsystem: PROP
maturity: class_c
masses_kg:
  launch: 9.0
  bol: 8.5
  eol: 0.8
mass_properties:
  position_m: [0.0, 0.0, 0.35]
```

## How do I get the centre of gravity and inertia?

Give each unit (and expendable) a `mass_properties` block: the position of its centre of mass in the project's body frame (metres) and, if you know it, its [inertia tensor](../glossary.md#inertia) about its own centre of mass (axes parallel to the body frame):

```yaml
mass_properties:
  position_m: [0.0, 0.0, 0.12]
  inertia:
    ixx_kgm2: 6.4e-05
    iyy_kgm2: 6.4e-05
    izz_kgm2: 0.000121
    ixy_kgm2: 0.0
    ixz_kgm2: 0.0
    iyz_kgm2: 0.0
```

The tool computes the centre of gravity (mass-weighted mean of positions) and the inertia about it with the parallel-axis theorem, for each phase. Items without a position are left out and reported (`MASS_PROPS_MISSING`, with the share of mass covered); an item without inertia counts as a point mass. Centre of gravity and inertia use the **nominal** mass (margin mass has no position; see [deviation DV-M1](../DEVIATIONS.md)).

## How do I check a mass limit?

List limits in `config/mass_limits.yaml` (each with a `source`), optionally per phase:

```yaml
limits:
  - name: Launch mass
    phase: launch
    limit_kg:
      value: 4.0
      source: "Launch provider user manual, section 3.2"
```

A total above its limit is reported as `MASS_LIMIT_EXCEEDED`, naming the limit's position in the file, with the margin that remains.

Next: [Thermal budget](thermal-budget.md).
