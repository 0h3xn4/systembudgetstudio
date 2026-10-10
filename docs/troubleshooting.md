# Troubleshooting

This page lists the errors you are most likely to meet when installing and starting the tool, with the exact text and the fix. Messages about your *project files* (problem codes such as `UNIT_INVALID`) are in [Read and fix problems](user-manual/read-and-fix-problems.md).

**Contents:** [Install](#install) · [Start the window](#start-the-window) · [Run a command](#run-a-command) · [Results](#results) · [Still stuck](#still-stuck)

## Install

### `pip install -e .` fails with "requires a different Python" or "No matching distribution"

The tool supports Python 3.11, 3.12 and 3.13 (not 3.14 or newer, not 3.10 or older). Check `python3 --version`, install a supported one, and create the virtual environment with it: `python3.13 -m venv .venv`.

### `pip` says "externally-managed-environment"

Your system Python refuses installs outside a virtual environment. Create one (`python3 -m venv .venv`, then activate it) as in [getting started](getting-started.md#2-install) and run `pip install -e .` inside it.

### `budget: command not found` (or `'budget' is not recognized`)

The virtual environment is not active in this terminal. Activate it from the repository folder: `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`). Your prompt then starts with `(.venv)`.

### PowerShell: "running scripts is disabled on this system"

Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, answer `Y`, then activate again. It only affects that window.

### `pip install` cannot reach the internet

On a machine without internet access, use a wheelhouse: [offline install](getting-started.md#offline-install).

## Start the window

### The window does not open on Linux

```text
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized.
```

A system library is missing. On Ubuntu or Debian: `sudo apt install libxcb-cursor0`. On RHEL or Rocky install the Qt libraries listed in the user guide chapter *Installing and uninstalling* ([source](../src/budget_core/guide/chapters/12-installation.md)) and, if the message stays, the package that provides `libxcb-cursor.so.0` (`dnf provides '*/libxcb-cursor.so.0'`). The command-line `budget` does not need it. To see what else is missing: `QT_DEBUG_PLUGINS=1 system-budget-studio`.

### "This plugin does not support propagateSizeHints()"

A harmless Qt message, printed when the window starts on some Linux set-ups (and always under `QT_QPA_PLATFORM=offscreen`). Ignore it.

### No window appears, but there is no error (Linux over SSH or in a container)

There is no display. Use the command line, or run with a display (X forwarding, a desktop session). For tests set `QT_QPA_PLATFORM=offscreen`; `system-budget-studio --smoke` then creates the window and prints `Smoke test passed.`

## Run a command

### `<project>: error FILE_NOT_FOUND: The project folder does not exist.`

The path is wrong. A project folder contains `project.yaml`. Run `budget validate <folder>`; if you are in the wrong directory, give the path relative to where you are or an absolute path.

### `spacecraft.yaml: error FILE_NOT_FOUND: The file cannot be read.`

The folder exists but is not a project (for example an empty folder), or a file is missing. Compare with an example: `budget export-examples demo` and look at `demo/cubesat_3u`.

### `A file could not be written. Check that the output folder exists, is a folder and that you may write to it.`

`--out` points at a file, a folder you cannot write to, or a path that does not exist and cannot be created. Choose a folder you own. Without `--out` the tool writes to `<project>/results`, so the project folder itself must be writable.

### `Two outputs would be written to the same file name.`

Two units, links, phases or cases have names that become the same file name (file names keep only letters, digits, `.`, `-`, `_`). Rename one.

### `<project>: error SCENARIO_UNKNOWN: Scenario 'x' does not exist.`

The `--scenario` id is wrong. The message ends with the list of scenarios the project has (`Defined scenarios: one_day.`); the id is the file name in `scenarios/` without `.yaml`.

### `budget run: error: argument --budget: invalid choice`

You gave a value the option does not accept; the message lists the allowed ones. Exit code 2.

### `Give a second project folder, or two different scenarios (--scenario-a and --scenario-b) of the same project.`

`budget compare` needs two sides. Give two folders, or `--scenario-a` and `--scenario-b` that differ. See [compare](user-manual/compare.md).

### The command wrote all its files but exited with code 1

By design: an error-level *finding* (a limit exceeded) makes the exit code 1. Read the last lines of the output. The `cubesat_3u_eps` example does this on purpose ([examples](../examples/README.md#exit-codes-in-the-examples)).

### `A file or folder could not be read or written. Check the paths and that you may use them.`

A permission or path problem that is not one of the cases above (for example a read-only disk or a missing parent folder). Check the paths and your permissions.

### `Internal error (SomeError). Run 'budget validate <project folder>' to check the project and report the problem.`

A bug. The message names only the kind of error, never your data. Run `budget validate <project>` for details and report it with the error name.

## Results

### Results say `n/a` and the report starts with INCOMPLETE

A number the result needs is a placeholder. That is intended: see [placeholders and sources](user-manual/placeholders-and-sources.md).

### `BOL: n/a (inputs missing, see the problems below).`

The power timeline needs `config/power_system.yaml` with a complete array and battery, a scenario and a mission phase; the examples `cubesat_3u`, `microsat_150kg` and `stress_200_units` have templates only. Use `cubesat_3u_eps`, or fill in the numbers.

### Same inputs, different file bytes

Reports include the generation time and the user. Pass `--user` and `--date` to regenerate exactly: [reports and exports](user-manual/reports-and-exports.md#how-do-i-regenerate-a-report-exactly).

### The run is slow

A week at 1 s with 200 units takes about ten seconds; the orbit computation dominates. While exploring, use a larger `step_s` in the scenario, and with `power-timeline` or `link-passes` add `--no-plots`, `--report csv` or (power-timeline) `--series-every N`.

## Still stuck

1. Run `budget self-test`. It checks the installation and says what failed.
2. Run `budget validate <project>` and read the first error: later ones are often consequences.
3. Search the [FAQ](faq.md).
4. For a bug, collect the output of `budget --version`, the command you ran and the message. Do not attach project files if they may be sensitive; messages never contain your values.

Next: [FAQ](faq.md) · [Glossary](glossary.md).
