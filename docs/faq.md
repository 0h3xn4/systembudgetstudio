# FAQ

Short answers to the questions newcomers ask most. Each links to the page with the detail.

**Contents:** [General](#general) · [Numbers and sources](#numbers-and-sources) · [Using it](#using-it) · [Files and teams](#files-and-teams)

## General

### What does the tool do, in one sentence?

It computes power, mass, thermal and link budgets for a satellite from a model kept in plain text files, with every number sourced and every result reproducible ([README](../README.md)).

### Does it need the internet?

No, never while running. There is no telemetry, no update check and no online help; an automated test fails if the tool imports a networking module or opens a socket. You need the internet only once, to install the libraries (or never, with a [wheelhouse](getting-started.md#offline-install)).

### Which systems does it run on?

Windows 10/11 and Linux (RHEL/Rocky 8 or newer, Ubuntu LTS), Python 3.11 to 3.13. macOS is not tested.

### Is it free to use? What is the licence?

It is for internal use; the project decided not to add a LICENSE file. The libraries it uses are permissively licensed or LGPL ([licence list](LICENCES.md)).

### Are the examples real?

No. All example data is invented, and says so in every `source` field. Never use an example number in a real analysis.

## Numbers and sources

### Why does the tool refuse to give me a default margin or efficiency?

Because a plausible-looking default would end up in a review as if it were a decision. You supply the number with its source; until then results say *n/a* ([placeholders](user-manual/placeholders-and-sources.md)).

### What is the difference between a warning and an error?

A warning is something open (a placeholder, an empty table). An error is an invalid input or a violated limit. Errors give exit code 1; add `--strict` to make warnings do so too ([problems](user-manual/read-and-fix-problems.md#what-do-error-warning-and-info-mean)).

### Can I trust the equations?

They are textbook relations, each named in the *Equations and sources* chapter of the user guide. Where the reference text has not been attached the equation is flagged `SOURCE_MISSING`; treat such results as engineering estimates until your team has confirmed them. The simplifications of the physics are listed in [DEVIATIONS.md](DEVIATIONS.md) (perfect pointing, no albedo for the array, one array temperature, steady-state thermal only, and so on).

### Can I use dB and linear values together?

The tool never converts between them for you: a `dBW` value in a watt field is an error, on purpose ([units](user-manual/describe-the-spacecraft.md#how-do-i-write-units)).

## Using it

### How do I start a new project?

With the wizard (File → New project) or by copying an example: [create a project](user-manual/create-a-project.md).

### Why is my power timeline `n/a`?

It needs a complete `config/power_system.yaml`, a scenario and a mission phase. See [troubleshooting](troubleshooting.md#bol-na-inputs-missing-see-the-problems-below).

### How do I see what changed between two versions of my project?

[Compare](user-manual/compare.md): `budget compare old new`.

### Can I run it in CI or from a script?

Yes: exit codes, `--strict`, `--format json` and no network use are made for that ([command-line reference](user-manual/command-line.md#how-do-i-use-it-in-a-script-or-in-ci)).

### Can I import my units from a spreadsheet?

Not yet. Import from CSV or XLSX is in the specification but not built; enter units in the unit editor or the YAML files ([decision D-099](DECISIONS.md)). You can read every result *out* as XLSX, CSV or JSON.

### How do I regenerate last month's report byte for byte?

Same project folder (a checkout of that revision), same `--user`, same `--date`: [reports](user-manual/reports-and-exports.md#how-do-i-regenerate-a-report-exactly).

### The window and the command line give different answers?

They should not: both call the same core. If they do, that is a bug; save the project state and report it.

## Files and teams

### Where are my files? Does the tool keep settings or logs?

Your projects and reports are in folders you choose. The tool keeps no settings, caches, logs or crash dumps outside your project folders, and never writes project content to logs or temporary files elsewhere.

### Can several people work on one project?

Yes: put the folder in git. Units, modes, links and scenarios are separate files, and files are plain text with stable formatting, so they diff and merge cleanly.

### Is project data safe to share?

The tool itself never sends data anywhere, and its messages never repeat values from your files. The *files* may still contain export-controlled information: handle them as your organisation requires, and check who can see the repository you keep them in.

Next: [Troubleshooting](troubleshooting.md) · [Glossary](glossary.md).
