# Use the window

This page is a tour of the graphical window and a list of its shortcuts. Everything the window does can also be done with the [command line](command-line.md).

**Contents:** [Start it](#how-do-i-start-the-window) · [Layout](#what-is-where) · [Shortcuts](#shortcuts) · [Plots](#how-do-i-use-a-plot) · [Editing](#how-do-i-edit-a-file)

## How do I start the window?

```bash
system-budget-studio                       # then File → Open project
system-budget-studio path/to/project       # open a project at start
```

![The Power timeline tab: the project tree on the left, tabs for each budget, plots of generation, demand and state of charge with eclipses shaded, tables of results, and the Problems panel at the bottom](../images/power-timeline.png)

## What is where?

- **Project tree** (left): spacecraft, units, spacecraft modes, orbits, ground stations, imaging targets, scenarios, links and configuration files. Double-click a file to edit it as text; double-click a unit to edit its power modes in a table.
- **Tabs** (centre): **Power budget**, **Mass budget**, **Thermal budget**, **Link budget** (static tables, updated whenever the project changes), **Scenario**, **Power timeline**, **Link passes** (press **Compute**; they run in a background thread so the window stays responsive), and **Compare**.
- **Problems panel** (bottom): errors, warnings and open items. Double-click a row to jump to the file and line. The counts are also in the status bar.

If you edit a file and change the project, a timeline or link result computed from the older version is marked **stale** and cannot be exported until you compute again.

## Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New project (guided wizard) |
| Ctrl+O | Open project |
| Ctrl+S | Save the file you are editing |
| F5 | Reload the project from disk |
| Ctrl+M | Edit the selected unit's power modes in a table |
| Ctrl+E | Export reports of the static budgets |
| Ctrl+Shift+E | Export the power timeline |
| F1 | Open the user guide |

(On macOS the Ctrl key shortcuts are not tested.)

## How do I use a plot?

Hover to move a cursor with a readout of every series at that time. The mouse wheel zooms around the pointer, dragging pans, double-click shows everything. **A click pins a second cursor**: the readout then shows the differences between the two times. Escape or a right click removes it. The check box **Shade eclipses and passes** turns the shaded bands on and off.

## How do I edit a file?

Double-click it in the tree. It opens as text in a tab; **Ctrl+S** saves, and the project is checked again (the same checks as `budget validate`). Closing a modified tab, opening another project or quitting asks first, so you cannot lose edits by accident. A file that is not valid UTF-8 is refused instead of being damaged. In the **Scenario** tab, use the rule and segment buttons and **Save scenario**.

Next: [Command-line reference](command-line.md) · [Tips](../tips.md).
