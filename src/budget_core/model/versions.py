"""Current schema version of every file kind. Bump with a migration (see io/migrations.py)."""

CURRENT_VERSIONS: dict[str, int] = {
    "project": 1,
    "spacecraft": 1,
    "unit": 1,
    "spacecraft_mode": 1,
    "margin_policy": 1,
    "power_config": 1,
    "ebn0_table": 1,
    "attenuation_table": 1,
}
