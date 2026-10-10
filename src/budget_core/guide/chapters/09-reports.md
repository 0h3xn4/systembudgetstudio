# Reports and exports

`budget run`, `budget power-timeline`, `budget link-passes` and `budget compare` write their results next to each other:

| Kind | Content |
|---|---|
| XLSX | One sheet per table in the classic review layout, plots as pictures, assumptions and provenance |
| PDF | The same tables and plots on A4 landscape pages, with a provenance footer |
| DOCX | The same content for editing in a word processor |
| CSV | Every table and every time series, one file each, empty cells for values that are n/a |
| JSON | The full result for other tools |

Choose kinds with `--report xlsx --report csv` (default: all). In the window use **File > Export reports**.

## Assumptions and equations

Each report ends with the configuration numbers used (value, source, placeholder or sourced), the equations with their sources, the problems and the provenance. Entries that depend on placeholders show **n/a**, and the report starts with the INCOMPLETE banner.

## Reproducible files

The same project, scenario, user name and generation time give the same file contents. Use `--user` and `--date` (or `BUDGET_USER` and `SOURCE_DATE_EPOCH`) to regenerate an earlier report.

Every set of CSV files comes with a `<name>_provenance.csv` (tool and library versions, project, revision, scenario, time, user), because a CSV has no room for a header block. Plots exist only inside the reports, which carry the same provenance block; no plot is written as a loose image.

## Entering power data

Unit power data is typed in the unit editor or written in the unit's YAML file (`units/<id>.yaml`). Importing unit tables from CSV or XLSX is not part of version 1; a supplier's figures are entered by hand, with their source.
