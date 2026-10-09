# Project file format (schema version 1)

A project is a folder of YAML files (LF line endings). Every file starts with `schema_version` and `kind`.

```
project.yaml            kind: project            name, revision, description
spacecraft.yaml         kind: spacecraft         name, buses[{name, nominal_voltage_v}]
units/<id>.yaml         kind: unit               name, subsystem, mass_kg, bus, maturity, modes[]
modes/<id>.yaml         kind: spacecraft_mode    name, description, assignments{unit id: power mode name}
config/margin_policy.yaml      kind: margin_policy       classes{name: {margin_ratio}}, system_margin_ratio
config/power_config.yaml       kind: power_config        distribution_loss_ratio, converter_efficiency_ratio{bus}
config/ebn0_table.yaml         kind: ebn0_table          entries[{modulation, coding, required_ebn0_db}]
config/attenuation_table.yaml  kind: attenuation_table   entries[{name, attenuation_kind, freq_hz, elevation_deg, loss_db}]
```

Power mode: `name`, `avg_power_w`, `peak_power_w` (>= average), `duty_cycle_ratio` (0..1, default 1), optional `min_duration_s`, `max_duration_s`. Effective average power = `avg_power_w * duty_cycle_ratio` (D-024).

Every number in `config/` is `{value, source, note?}`. `source: TBD` or `value: null` marks a placeholder and raises the warning `CONFIG_PLACEHOLDER`. Never copy standards values without a source.

Units: the field-name suffix is the unit. A value may be written with a unit (`mass_kg: 200 g`); it is saved as the canonical number. See D-025, D-026.

JSON Schemas for all kinds: `budget export-schemas <dir>` (also committed in `src/budget_core/schemas/`).

## Problem codes (`budget validate`)

Errors: `FILE_NOT_FOUND`, `FILE_INVALID`, `YAML_SYNTAX`, `KIND_MISMATCH`, `SCHEMA_VERSION_MISSING`, `SCHEMA_TOO_NEW`, `SCHEMA_MIGRATION_MISSING`, `SCHEMA_MIGRATION_FAILED`, `FIELD_MISSING`, `FIELD_UNKNOWN`, `FIELD_INVALID`, `UNIT_INVALID`, `DUPLICATE_NAME`, `SOURCE_MISSING`, `REF_UNKNOWN_BUS`, `REF_UNKNOWN_MATURITY`, `REF_UNKNOWN_UNIT`, `REF_UNKNOWN_UNIT_MODE`, `UNIT_NOT_MAPPED`.
Errors (config values): `CONFIG_VALUE_INVALID`.
Warnings: `RESULT_INCOMPLETE` (a result needs a placeholder number, shown as n/a), `CONFIG_MISSING`, `CONFIG_PLACEHOLDER`, `CONFIG_EMPTY_TABLE`. Info: `FILE_MIGRATED`.

## Schema versions

Older files are migrated in memory (`budget_core/io/migrations.py`, one function per version step); newer files fail with `SCHEMA_TOO_NEW`. All kinds are at version 1.
