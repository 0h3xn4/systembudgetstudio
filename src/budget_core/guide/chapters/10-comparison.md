# Comparing revisions and scenarios

The comparison shows what changed between two sides:

- **two project revisions**: two project folders (for example a copy of last month's folder, or a checkout of an earlier revision);
- **two scenarios** of one project.

## In the window

Open the **Compare** tab. Side A is the open project (with an optional scenario). For side B enter or browse to another project folder, or leave it empty and choose a second scenario. **Compare** runs in the background and lists, budget by budget, every value that differs, with the change, the change in percent and a status:

| Status | Meaning |
|---|---|
| changed | the value is different |
| added / removed | a row exists on one side only |
| now computed | n/a before, a value now |
| now n/a | a value before, n/a now (an input became a placeholder) |

**Export** writes the comparison as XLSX, PDF, DOCX, CSV and JSON.

## On the command line

```
budget compare rev1 rev2 --out out
budget compare project --scenario-a one_day --scenario-b variant --out out
```

With two folders the static power, mass, thermal and link budgets are compared; give scenarios to also compare the power timeline and the link passes. Use `--budget` to limit the comparison and `--max-rows` to change how many differences are listed per budget.

## What counts as a difference

Values are compared as displayed in the reports. A change below the displayed precision is not reported. Rows are matched by their first column, so renaming a unit shows up as one removed and one added row. Differences beyond the list limit are counted and stated, never dropped silently.
