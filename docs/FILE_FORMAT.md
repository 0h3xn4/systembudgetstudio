# Project file format

A project is a folder of YAML files (LF line endings). Every file starts with `schema_version` and `kind`. All kinds are at schema version 1 except `margin_policy` (version 2, see below).

```
project.yaml            kind: project            name, revision, description
spacecraft.yaml         kind: spacecraft         name, buses[{name, nominal_voltage_v}], mission_phases[], body_frame
units/<id>.yaml         kind: unit               name, subsystem, mass_kg, bus, maturity, modes[], mass_properties?, phases[]?
expendables/<id>.yaml   kind: expendable         name, subsystem, maturity, masses_kg{phase: kg}, mass_properties?
modes/<id>.yaml         kind: spacecraft_mode    name, description, assignments{unit id: power mode name}
config/margin_policy.yaml      kind: margin_policy (v2)  classes{name: {power_margin_ratio, mass_margin_ratio}}, system_power_margin_ratio, system_mass_margin_ratio
config/mass_limits.yaml        kind: mass_limits         limits[{name, phase?, limit_kg}]
config/power_config.yaml       kind: power_config        distribution_loss_ratio, converter_efficiency_ratio{bus}
config/ebn0_table.yaml         kind: ebn0_table          entries[{modulation, coding, required_ebn0_db}]
config/attenuation_table.yaml  kind: attenuation_table   entries[{name, attenuation_kind, freq_hz, elevation_deg, loss_db}]
```

Power mode: `name`, `avg_power_w`, `peak_power_w` (>= average), `duty_cycle_ratio` (0..1, default 1), optional `min_duration_s`, `max_duration_s`. Effective average power = `avg_power_w * duty_cycle_ratio` (D-024).

## Mass properties (decisions D-048 to D-050)

- One right-handed **body frame** per project, described in words in `spacecraft.yaml` (`body_frame`). Suggested: origin at the centre of the launch-vehicle interface plane, +Z along the launch axis away from the interface, X and Y in that plane. Positions are item centres of mass in metres: `mass_properties: {position_m: [x, y, z]}` (strings with units such as `"10 cm"` are accepted).
- Optional `inertia` inside `mass_properties`: `ixx_kgm2`, `iyy_kgm2`, `izz_kgm2`, `ixy_kgm2`, `ixz_kgm2`, `iyz_kgm2` about the item's own centre of mass, axes parallel to the body frame. The off-diagonal entries are **tensor elements** (minus the products of inertia). The tensor must belong to a rigid body (checked). An item without inertia is a point mass.
- `mission_phases`: ordered list of names you choose (none are assumed; without it there is one phase `all`). Units may list `phases` they are present in (default: all). Expendables give `masses_kg` for **every** phase (write `0.0` explicitly).
- Margins: item mass x (1 + `mass_margin_ratio` of its maturity class), then x (1 + `system_mass_margin_ratio`). Centre of gravity and inertia use nominal masses of items that have a position; the others are excluded and reported (`MASS_PROPS_MISSING`).
- Mass limits are checked against the system-margined total (`MASS_LIMIT_EXCEEDED` when exceeded).

## Margin policy schema 2

`margin_ratio` became `power_margin_ratio` and `mass_margin_ratio` per class; `system_margin_ratio` became `system_power_margin_ratio` and `system_mass_margin_ratio`. Version 1 files migrate in memory (`FILE_MIGRATED`); the new mass values are placeholders until supplied.

Every number in `config/` is `{value, source, note?}`. `source: TBD` or `value: null` marks a placeholder and raises the warning `CONFIG_PLACEHOLDER`. Never copy standards values without a source.

Units: the field-name suffix is the unit. A value may be written with a unit (`mass_kg: 200 g`); it is saved as the canonical number. See D-025, D-026.

JSON Schemas for all kinds: `budget export-schemas <dir>` (also committed in `src/budget_core/schemas/`).

## Problem codes (`budget validate`)

Errors: `FILE_NOT_FOUND`, `FILE_INVALID`, `YAML_SYNTAX`, `KIND_MISMATCH`, `SCHEMA_VERSION_MISSING`, `SCHEMA_TOO_NEW`, `SCHEMA_MIGRATION_MISSING`, `SCHEMA_MIGRATION_FAILED`, `FIELD_MISSING`, `FIELD_UNKNOWN`, `FIELD_INVALID`, `UNIT_INVALID`, `DUPLICATE_NAME`, `SOURCE_MISSING`, `REF_UNKNOWN_BUS`, `REF_UNKNOWN_MATURITY`, `REF_UNKNOWN_UNIT`, `REF_UNKNOWN_UNIT_MODE`, `UNIT_NOT_MAPPED`.
Errors (config values): `CONFIG_VALUE_INVALID`, `REF_UNKNOWN_PHASE`, `PHASE_MASS_MISSING`.
Result findings: `MASS_LIMIT_EXCEEDED` (error). Warnings: `MASS_PROPS_MISSING`, `MASS_FRAME_UNDEFINED`, `RESULT_INCOMPLETE` (a result needs a placeholder number, shown as n/a), `CONFIG_MISSING`, `CONFIG_PLACEHOLDER`, `CONFIG_EMPTY_TABLE`. Info: `FILE_MIGRATED`, `MASS_INERTIA_POINT_MASS`.

## Schema versions

Older files are migrated in memory (`budget_core/io/migrations.py`, one function per version step); newer files fail with `SCHEMA_TOO_NEW`. All kinds are at version 1.
