# Examples

This folder holds four complete example projects with **invented data**: none of the numbers describes a real spacecraft, and none comes from a standard or a data sheet. Use them to learn the tool and as templates for your own project.

**Contents:** [Getting a copy](#getting-a-copy) · [Which example for what](#which-example-for-what) · [cubesat_3u](#cubesat_3u-placeholders-everywhere) · [cubesat_3u_eps](#cubesat_3u_eps-complete-power-and-thermal-inputs) · [microsat_150kg](#microsat_150kg-two-links-and-phases) · [stress_200_units](#stress_200_units-a-week-at-one-second) · [Exit codes](#exit-codes-in-the-examples)

## Getting a copy

You can run the examples straight from this folder (`budget run examples/cubesat_3u_eps …`), but the tool writes its reports into `<project>/results` by default, so give `--out` or work on a copy:

```bash
budget export-examples demo      # writes demo/cubesat_3u, demo/cubesat_3u_eps, demo/microsat_150kg, demo/stress_200_units
```

The copy is identical to this folder. (A test fails if the two ever differ, so the examples cannot go out of date silently.) All commands below assume the copy in `demo/` and an output folder `out`; run them from the folder that contains `demo/`. Install first: [getting started](../docs/getting-started.md).

## Which example for what

| Example | Shows | Complete inputs for | Takes |
|---|---|---|---|
| [`cubesat_3u`](cubesat_3u) | A minimal 3U CubeSat; what a project with **placeholders** looks like: results that cannot be computed say *n/a* and the report is marked [INCOMPLETE](../docs/glossary.md#incomplete) | static power, mass; scenario | seconds |
| [`cubesat_3u_eps`](cubesat_3u_eps) | The same CubeSat with a complete (invented) solar array, battery and thermal model: the time-domain power budget, thermal budget and **findings** | power timeline, thermal | seconds |
| [`microsat_150kg`](microsat_150kg) | A 150 kg satellite with 17 units, propellant ([mass phases](../docs/glossary.md#mission-phase)) and **two links** (S-band and X-band downlinks), two ground stations and an imaging target | link budget, link passes, mass | seconds |
| [`stress_200_units`](stress_200_units) | 200 units and a **one-week scenario at 1 s** (604,801 steps): a performance and scale check | scenario, static budgets | about 10 s per run |

Every example leaves some numbers as [placeholders](../docs/glossary.md#placeholder) on purpose (the margin policy, the [Eb/N0](../docs/glossary.md#ebn0) table, mass limits and so on): the tool will not invent standards values, so each result that needs one shows *n/a* until you supply it with a source. Reports say so in an INCOMPLETE banner.

## cubesat_3u: placeholders everywhere

What to look at: how the tool behaves when inputs are missing.

```bash
budget validate demo/cubesat_3u
budget run demo/cubesat_3u --budget mass --out out
budget scenario demo/cubesat_3u --out out
```

Expected: `validate` ends with `0 errors, 82 warnings` (almost all are placeholders: the margin policy, the Eb/N0 table, mass limits, thermal and power numbers); `run` writes `out/mass_static.xlsx` and friends and prints

```text
INCOMPLETE: some inputs are placeholders (source TBD or missing). Entries marked n/a depend on them and are not computed. Do not use this report as evidence until the placeholders are replaced with sourced values.
```

`scenario` prints `Scenario one_day (elements): 15 eclipse(s); passes: gs_north 11, tgt_plains 1; 54 timeline segment(s).` and writes the eclipses, passes and mode timeline of one day as CSV and JSON. `budget power-timeline demo/cubesat_3u` prints `BOL: n/a (inputs missing, see the problems below).` because this project has no complete array and battery: use `cubesat_3u_eps` for that.

Try: open `demo/cubesat_3u/config/margin_policy.yaml`, replace one `TBD` with a number and a source, and run again; the *n/a* cells that depended on it fill in.

## cubesat_3u_eps: complete power and thermal inputs

What to look at: the time-domain power budget, the thermal budget, and how a **finding** looks. This is the example used in [getting started](../docs/getting-started.md#5-a-first-worked-example-find-and-fix-a-power-violation).

```bash
budget power-timeline demo/cubesat_3u_eps --out out
budget run demo/cubesat_3u_eps --budget thermal --out out
```

Expected from the first command (exit code 1, by design):

```text
BOL: generated 99.7 Wh, lowest state of charge 89.3 %, 0 violation(s).
EOL: generated 93.8 Wh, lowest state of charge 89.0 %, 0 violation(s).
config/power_system.yaml: error PEAK_POWER_EXCEEDED: The peak power demand at the source exceeds the power limit. 12 interval(s), the first at T+00:02:06. (at limits.peak_power_w)
```

Expected from the second (also exit code 1, by design):

```text
units/radio.yaml: error THERMAL_MARGIN_INSUFFICIENT: Unit 'radio' is within its operating limits but closer than the required temperature margin. (at temperature_limits)
```

The radio is inside its temperature limits but closer to one than the required margin. Raise `limits.peak_power_w` in `config/power_system.yaml` (or lower the radio's power) and the first finding goes; change the radio's `temperature_limits` or `temperature_margin_k` and the second goes. In the window, open the **Power timeline** and **Thermal budget** tabs.

## microsat_150kg: two links and phases

What to look at: link budgets, and a mass budget with three mission phases (launch, beginning of life, end of life) in which the propellant mass falls from 9.0 kg to 0.8 kg.

```bash
budget run demo/microsat_150kg --budget link --out out
budget link-passes demo/microsat_150kg --out out
budget run demo/microsat_150kg --budget mass --out out
```

Expected from `link-passes` (a Link passes report per scenario, XLSX/PDF/DOCX/JSON and CSV):

```text
sband_down: 11 pass(es) over gs_north, 4438.17 MByte in the scenario (4438.17 MByte per day).
xband_down: 4 pass(es) over gs_south, 2718.97 MByte in the scenario (2718.97 MByte per day).
0 errors, 0 warnings.
```

For each pass the report gives the lowest margin, the time with a rate that closes and the data volume, from the highest listed data rate whose margin meets the required margin at each step. `budget run … --budget link` writes the static table: EIRP, path loss, G/T, C/N0, Eb/N0 and margin per listed data rate at chosen elevations. In the window use the **Link budget** and **Link passes** tabs.

`budget power-timeline demo/microsat_150kg` prints `n/a` for BOL and EOL: this example's power system is a template. Use it to see how the mass budget handles phases (open `expendables/propellant.yaml`: an expendable gives its mass for **every** phase, writing `0.0` where it is gone).

## stress_200_units: a week at one second

What to look at: scale. 200 units, three sites, a seven-day scenario at 1 s.

```bash
budget scenario demo/stress_200_units --out out
```

Expected: `Scenario stress_week (elements): 106 eclipse(s); passes: gs_north 71, gs_south 28, tgt_plains 10; 240 timeline segment(s).` after roughly seven seconds. The environment (orbit, eclipses and passes over 604,801 steps) is the expensive part. With complete power inputs a week at 1 s with 200 units, including the power budget, is computed in about ten seconds on an ordinary laptop. This project's power system is a template, so `power-timeline` reports `n/a`; the timing is checked by the performance tests, not by this example.

## Exit codes in the examples

A command that finds an **error-level** problem exits with **1**, so scripts and CI notice. `cubesat_3u_eps` is built to show two such findings, so two commands above exit 1 even though they wrote all their files. `--strict` makes warnings count as failures too. Exit **0** means no errors; **2** means a command was called wrongly. See the [command-line reference](../docs/user-manual/command-line.md#exit-codes).

Next: the [user manual](../docs/user-manual/README.md) to build your own project, or the [glossary](../docs/glossary.md) for the terms used here.
