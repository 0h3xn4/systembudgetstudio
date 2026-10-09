# M2a Static power budget — demo note

```
budget export-examples demo
budget run demo/microsat_150kg --out out --user "Your Name"     # XLSX, PDF, JSON, CSV
budget run demo/microsat_150kg --report pdf --date 2026-01-02T00:00:00Z --user X   # byte-identical on every run
system-budget-studio demo/microsat_150kg                         # the GUI
```

What you see: the power table for every spacecraft mode (effective power = average x duty cycle, unit margins by maturity class, system margin, converter and distribution losses, peak). All configuration numbers in the examples are placeholders on purpose, so margin and source columns show **n/a** and the report carries an INCOMPLETE banner. Put sourced values into `config/margin_policy.yaml` and `config/power_config.yaml` and the columns fill in.

GUI: project tree, Problems panel (double-click a problem to open the file at the offending line), budget tabs, unit table editor (right-click a unit, or Ctrl+M; "2500 mW" is accepted), Ctrl+S saves and recomputes, Ctrl+E exports in a background thread.

Tests: 248 (unit, regression with 17 hand-calculated power cases, Hypothesis properties, golden report content for the three reference projects, offline guard, GUI flows). Byte-identical regeneration is tested in-process, across processes with different hash seeds, and across seconds.

Open for the owner: D-043 (importing ReportLab's unused networking modules in the PDF path); margin policy and converter numbers (placeholders); M2b (mass) comes next.
