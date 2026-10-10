# Create a project

A project is a folder of plain-text YAML files that describe one spacecraft; this page shows how to start one and what the folder holds.

**Contents:** [With the wizard](#how-do-i-start-a-project-with-the-wizard) · [From an example](#how-do-i-start-a-project-from-an-example-on-the-command-line) · [The folder](#what-is-in-a-project-folder) · [Revisions](#how-do-i-keep-revisions)

## How do I start a project with the wizard?

1. Start the window: `system-budget-studio`.
2. Choose **File → New project (guided)** (Ctrl+N). Five short pages follow:
   1. **Project**: a name and the parent folder. The project goes into a new folder named after the project; an existing folder is never touched.
   2. **Spacecraft**: a sample to start from: a 3U CubeSat with complete example inputs, a 150 kg microsatellite with two links, or a 3U CubeSat with placeholder inputs.
   3. **Orbit**: altitude (160 to 2000 km), inclination and RAAN of a near-circular orbit.
   4. **Scenario**: how long to simulate (up to 30 days) and when it starts (UTC).
   5. **Review**: **Finish** creates the project, opens it and computes the first power timeline.

With the defaults you press **Next** four times and **Finish**. The result is a *sample* project with **invented** numbers (its description says so). Replace them with your own sourced numbers; the Problems panel lists what is still open.

## How do I start a project from an example on the command line?

There is no `new` command. Copy an example and edit it:

```bash
budget export-examples demo
cp -r demo/cubesat_3u my_satellite          # Windows: Copy-Item -Recurse demo\cubesat_3u my_satellite
```

Then open `my_satellite/project.yaml` and change `name`, `revision` and `description`, and replace the example units with yours ([Describe the spacecraft](describe-the-spacecraft.md)). Check as you go:

```bash
budget validate my_satellite
```

## What is in a project folder?

```text
project.yaml              name, revision, description
spacecraft.yaml           buses, mission phases, body frame
units/<id>.yaml           one file per unit: mass, bus, maturity, power modes, limits
modes/<id>.yaml           spacecraft modes: which power mode each unit is in
orbits/  ground_stations/  targets/  scenarios/
links/<id>.yaml           one file per radio link
expendables/<id>.yaml     consumables with a mass for every mission phase
config/                   margin policy, power system, thermal model, Eb/N0 and attenuation tables
results/                  written by the tool; not part of the project
```

Every file begins with `schema_version` and `kind`. Files are meant to be edited with any text editor and compared with ordinary tools: put the folder in git and you have a full history. Units, modes, links and scenarios are separate files so several people can work on different ones at the same time. The complete field list is the [project file format](../FILE_FORMAT.md); `budget export-schemas schemas` writes a JSON Schema for every kind, which many editors can use for completion.

Files written by an earlier version of the tool are upgraded in memory when loaded (you see the information message `FILE_MIGRATED`) and are written back in the new format only when you save them. A file from a *newer* version is refused with a clear message.

## How do I keep revisions?

`project.yaml` has a `revision` field. Increase it whenever you change numbers behind a report: it is printed on every output and used to label the sides of a [comparison](compare.md). Keep each revision as a git tag or a copy of the folder.

Next: [Describe the spacecraft](describe-the-spacecraft.md).
