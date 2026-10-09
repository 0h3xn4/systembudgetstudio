# M2b Static mass budget — demo note

```
budget export-examples demo
budget run demo/microsat_150kg --budget mass --out out --user "Your Name"
```

What you get per mission phase (launch, bol, eol in the microsat example): mass by unit, subsystem and in total with maturity and system margins, mass limits with ok / exceeded / n/a, centre of gravity, and the inertia tensor about the CG and about the frame origin. In the microsat example the adapter is present only at launch and the propellant mass falls from 9.0 kg to 0.8 kg, so the CG and inertia move between phases (launch: 152.6 kg, CG z = 0.457 m).

All margins and the launch mass limit are placeholders, so the margined columns show n/a and the report carries an INCOMPLETE banner. Geometry (positions, box inertias) is invented synthetic data, not a placeholder: it does not come from a standard.

An independent plain-Python recomputation straight from the YAML files agrees with the solver (total, CG, all six inertia entries) and is kept as a regression test.

GUI: a **Mass budget** tab next to the power tab, an Expendables group in the project tree, Problems for missing positions (`MASS_PROPS_MISSING`), unknown phases and exceeded limits; the unit editor keeps mass properties intact when it saves.

Tests: 345 (hand-calculated mass, CG, inertia and phase cases, Hypothesis properties on CG and inertia, migration of a v1 margin policy, golden mass reports for the three reference projects).

Open for the owner: confirm D-048 (body frame text and tensor-entry convention); supply mass margins and limits with sources; confirm D-043 (from M2a) if not yet done.
