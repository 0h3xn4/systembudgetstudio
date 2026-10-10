# Thermal budget

## Heat dissipation

For each power mode `heat_dissipation_ratio` states which share of the electrical power ends up as heat in the unit. Use 1.0 unless the unit radiates RF or exports power. The budget lists the dissipation by unit, subsystem, thermal node and spacecraft mode.

## Steady-state node model

`config/thermal_model.yaml` describes a small lumped network: thermal nodes, linear conductances between nodes, and outer surfaces with area, emissivity and absorptivity that radiate to space and absorb solar, albedo and Earth infrared flux. `config/thermal_environment.yaml` defines the cases (for example hot and cold): the spacecraft mode whose dissipation is applied, the limit set, and the fluxes.

The tool solves the equilibrium temperatures of all nodes and compares each unit with its limits: **ok**, **margin** (inside the limits but within the required margin), **exceeded**, or **no limits** when the unit gives none.

## Scope

The model is steady state only. Transient thermal analysis, finite elements and ray-traced view factors are out of scope for version 1. The tool ships *templates* with placeholder numbers; every flux, optical property, conductance and limit comes from you, with its source.
