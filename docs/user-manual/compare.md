# Compare

This page shows how to see exactly what changed between two project revisions, or between two scenarios of one project.

**Contents:** [Two revisions](#how-do-i-compare-two-revisions) · [Two scenarios](#how-do-i-compare-two-scenarios) · [In the window](#how-do-i-compare-in-the-window) · [How to read it](#how-do-i-read-the-comparison)

## How do I compare two revisions?

A revision is a project folder: a copy of last month's folder, or a checkout of an earlier git tag. Compare any two:

```bash
budget compare demo/cubesat_3u_eps demo/cubesat_3u --out out
```

```text
Static power budget: 218 value(s) differ out of 544 compared.
Mass budget: 0 value(s) differ out of 229 compared.
Thermal budget: 210 value(s) differ out of 602 compared.
Link budget: 53 value(s) differ out of 62 compared.
```

Side A is the first folder, side B the second. With two folders the **static** power, mass, thermal and link budgets are compared. It writes `compare.xlsx`, `.pdf`, `.docx`, `.json`, `compare_differences.csv` and a provenance file. Column labels name only what differs (`rev 1`, `rev 2`, or scenario names; `A` and `B` otherwise).

To compare your project with its previous revision, keep the old one next to it (for example `git worktree add ../old v1` or a copied folder) and run `budget compare my_satellite ../old`.

## How do I compare two scenarios?

```bash
budget compare my_satellite --scenario-a one_day --scenario-b variant --out out
```

Giving scenarios also compares the **power timeline** and the **link passes**. `--scenario x` uses the same scenario on both sides. `--budget power --budget link` limits what is compared; `--max-rows N` changes how many differences are listed per budget (default 200; the rest are counted and stated, never dropped silently).

## How do I compare in the window?

Open the **Compare** tab. Side A is the open project (with an optional scenario). For side B enter or browse to another project folder, or leave it empty and choose a second scenario. **Compare** runs in the background and lists, budget by budget, every value that differs. **Export…** writes the files above.

## How do I read the comparison?

Each difference has the row, the quantity, both values, the change, the change in percent and a status:

| Status | Meaning |
|---|---|
| `changed` | the value is different |
| `added` / `removed` | a row exists on one side only |
| `now computed` | n/a before, a value now |
| `now n/a` | a value before, n/a now (an input became a placeholder) |

Things to know:

- Values are compared **as displayed** in the reports: a change below the shown precision is not a difference. Two folders that differ only in `revision` show 0 differences.
- Rows are matched by their first column, so renaming a unit shows up as one removed and one added row.
- A percentage point change is shown for percent columns (`+10.0 pp`).
- The Problems, Provenance and Equations tables are not compared.

Next: [Read and fix problems](read-and-fix-problems.md).
