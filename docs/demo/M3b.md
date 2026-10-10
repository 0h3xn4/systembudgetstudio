# M3b Scenario view and timeline editor — demo note

```
budget export-examples demo
system-budget-studio demo/microsat_150kg      # then open the Scenario tab and press the Compute button
```

What you see: a timeline with a Sunlight row (eclipse in grey, umbra in black when the conical shadow is chosen), one row per ground station or target with its passes, and the Mode row built from the scenario's layers. Mouse wheel zooms around the pointer, drag pans, double-click shows the whole scenario, hovering shows the time, mode, eclipse state and the passes at that moment, and **Shift+drag adds a manual segment**.

Editing: change the default mode, shadow model, sites, rules (kind, site, mode, lead, lag) and manual segments in the editor next to the timeline. Invalid edits are explained in plain words and nothing is written; Save writes the scenario file. Rule and segment edits rebuild the timeline at once from the existing environment; changing the orbit, a site, the times or the step marks the results stale until you press Compute. Eclipses, passes and the mode timeline are also listed in tables, and `budget scenario` writes the same files (the window has no menu entry for exporting them; `File > Export scenario results` was planned but is not wired up).

Tests: 36 new (core environment key and timeline rebuild, timeline widget zoom/pan/hover/selection/painting, scenario view compute in a worker, edits, stale detection, plain-language failures, export, unsaved-edit prompt).

Open for the owner: SpaceMissionStudio sample files; confirm D-054 and D-059 (see M3a). Next is M4, the time-domain power budget.
