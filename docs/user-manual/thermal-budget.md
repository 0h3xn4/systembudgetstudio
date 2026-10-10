# Thermal budget

This page shows how to get the heat each unit dissipates and the temperatures of a simple thermal model in a hot and a cold case, and how to check them against the units' temperature limits.

**Contents:** [Dissipation](#how-do-i-get-the-heat-dissipation) · [Temperatures](#how-do-i-get-node-temperatures-for-a-hot-and-a-cold-case) · [Limits](#how-do-i-check-unit-temperature-limits) · [Scope](#what-the-model-does-not-do)

## How do I get the heat dissipation?

Each power mode of a unit has a [`heat_dissipation_ratio`](../glossary.md#heat-dissipation): the share of the electrical power that ends up as heat inside the unit. Use `1.0` unless the unit sends power out of itself, for example a transmitter radiates part of its input as RF (`0.7` in the example radio's downlink mode). If the ratio is missing, thermal results that need it show *n/a*.

```bash
budget run my_satellite --budget thermal --out out
```

The report lists the dissipation by unit, subsystem, thermal node and spacecraft mode.

## How do I get node temperatures for a hot and a cold case?

You describe a small [**lumped network**](../glossary.md#node) in two files; every number in them has a source ([placeholders](placeholders-and-sources.md)).

`config/thermal_model.yaml`: nodes, linear conductances between nodes (W/K), and outer surfaces that radiate to space and absorb sunlight, albedo and Earth infrared:

```yaml
schema_version: 1
kind: thermal_model
nodes:
  EPS: {name: Power board}
  DH: {name: Data handling}
conductances:
  - {first_node: EPS, second_node: DH, conductance_wk: {value: 0.5, source: "…"}}
surfaces:
  - name: EPS panel
    node: EPS
    area_m2: 0.02
    emissivity_ratio: {value: 0.8, source: "…"}
    absorptivity_ratio: {value: 0.3, source: "…"}
    exposure:
      hot:  {solar_view_ratio: {value: 0.5, source: "…"}, earth_view_ratio: {value: 0.5, source: "…"}}
      cold: {solar_view_ratio: {value: 0.0, source: "…"}, earth_view_ratio: {value: 0.0, source: "…"}}
```

`config/thermal_environment.yaml`: the space temperature, the required temperature margin, and the **cases**:

```yaml
schema_version: 1
kind: thermal_environment
space_temperature_k: {value: 3.0, source: "…"}
temperature_margin_k: {value: 5.0, source: "…"}
cases:
  hot:
    spacecraft_mode: imaging       # whose dissipation is applied
    limit_set: operating           # or survival
    solar_flux_wm2: {value: 1000.0, source: "…"}
    albedo_ratio: {value: 0.3, source: "…"}
    earth_ir_wm2: {value: 230.0, source: "…"}
```

(The numbers above only show the shape of the file. Use your own, with their sources.)

Each unit sits in a thermal node: by default the node named like its `subsystem`, or the unit's `thermal_node`. The tool solves the heat balance of every node, `sum of conduction to the other nodes + radiation to space + absorbed heat + dissipation = 0`, for each case, and reports temperatures, heat absorbed, radiated and conducted.

## How do I check unit temperature limits?

Give a unit limits (any of them may be left out; a limit that is not given is not checked):

```yaml
temperature_limits:
  operating_min_k: 233.15
  operating_max_k: 343.15
  survival_min_k: 223.15
  survival_max_k: 353.15
```

Each case picks the `operating` or `survival` set. Every unit gets a status:

| Status | Meaning |
|---|---|
| `ok` | inside the limits, by at least the required margin |
| `ok (margin not checked)` | inside the limits, but the required margin is a placeholder, so the margin was not checked |
| `margin` | inside the limits but closer than the required margin (`THERMAL_MARGIN_INSUFFICIENT`) |
| `exceeded` | outside the limits (`THERMAL_LIMIT_EXCEEDED`) |
| `no limits` | the unit gives none for this set (`THERMAL_NO_LIMITS`, a warning) |
| `n/a` | the temperature could not be computed (a placeholder upstream) |

If a group of nodes has no path to space (no radiating surface), there is no equilibrium and you get `THERMAL_SOLVE_FAILED` naming the nodes: give every connected group a surface. A network whose conductances are many orders of magnitude above its radiation cannot be solved accurately in double precision; the tool says so instead of returning a wrong temperature. In the window use the **Thermal budget** tab.

## What the model does not do

[Steady state only](../glossary.md#steady-state). No transient (time-domain) analysis, no finite elements, no ray-traced view factors: you give the view ratios. The tool ships templates with placeholder numbers; every flux, optical property, conductance and limit is yours to supply. [`docs/THERMAL_SOURCES.md`](../THERMAL_SOURCES.md) lists *candidate* reference sources for a thermal engineer to check; nothing from them is entered for you.

Next: [Link budget](link-budget.md).
