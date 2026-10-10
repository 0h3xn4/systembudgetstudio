# Quick start

## Guided mode: from an orbit to a first budget

Choose **File > New project (guided)** (Ctrl+N). Five short pages ask for:

1. **Project**: a name and the parent folder. The project is stored in a new folder named after the project; an existing folder is never touched.
2. **Spacecraft**: a sample spacecraft to start from (a 3U CubeSat with complete example inputs, a 150 kg microsatellite with two links, or a 3U CubeSat with placeholder inputs).
3. **Orbit**: altitude, inclination and RAAN of a near-circular orbit.
4. **Scenario**: how long to simulate and when it starts (UTC).
5. **Review**: Finish creates the project, opens it, and computes the first power timeline.

With the defaults you only press **Next** four times and **Finish**. The first power timeline appears in well under a minute. Everything in the new project is *sample data with invented numbers*; the project description says so. Replace the numbers with your own sourced values, and the Problems panel and the INCOMPLETE banners show what is still open.

## From the command line

```
budget export-examples demo
budget validate demo/cubesat_3u_eps
budget run demo/cubesat_3u_eps --out out
budget power-timeline demo/cubesat_3u_eps --out out
budget link-passes demo/microsat_150kg --out out
budget compare demo/cubesat_3u_eps other_revision --out out
budget guide --out guide
```

Every command that writes files accepts `--user` and `--date` so that you can regenerate a report byte for byte. Without them the user is `BUDGET_USER` or the login name, and the date is `SOURCE_DATE_EPOCH` or the clock.

## The window

- The **Project** tree lists spacecraft, units, modes, scenarios, links and configuration files. Double-click a file to edit it; double-click a unit to edit its power modes in a table.
- The tabs show the **Power**, **Mass**, **Thermal** and **Link** budgets, the **Scenario** timeline, the **Power timeline**, the **Link passes** and the **Compare** view.
- The **Problems** panel at the bottom lists errors, warnings and open items. Double-click a row to jump to the file and line.
- **File > Export reports** (Ctrl+E) writes the reports of all budgets to a folder you choose. Long computations run in a worker thread, so the window stays responsive.
