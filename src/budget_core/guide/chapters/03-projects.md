# Projects and files

A project is a folder of YAML files with LF line endings. Every file starts with `schema_version` and `kind`. Files are meant to be read, edited and compared with ordinary text tools; a folder under version control gives you a full history of revisions.

```
project.yaml              name, revision, description
spacecraft.yaml           buses, mission phases, body frame
units/<id>.yaml           one file per unit: mass, bus, maturity, power modes, limits
modes/<id>.yaml           spacecraft modes: which power mode each unit is in
orbits/  ground_stations/  targets/  scenarios/
links/<id>.yaml           one file per RF link
expendables/<id>.yaml     consumables with a mass per mission phase
config/                   margin policy, power, thermal, Eb/N0 and attenuation tables
```

The complete field list is in the file format reference (`docs/FILE_FORMAT.md` in the source repository), and the JSON Schema of every kind is written by `budget export-schemas <folder>`.

## Sourced numbers

Everything in `config/` and every RF or thermal parameter is written as:

```
power_margin_ratio:
  value: 0.15
  source: "Programme margin policy, section 4"
  note: "optional free text"
```

`source: TBD` or a missing `value` marks a placeholder. The tool still loads the project and warns with `CONFIG_PLACEHOLDER`. Results that need the number show **n/a**.

## Revisions

`project.yaml` carries a `revision`. Increase it whenever you change the numbers behind a report; it is printed on every output and used by the comparison view to label the two sides.

## Older files

Files written by earlier versions are upgraded in memory when they are loaded (the Problems panel shows `FILE_MIGRATED`). They are written back in the new format only when you save them.

## Validating

`budget validate <folder>` lists every problem; `--strict` also fails on warnings. The GUI runs the same checks each time a file is saved.
