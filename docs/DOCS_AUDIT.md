# Documentation audit

Audit of every document, `--help` text and in-app help of System Budget Studio, made on branch `docs-audit` (from `main` at commit `15a6e53`). The audit was written **before** any other file was changed (commit `71568d3`); the *Status* column was updated at the end, and findings A20 to A23 were added while rewriting.

## Summary

| | |
|---|---|
| Is the repository a fork? | **No.** `fork: false` in the GitHub API, a single `origin` remote and no `upstream`, 45 commits all made in this repository (the first one adds the specification). So the README uses the single-README layout and there is no upstream README to preserve. |
| Documents found | `README.md`, `CLAUDE.md`, 11 files in `docs/`, 10 milestone demo notes in `docs/demo/`, 12 chapters of the in-app user guide (`src/budget_core/guide/chapters/`), `assets/licences/README.md`, the `--help` text of 10 CLI commands. No images, no CHANGELOG, no CONTRIBUTING. |
| Clean-venv run | `python3 -m venv` + `pip install -e .` on Python 3.13: **works** (all 25 wheels installed, no compiler needed). `budget --version`, `export-examples`, `validate`, `run`, `scenario`, `link-passes`, `power-timeline`, `compare`, `guide`, `self-test` and `system-budget-studio --smoke` all work as documented, with the exceptions listed below. |
| Biggest problems | (1) there is no path for a newcomer: no clone/venv step, no getting-started page, no docs index, no glossary, no troubleshooting for installation; (2) the README opens with one 400-word sentence of milestone names; (3) `docs/ARCHITECTURE.md` still describes features that were never built (`--reproducible`, an import-linter test, hand-calculation files); (4) no document links to another one (all references are code spans, so nothing is clickable on GitHub); (5) on Linux the GUI does not start without `libxcb-cursor0`, and no document says so. |
| Counts | 50 findings (46 found before the rewrite, 4 more while rewriting: A20 to A23): 9 high, 26 medium, 15 low. 49 fixed (A20 and A21 have an application-code part that is deferred to the owner), 1 deferred (A23, needs a Windows machine). See "Deferred". |

Severity: **high** = a newcomer is blocked or misled; **medium** = wrong or missing information that costs time; **low** = polish.

## Findings

### A. Accuracy (what the text says versus what the tool does)

| # | File | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|---|
| A1 | `README.md` | Install block starts at `pip install -e .` with no `git clone`, no `cd`, no virtual environment. It fails outside the repository root; nothing says the package is not on PyPI. | high | New README quick start and `docs/getting-started.md` with clone + venv for Windows, macOS, Linux. | fixed |
| A2 | `README.md`, guide ch. 2 | `budget compare demo/cubesat_3u_eps other_revision`: there is no `other_revision` folder, so the command fails (`FILE_NOT_FOUND`) as written. | medium | Use two folders that exist (`cubesat_3u_eps` and `cubesat_3u`) and show how to make a second revision. | fixed |
| A3 | `README.md` | Two listed commands (`budget run … --budget thermal`, `budget power-timeline …`) end with exit code 1 on the example. That is by design (a thermal-margin finding on the radio; peak power above the limit) but it is not explained, so it looks like a failure. | medium | Explain exit codes in getting-started and the examples page, with the real output. | fixed |
| A4 | `README.md` | "Status" is a single paragraph naming milestones M0 to M6 ("M6 Polish on top of M5 on top of …"); a newcomer cannot tell what the tool does. | high | Replace with "What is this?" and a Features list; milestone history moves to `CHANGELOG.md`. | fixed |
| A5 | `README.md`, `docs/`, guide ch. 12 | Linux: the GUI fails with "Could not load the Qt platform plugin xcb … xcb-cursor0 or libxcb-cursor0 is needed" on a plain Ubuntu install. Not documented anywhere (guide ch. 12 lists packages for the *installer* on RHEL only). | high | Prerequisites in getting-started and the first entry of `docs/troubleshooting.md` (real error text). | fixed |
| A6 | `docs/ARCHITECTURE.md` | Title says "(proposal)"; the tool is built. | low | Retitle, add a status line. | fixed |
| A7 | `docs/ARCHITECTURE.md` §3 | Says a `--reproducible` mode exists. The CLI has `--user` and `--date` (and `BUDGET_USER`, `SOURCE_DATE_EPOCH`) instead. | medium | Correct the text. | fixed |
| A8 | `docs/ARCHITECTURE.md` §2 | "enforced by import-linter test": there is no import-linter; the rules are kept by convention and the offline test checks networking only. | medium | Correct the text. | fixed |
| A9 | `docs/ARCHITECTURE.md` §9 | "hand calculations committed in `tests/regression/*.md`": there are no such files; the hand calculations are comments inside the test files. | medium | Correct the text. | fixed |
| A10 | `docs/ARCHITECTURE.md` §2 | Stray draft text: "`budget_gui → budget_cli? no`". | low | Remove. | fixed |
| A11 | `docs/ARCHITECTURE.md` §4 | Says `project.yaml` holds a spacecraft ref and a margin-policy ref, and `spacecraft.yaml` holds array, battery and converters. In the real format `project.yaml` has name, revision and description; array and battery are in `config/power_system.yaml`, converters in `config/power_config.yaml`. | medium | Point to `docs/FILE_FORMAT.md` and fix the tree. | fixed |
| A12 | `docs/PLAN.md` | Title "(proposal)"; every milestone is done. | low | Retitle, status line. | fixed |
| A13 | `docs/BRANCH_PROTECTION.md` | Says to change the default branch to `main` (it already is) and that the repository is "currently public" without saying that this conflicts with `docs/SPEC.md` (stop and ask if public). | medium | Update the status of each item; the visibility decision stays with the owner (see "Decisions needed"). | fixed (visibility decision stays with the owner) |
| A14 | `docs/ENVIRONMENT_FORMAT.md` | "Commands" says `budget scenario` writes four files; it writes five (`<id>_provenance.csv` since D-100). | low | Correct. | fixed |
| A15 | `docs/FILE_FORMAT.md`, guide ch. 11 | The list of problem codes lacks `LINK_NOT_CLOSED` (D-098) and `INTERNAL_ERROR`. | medium | Add both with what to do. | fixed |
| A16 | guide ch. 3, 8 | Refer to `docs/FILE_FORMAT.md` and `docs/ENVIRONMENT_FORMAT.md`, which are not inside an installed copy of the tool. | medium | Say "in the source repository"; list the files in the docs index. | fixed |
| A17 | `docs/demo/M0.md`, `M1.md` | Say "three synthetic projects"; there are four (the stress case is the fourth). These are milestone logs, true when written. | low | Label the demo notes as historical in the docs index; leave the notes unchanged. | fixed (labelled historical) |
| A18 | `docs/SPEC.md` | Written as an instruction to the implementer ("You are a senior software engineer …", "the repository is empty"). It is authoritative (`CLAUDE.md`), so it is not rewritten. | low | The docs index says what it is and who it is for. | fixed (labelled in the index) |
| A19 | `README.md` | "Offline use" promises a "user-started reference-data download (later milestones)"; no such feature exists. | low | Say plainly that nothing is downloaded. | fixed |
| A20 | `src/budget_gui/main_window.py` (UI text), `docs/demo/M3b.md` | The message "Compute a scenario first (Ctrl+R)" and the demo note name a Ctrl+R shortcut that does not exist (the window has a **Compute** button and no such key). The documents do not claim it. | low | Documents: the demo note now says "press the Compute button". The UI string is application code, out of scope here. | fixed (docs); UI text deferred: owner |
| A21 | `docs/demo/M3b.md`, `main_window.py` | The demo note says *File → Export scenario results* writes the scenario files; the menu has no such entry (`_choose_scenario_export` is not connected to any menu or button), so the window cannot export a scenario. `budget scenario` can. | medium | Documents corrected (demo note, user manual say so). Wiring the menu item is a code change: deferred, owner to decide. | fixed (docs); feature gap deferred: owner |
| A22 | `docs/ARCHITECTURE.md` §3, §4 | Described a `budget_core/refdata/` download module and a `budgets:` registry in `project.yaml`; neither exists. | medium | Corrected: no download feature in 0.1.0; storage budgets out of scope, no registry. | fixed |
| A23 | `docs/getting-started.md` | The Windows (PowerShell) commands could not be run here: the audit machine is Linux. They mirror the commands CI runs on Windows (`python -m venv`, `pip install -e .`, `budget --version`) but were not executed. | medium | Marked here; a reviewer on Windows should run section 2 once. | deferred: needs a Windows machine |

### B. Completeness (missing documents; documents about things that do not exist)

| # | File | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|---|
| B1 | — | No getting-started page (prerequisites, install per OS, first run, a worked example). | high | `docs/getting-started.md`. | fixed |
| B2 | — | No docs index. | high | `docs/README.md`. | fixed |
| B3 | — | No user manual organised by task. The in-app guide is organised by topic and only available once the tool runs. | high | `docs/user-manual/` with one "How do I …" page per workflow. | fixed |
| B4 | `examples/` | The four example projects have no README: what each shows, how to run it, what to expect. | medium | `examples/README.md` with output from real runs. | fixed |
| B5 | — | No FAQ, no troubleshooting page for installation and start-up problems (guide ch. 11 covers problem codes only). | medium | `docs/faq.md`, `docs/troubleshooting.md`. | fixed |
| B6 | — | No glossary. Terms used without explanation: BOL/EOL, depth of discharge, state of charge, EIRP, G/T, C/N0, Eb/N0, TLE, RAAN, AOS/LOS, eclipse/umbra/penumbra, maturity class, margin policy, centre of gravity, inertia tensor, placeholder, INCOMPLETE, TBD, golden file, SBOM, ECSS (SPEC only). | high | `docs/glossary.md`; first-use links from the new pages. | fixed |
| B7 | — | No tips page, and nothing on how this tool relates to the other tools in the family. Only SpaceMissionStudio is documented (interim import format). | medium | `docs/tips.md`; states exactly what exists and what does not (see "Decisions needed"). | fixed (what exists is documented; new integrations are the owner's decision) |
| B8 | — | No `CONTRIBUTING.md`, no developer docs: dev setup is one line in `CLAUDE.md`; the release procedure exists only inside `.github/workflows/release.yml`. | medium | `CONTRIBUTING.md`, `docs/developer/` (setup, tests, release, doc maintenance). | fixed |
| B9 | — | No `CHANGELOG.md`. | medium | Add one, from `docs/PLAN.md` and `docs/DECISIONS.md`. | fixed |
| B10 | — | No CLI reference: sub-commands, options, exit codes, environment variables (`BUDGET_USER`, `SOURCE_DATE_EPOCH`, `QT_QPA_PLATFORM`) exist only in `--help` and scattered chapters. | medium | `docs/user-manual/command-line.md`. | fixed |
| B11 | — | GUI shortcuts (Ctrl+N, Ctrl+O, Ctrl+S, F5, Ctrl+M, Ctrl+E, Ctrl+Shift+E, F1) are not listed anywhere together. | low | In `docs/tips.md` and the manual. | fixed |
| B12 | repository | No screenshot anywhere. | medium | Two screenshots of the real window, saved under `docs/images/`. | fixed (screenshots from Linux/offscreen; owner may replace) |
| B13 | `docs/SPEC.md`, `README.md` | Unit-data import from CSV/XLSX and an expert mode are in the spec but not built (D-099). | low | Already recorded as deferred; the README feature list does not claim them. | fixed |
| B14 | `README.md` | No licence statement. By decision (SPEC, open decisions) there is no LICENSE file: internal use. | low | State this in the README; flag in "Decisions needed". | fixed (stated; the licence decision is the owner's) |
| B15 | repository | There is no release and no tag yet, so the installers described in guide ch. 12 cannot be downloaded. | medium | Getting-started installs from source and says installers come with the first release. | fixed (documented as source install for now) |

### C. Links and images

| # | File | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|---|
| C1 | all `docs/*.md`, `README.md` | Cross-references are code spans (`` `docs/FILE_FORMAT.md` ``), never links. `lychee` finds no usable link in the existing Markdown: nothing is clickable on GitHub. | medium | Every reference in new and rewritten pages is a relative Markdown link; the index links every page. | fixed |
| C2 | repository | No images, so no broken ones. Screenshots added by this change are checked with the link checker. | low | — | fixed (images checked by the link checker) |
| C3 | `docs/demo/*.md` | Notes refer to each other and to docs only as code spans. | low | Linked from the docs index; text unchanged. | fixed (linked from the index) |

### D. Jargon

| # | File | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|---|
| D1 | `README.md`, guide, `docs/*` | Terms from space engineering (see B6) are used without a first-use explanation. The acronyms VCM, AIT, NCR and ICD do **not** occur in this repository (they belong to sibling tools); ECSS occurs only in the spec and the decisions. | high | Glossary, with every term linked at its first use in the new pages. | fixed |
| D2 | `docs/DECISIONS.md`, `docs/DEVIATIONS.md` | "D-0xx" and "DV-xx" identifiers are used everywhere without saying what they are. | low | Explained in the docs index and the glossary. | fixed |

### E. Duplicated or contradictory content

| # | Files | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|---|
| E1 | `README.md`, guide ch. 2, `docs/demo/*` | The same command list appears three times with slight differences (`other_revision`, `/tmp/demo` versus `demo`). | medium | One authoritative list in getting-started; README and manual link to it. | fixed |
| E2 | `docs/user-manual/` (new) and guide ch. 3 to 10 | The new task pages overlap with the in-app guide chapters. Two copies can drift. | medium | Manual pages are task-oriented and link to the in-app chapter for reference detail; `docs/developer/` says both must change together. | fixed (mitigated: developer docs say change both) |
| E3 | `docs/ARCHITECTURE.md`, `docs/FILE_FORMAT.md` | Both describe the project tree, with different content (A11). | medium | ARCHITECTURE points to FILE_FORMAT. | fixed |
| E4 | `docs/DEVIATIONS.md` | Two sets of IDs `DV-M1` to `DV-M3` (fixed earlier in D-099). | low | Verified no duplicates remain. | fixed |

### F. Findability (README → install → first result → manual → examples → troubleshooting in three clicks)

| # | Problem | Sev. | Planned fix | Status |
|---|---|---|---|---|
| F1 | Before: README → `docs/` folder listing (a flat list of 11 files with engineering names) → no path to a first result. | high | README "Where to go next" table; docs index grouped as Getting started / User guides / Reference / Examples / Developer docs. | fixed |
| F2 | There is no page that says what to expect after each step. | medium | Getting-started shows the real output of each command. | fixed |
| F3 | A newcomer who hits an error has nowhere to look. | medium | Troubleshooting and FAQ linked from the README and from the end of every guide. | fixed |

## What was checked

| Check | Result |
|---|---|
| Clean venv install (Python 3.13, Linux) | passes |
| Every command of the old README run in the clean venv | all run; `thermal` and `power-timeline` exit 1 by design; `compare` with `other_revision` fails (A2) |
| `system-budget-studio` without a display | fails with the xcb-cursor message (A5) |
| `budget validate` on a missing folder, an empty folder; `run` into an unwritable folder; unknown scenario; invalid option | each gives the plain message recorded in the troubleshooting page |
| `lychee --offline --include-fragments` on the old Markdown | 2 links found, both excluded: there were no links to check (C1) |
| Problem codes in the source versus FILE_FORMAT and guide ch. 11 | 2 missing (A15) |
| Claims in `ARCHITECTURE.md` checked against the code | 7 wrong (A7 to A11, A22) |
| **After the rewrite** | |
| Fresh `git clone` of the branch, new venv, `pip install -e .`, then every command of getting-started section 2 to 5 (`--version`, `self-test`, `export-examples`, `validate`, `run`, `power-timeline`, edit the limit, run again, `--smoke`) | all outputs match the text; the violation appears with exit code 1 and disappears with exit code 0 |
| Every command and output in `examples/README.md` and the user manual (scenario, thermal, link-passes, compare, guide, self-test) | run on the same venv; counts and messages quoted in the pages are the real ones |
| YAML snippets of the manual (unit, spacecraft mode, scenario rules and segments, mass limits) put into a copy of an example | validate with 0 errors; a unit missing from a mode gives `UNIT_NOT_MAPPED` as the page says |
| Offline wheelhouse recipe in getting-started | found that `pip install --no-index -e .` also needs `hatchling` and `editables`; recipe changed and re-run in a new venv: works |
| `lychee --offline --include-fragments` over README, CONTRIBUTING, CHANGELOG, `docs/**`, `examples/**` | 534 links, 529 OK, **0 errors**, 5 excluded (remote URLs are skipped in offline mode) |
| `lychee` online pass | 3 hosts could not be reached from the audit sandbox: `keepachangelog.com`, `img.shields.io` (no connection) and `github.com` web pages (403). They are ordinary public URLs; a reviewer should check that the two badges render |
| GFM table shape (columns per row) in every new or rewritten page | no mismatches |
| Pages open with a one-sentence purpose and end with `Next:` links; pages over two screens have a contents line | yes, for every page created or rewritten; `SPEC.md`, `LICENCES.md` (generated) and the milestone demo notes are left as they are |
| Screenshots | taken from the real window (Qt offscreen, Linux), viewed and checked for readability |
| GitHub rendering | not possible to view from the sandbox; only Markdown constructs GitHub supports are used (tables, anchors with `<a id>`, relative links, images) |

## Deferred

| Item | Why | Who |
|---|---|---|
| Windows commands of getting-started section 2 (A23) | No Windows machine here | A reviewer on Windows |
| UI text "Compute a scenario first (Ctrl+R)" (A20) | Application code, out of scope for a documentation PR | Owner: change the text or add the shortcut |
| *File → Export scenario results* does not exist (A21) | Feature gap in the GUI; `budget scenario` does the job | Owner: wire the existing method to a menu entry or drop it |
| Checking the two README badges and external links on GitHub | The sandbox cannot reach those hosts | Reviewer |
| Screenshots from Windows | Taken on Linux | Optional |

## Decisions needed from the owner

1. **Repository visibility.** The GitHub API reports the repository as **public**. `docs/SPEC.md` says to stop and ask in that case (project data may be export-controlled), and `docs/BRANCH_PROTECTION.md` lists making it private. The examples contain invented data only. This documentation PR does not change visibility.
2. **Licence.** The spec says "internal only; no LICENSE file". The README says so. If the repository is to stay public, a licence decision is needed.
3. **Integration with the other tools** (Harness Design Studio, Requirements Studio, AIT Logbook, ICD Studio). Only SpaceMissionStudio has an importer (an interim CSV format, D-055, waiting for real sample files). For the others, `docs/tips.md` describes only what exists today: the CSV, JSON and XLSX exports any tool can read. No import or export is documented that the code does not have. Say which exchanges you want built.
4. **Screenshots.** Generated from the real window with Qt's offscreen platform, on Linux. Replace them with screenshots from Windows if you prefer.
5. **Installers.** No release exists, so the documents say "from source" for now.

## Changes to the README (not a fork)

The README follows the non-fork layout. There is no upstream README, so there is no `docs/upstream/` copy and no BEGIN/END UPSTREAM markers.

Next: [Docs index](README.md) · [Getting started](getting-started.md).
