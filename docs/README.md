# Documentation index

This page is the map of everything written about System Budget Studio. If you are new, read the first two links under *Getting started* and stop there.

**Contents:** [Getting started](#getting-started) · [User guides](#user-guides) · [Reference](#reference) · [Examples](#examples) · [Developer docs](#developer-docs) · [Records and history](#records-and-history)

## Getting started

| Page | What it is for |
|---|---|
| [../README.md](../README.md) | What the tool is and a ten-line quick start |
| [getting-started.md](getting-started.md) | Prerequisites, install on Windows, macOS and Linux, a first budget, a worked example, the window |
| [glossary.md](glossary.md) | Every term and abbreviation (BOL, EIRP, Eb/N0, placeholder, …) |

## User guides

| Page | What it is for |
|---|---|
| [user-manual/](user-manual/README.md) | The task-by-task manual: one page per workflow |
| [user-manual/create-a-project.md](user-manual/create-a-project.md) | Start a project; what is in the folder; revisions |
| [user-manual/describe-the-spacecraft.md](user-manual/describe-the-spacecraft.md) | Units, power modes, spacecraft modes, buses, phases |
| [user-manual/placeholders-and-sources.md](user-manual/placeholders-and-sources.md) | *n/a*, INCOMPLETE, how to enter a sourced number |
| [user-manual/power-budget.md](user-manual/power-budget.md) | Static and time-domain power budgets |
| [user-manual/mass-budget.md](user-manual/mass-budget.md) | Mass, centre of gravity, inertia, phases, limits |
| [user-manual/thermal-budget.md](user-manual/thermal-budget.md) | Dissipation, node temperatures, unit limits |
| [user-manual/link-budget.md](user-manual/link-budget.md) | Link margin, data volume over passes |
| [user-manual/scenarios.md](user-manual/scenarios.md) | Orbits, stations, mode timeline, SpaceMissionStudio data |
| [user-manual/reports-and-exports.md](user-manual/reports-and-exports.md) | Files written, reproducible reports, the guide |
| [user-manual/compare.md](user-manual/compare.md) | Differences between revisions or scenarios |
| [user-manual/read-and-fix-problems.md](user-manual/read-and-fix-problems.md) | What messages mean and how to fix them |
| [user-manual/use-the-window.md](user-manual/use-the-window.md) | The GUI tour and shortcuts |
| [user-manual/command-line.md](user-manual/command-line.md) | Every command, option, exit code |
| [tips.md](tips.md) | Shortcuts, habits, scripting, links to the other tools |
| [faq.md](faq.md) | Short answers to common questions |
| [troubleshooting.md](troubleshooting.md) | Install, start-up and run errors with fixes |
| *In-app user guide* | The same material by topic, inside the tool (*Help → User guide*, or `budget guide --out guide`); sources in [`src/budget_core/guide/chapters/`](../src/budget_core/guide/chapters/) |

## Reference

| Page | What it is for |
|---|---|
| [FILE_FORMAT.md](FILE_FORMAT.md) | Every project file, field and problem code |
| [ENVIRONMENT_FORMAT.md](ENVIRONMENT_FORMAT.md) | Scenario files, orbits, and the interim SpaceMissionStudio format |
| [THERMAL_SOURCES.md](THERMAL_SOURCES.md) | Candidate reference sources for the numbers a thermal engineer must supply |
| [LICENCES.md](LICENCES.md) | Licences of every runtime dependency |
| [SPEC.md](SPEC.md) | The original requirements (written as a brief to the implementer; authoritative) |

## Examples

| Page | What it is for |
|---|---|
| [../examples/README.md](../examples/README.md) | The four example projects: what each shows, how to run it, expected output |

## Developer docs

| Page | What it is for |
|---|---|
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Set up, rules, how to get a change merged |
| [developer/README.md](developer/README.md) | Layout, tests, generated files, keeping docs true, releases |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the tool is built |
| [INSTALL_CHECKLIST.md](INSTALL_CHECKLIST.md) | Clean-machine install checklist for a release |
| [BRANCH_PROTECTION.md](BRANCH_PROTECTION.md) | Repository settings for the owner to apply |
| [../CLAUDE.md](../CLAUDE.md) | Short working notes for the AI assistant that builds the tool |

## Records and history

| Page | What it is for |
|---|---|
| [DECISIONS.md](DECISIONS.md) | Every design decision with its reason (numbers `D-001`…) |
| [DEVIATIONS.md](DEVIATIONS.md) | Every simplification of the physics (`DV-…`) |
| [PLAN.md](PLAN.md) | The milestones M0 to M6 |
| [../CHANGELOG.md](../CHANGELOG.md) | What changed |
| [demo/](demo/M0.md) | One short note per milestone (historical: written when each milestone was finished): [M0](demo/M0.md) · [M1](demo/M1.md) · [M2a](demo/M2a.md) · [M2b](demo/M2b.md) · [M3a](demo/M3a.md) · [M3b](demo/M3b.md) · [M4](demo/M4.md) · [M4b](demo/M4b.md) · [M5](demo/M5.md) · [M6](demo/M6.md) |
| [DOCS_AUDIT.md](DOCS_AUDIT.md) | The audit behind this documentation structure |

Next: [Getting started](getting-started.md).
