# Reports and exports

This page lists the files the tool writes, shows how to choose them, and explains how to regenerate a report exactly.

**Contents:** [Which files](#which-files-do-i-get) · [Choose what is written](#how-do-i-choose-what-is-written) · [Regenerate exactly](#how-do-i-regenerate-a-report-exactly) · [From the window](#how-do-i-export-from-the-window) · [User guide](#how-do-i-get-the-user-guide)

## Which files do I get?

| Kind | Content |
|---|---|
| XLSX | One sheet per table in the classic review layout, plots as pictures, the configuration numbers used with their sources, the equations, the problems and the provenance |
| PDF | The same tables and plots on A4 landscape pages, with a provenance footer |
| DOCX | The same content for editing in a word processor |
| CSV | Every table and every time series, one file each; empty cells where a value is n/a. Each set also has `<name>_provenance.csv` |
| JSON | The full result for other tools, with the provenance |

Commands and what they write (prefix is the file name start):

| Command | Files start with |
|---|---|
| `budget run --budget power` | `power_static` (and one CSV per spacecraft mode) |
| `budget run --budget mass` | `mass_static` (one CSV per phase) |
| `budget run --budget thermal` | `thermal_static`, `thermal_case_<case>` |
| `budget run --budget link` | `link_static` |
| `budget power-timeline` | `power_time_<scenario>` (series per case, orbits, violations) |
| `budget link-passes` | `link_passes_<scenario>` |
| `budget scenario` | `<scenario>_environment.json`, `_eclipses.csv`, `_passes.csv`, `_timeline.csv` |
| `budget compare` | `compare` and `compare_differences.csv` |

All of them write to `<project>/results` unless you give `--out`.

## How do I choose what is written?

`--report xlsx --report csv` (repeat the option; the default is all kinds). `--budget` chooses the budget for `run`. `--no-plots` leaves the plots out of the reports (faster). `--series-every N` thins the time-series CSV of `power-timeline`.

## How do I regenerate a report exactly?

The same project, scenario, user name and generation time give the same file contents, byte for byte. A report carries the time and the user in its provenance block, so to reproduce an earlier report give both:

```bash
budget run my_satellite --user "A. Engineer" --date 2026-01-02T00:00:00Z --out out
```

Without them the user is the `BUDGET_USER` environment variable or your login name, and the date is `SOURCE_DATE_EPOCH` or the clock. Every report records the tool version, the library versions, the project revision, the scenario, the time and the user; because of that, remember to raise `revision` in `project.yaml` when you change numbers ([revisions](create-a-project.md#how-do-i-keep-revisions)).

## How do I export from the window?

**File → Export reports** (Ctrl+E) writes the reports of all static budgets to a folder you choose. **File → Export power timeline** (Ctrl+Shift+E) writes the power timeline. The Power timeline, Link passes and Compare tabs also have an **Export…** button. Long exports run in the background and the window stays usable; a second export cannot start while one runs.

An export never overwrites a file by writing half of it: files are written to a temporary name and moved into place, and file names are reduced to letters, digits, `.`, `-` and `_`.

## How do I get the user guide?

Inside the window: **Help → User guide** (F1). As files:

```bash
budget guide --out guide                       # system-budget-studio-guide.html and .pdf
budget guide --out guide --project my_satellite   # also list your project's numbers and their sources
```

The HTML is a single self-contained file (fonts inlined, no scripts, no external resource). Its last chapter, *Equations and sources*, lists every equation the tool uses with its source (or `SOURCE_MISSING`), the constants shipped in code, and with `--project` every sourced number of your configuration and whether it is still a placeholder.

Next: [Compare](compare.md).
