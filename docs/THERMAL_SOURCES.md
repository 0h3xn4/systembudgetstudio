# Thermal inputs: candidate reference sources (to be verified)

System Budget Studio enters **no** thermal value itself (decision D-039, D-073). The numbers below are inputs you supply in `config/thermal_environment.yaml`, `config/thermal_model.yaml` and the unit files, each with a `source`. This page lists documents that a thermal engineer may want to check for them. **The tool has not read these texts and does not vouch for them**: confirm the exact title, edition and clause before citing one in a `source` field, and change this list if your project uses other references.

| Input | Where it goes | Candidate references to check |
|---|---|---|
| Solar flux, albedo and Earth infrared values for hot and cold cases | `cases.<name>.solar_flux_wm2`, `albedo_ratio`, `earth_ir_wm2` | ECSS-E-ST-10-04C Space environment; ECSS-E-ST-31C Thermal control general requirements; the thermal chapter of a spacecraft systems engineering handbook |
| Definition of the hot and cold cases (which orbit conditions, which modes) | the case names, `spacecraft_mode`, `limit_set`; view ratios in `surfaces[].exposure` | ECSS-E-ST-31C; ECSS-E-HB-31-01A Thermal design handbook; the project's own thermal design specification |
| Emissivity and absorptivity of coatings, paints, MLI | `surfaces[].emissivity_ratio`, `absorptivity_ratio` | Coating or material data sheets (beginning and end of life values); the thermal design handbook; Gilmore (ed.), Spacecraft Thermal Control Handbook, Volume I, Aerospace Press |
| Conductances between nodes (interfaces, structure, harness) | `conductances[].conductance_wk` | Interface test or analysis data; the thermal design handbook; Gilmore, Spacecraft Thermal Control Handbook |
| Space (sink) temperature | `space_temperature_k` | ECSS-E-ST-10-04C and the project thermal specification |
| Required temperature margin to unit limits | `temperature_margin_k` | ECSS-E-ST-31C and the project's thermal margin policy |
| Unit operating and survival limits | `temperature_limits` in the unit file | The unit data sheet or interface control document |
| Heat dissipation ratio of transmitters and other exporting units | `modes[].heat_dissipation_ratio` | The unit data sheet (RF output power, efficiency) |

The Stefan-Boltzmann constant is the one thermal number the tool carries (definition from the 2019 SI constants, decision D-072).

Next: [Thermal budget (user manual)](user-manual/thermal-budget.md) · [Placeholders and sources](user-manual/placeholders-and-sources.md) · [Docs index](README.md).
