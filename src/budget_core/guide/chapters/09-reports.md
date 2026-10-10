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

## Importing power data

Unit power tables can be exported to and imported from CSV or XLSX templates that the tool generates itself, so a supplier's data can be filled in outside the tool.
