# Command-line reference

This page lists every `budget` command with its options, the exit codes, and the environment variables that matter. `budget <command> --help` prints the same options.

**Contents:** [Commands](#commands) · [Common options](#common-options) · [Exit codes](#exit-codes) · [Environment variables](#environment-variables) · [Use in scripts and CI](#how-do-i-use-it-in-a-script-or-in-ci)

## Commands

| Command | What it does |
|---|---|
| `budget validate PROJECT [--format text\|json] [--strict]` | Check a project folder and list problems |
| `budget run PROJECT [--budget power\|mass\|thermal\|link\|all] [--report …] [--out DIR]` | Compute the static budgets and write reports (default: all budgets, all report kinds) |
| `budget scenario PROJECT [--scenario ID] [--out DIR]` | Compute a scenario's eclipses, passes and mode timeline |
| `budget power-timeline PROJECT [--scenario ID] [--case bol\|eol\|both] [--load-basis nominal\|margined] [--phase NAME] [--series-every N] [--no-plots] [--report …] [--out DIR]` | Time-domain power budget of a scenario |
| `budget link-passes PROJECT [--scenario ID] [--no-plots] [--report …] [--out DIR]` | Link margin, selected data rate and data volume over every pass |
| `budget compare PROJECT [OTHER] [--scenario ID] [--scenario-a ID] [--scenario-b ID] [--budget …] [--report …] [--max-rows N] [--out DIR]` | Compare two revisions or two scenarios |
| `budget guide --out DIR [--format html\|pdf\|all] [--project PROJECT]` | Write the user guide (offline HTML and PDF) |
| `budget self-test` | Check that this installation can compute and render a budget |
| `budget export-schemas DIR` | Write the JSON Schema of every file kind |
| `budget export-examples DIR` | Write the four example projects |
| `budget --version` | Print the version |

`--report` can be repeated and takes `xlsx`, `pdf`, `docx`, `json`, `csv` or `all`. `--scenario` is optional when the project has only one.

## Common options

| Option | Meaning |
|---|---|
| `--out DIR` | Output folder (default: `<project>/results`) |
| `--user NAME` | User name for the provenance block (default: `BUDGET_USER`, then your login name) |
| `--date ISO8601` | Generation time (default: `SOURCE_DATE_EPOCH`, then the clock); with `--user` it makes a report reproducible |
| `--strict` | Treat warnings as failures (exit code 1) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Finished; no error-level problem (and no warning with `--strict`) |
| 1 | An error-level problem or finding, a file that could not be written, or an unexpected error (one plain line, never a traceback) |
| 2 | The command was called wrongly (unknown option, a value not allowed, `compare` without a second side) |
| 130 | Interrupted with Ctrl+C |

Note that finding a *result* problem (a limit exceeded) is exit code 1 even though every file was written.

## Environment variables

| Variable | Used for |
|---|---|
| `BUDGET_USER` | The user name in the provenance block |
| `SOURCE_DATE_EPOCH` | The generation time (seconds since 1970) |
| `QT_QPA_PLATFORM=offscreen` | Run the window without a screen (tests, `system-budget-studio --smoke`) |

## How do I use it in a script or in CI?

```bash
budget validate project --strict            # fail on any warning
budget run project --budget power --report csv --report json --out out
budget power-timeline project --out out || echo "violations found"   # exit code 1
```

`budget validate --format json` prints the problems as JSON for other tools. The tool needs no network and writes only into the output folder you name. The [offline test](../developer/README.md#the-offline-test) keeps that true.

Next: [Tips](../tips.md) · [Troubleshooting](../troubleshooting.md).
