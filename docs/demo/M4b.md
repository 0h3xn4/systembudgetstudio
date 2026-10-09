# M4b Thermal budget — demo note

```
budget export-examples demo
budget run demo/cubesat_3u_eps --budget thermal --out out
system-budget-studio demo/cubesat_3u_eps        # tab "Thermal budget"
```

`cubesat_3u_eps` has complete **invented** thermal values (their source text says so): one node per subsystem in a chain, one radiating panel per node, a hot case (sunlight, imaging mode) and a cold case (eclipse, safe mode), unit limits and a 5 K margin. The other examples carry a thermal template whose numbers are `TBD`; their cases show "not computed (inputs missing)" and the INCOMPLETE banner, never a zero.

What you see for the complete example: node temperatures per case (cold about -28 C, hot about 60 C), the heat absorbed from the environment, radiated to space and conducted between nodes, a check of each unit against its operating limits, and one finding built to show the feature: **the radio is closer than the required 5 K margin to its upper limit in the hot case** (`THERMAL_MARGIN_INSUFFICIENT`, exit code 1, jump link to `units/radio.yaml`). Dissipation tables by unit, subsystem, thermal node and spacecraft mode are in the reports (XLSX, PDF, DOCX, JSON) and in the window; CSV files hold dissipation per mode and node temperatures per case.

Inputs: `heat_dissipation_ratio` per power mode (1.0 unless the unit radiates RF; never assumed, missing means n/a), `thermal_node` and `temperature_limits` per unit, `config/thermal_model.yaml`, `config/thermal_environment.yaml` (format in `docs/FILE_FORMAT.md`). Unit schema is now version 2; version 1 units migrate unchanged. Candidate reference sources for a thermal engineer to verify: `docs/THERMAL_SOURCES.md` (no value from them is entered).

Verified against hand calculations (21 cases): a single node radiating to space (300 K), radiator sizing, no heat gives the space temperature, two nodes in series (T2 = T1 + Q/G), symmetric nodes, a three-node chain with energy conservation, nodes without a path to space, dissipation ratios, the absorbed-heat terms, the two-node project (283.01 K and 286.01 K in the hot case), limit status ok/margin/exceeded, survival limits, and n/a for missing ratios, fluxes and conductances. Hypothesis properties: energy is conserved and the balance closes, more dissipation never lowers a temperature, more radiator area never raises one, better conduction never widens the spread.

Open for the owner: every thermal number (fluxes, optical properties, conductances, margins, unit limits, case definitions) and the node mapping convention (default: node named like the subsystem); confirm D-072 together with D-054; equations `TH-*` are `SOURCE_MISSING`. Still open from earlier: the M4 items (attitude convention, demand basis, `TDP-*` equations, real array and battery numbers), SpaceMissionStudio samples, D-043, D-048, D-054, D-059, the repository being public, and branch protection. Next is M5 (link budget).
