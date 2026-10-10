# Glossary

Every domain term, abbreviation and tool-specific word used in this repository's documents, in alphabetical order. Each entry is short; the manual page that uses the word is linked.

**Jump to:** [A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) · [H](#h) · [I](#i) · [L](#l) · [M](#m) · [N](#n) · [O](#o) · [P](#p) · [R](#r) · [S](#s) · [T](#t) · [U](#u) · [V](#v)

## A

<a id="aos-los"></a>
**AOS and LOS**: acquisition of signal and loss of signal: the start and end of a [pass](#pass).

<a id="attenuation"></a>
**Attenuation**: signal loss on the path through the atmosphere (gases, rain, clouds), in dB. It depends on the elevation. In this tool the values come from `config/attenuation_table.yaml`, each with a source, never from the tool itself. See [link budget](user-manual/link-budget.md).

**AIT**: assembly, integration and test: the phase in which the real hardware is built and verified. Not used by this tool; named in [tips](tips.md) because "AIT Logbook" is a sibling tool.

## B

<a id="bol-eol"></a>
**BOL and EOL**: beginning of life (new solar array and battery) and end of life (after the design life: the array has degraded and the battery lost capacity). The time-domain power budget computes both. See [power budget](user-manual/power-budget.md).

<a id="body-frame"></a>
**Body frame**: the coordinate axes fixed to the spacecraft, described once in words in `spacecraft.yaml`. Positions of units are given in it. The tool uses one right-handed frame per project.

<a id="bus"></a>
**Bus (power bus)**: a power supply line with a nominal voltage. Each unit names the bus it draws from, and each bus has a [converter efficiency](#converter-efficiency).

## C

<a id="cg"></a>
**Centre of gravity (CG)**: the mass-weighted average position of the spacecraft's parts. See [mass budget](user-manual/mass-budget.md).

<a id="cn0"></a>
**C/N0**: carrier-to-noise-density ratio, in dB-Hz: how strong the received signal is compared with the noise per hertz. It is the starting point of the [Eb/N0](#ebn0) calculation.

<a id="config-file"></a>
**Config file**: a file in a project's `config/` folder that holds numbers with a [source](#source): the margin policy, the power system, the thermal model, the Eb/N0 table, the attenuation table, the mass limits. The tool carries no such numbers itself.

<a id="converter-efficiency"></a>
**Converter efficiency and distribution loss**: the share of power lost in a bus's converters and in the cabling. Both come from `config/power_config.yaml`; the power needed *at the source* is higher than the power the units use.

<a id="shadow-model"></a>
**Cylindrical and conical shadow**: two models of the Earth's shadow. Cylindrical has a sharp edge (the satellite is either lit or in shadow); conical includes the soft [penumbra](#umbra-penumbra). Chosen per scenario (`shadow_model`).

## D

<a id="decision-ids"></a>
**D-0xx and DV-xx**: numbers in this repository's own records. A **D-** number is a design decision in [DECISIONS.md](DECISIONS.md) (what was decided and why); a **DV-** number is a physics simplification in [DEVIATIONS.md](DEVIATIONS.md). They are cited in the documents so you can find the reason for a behaviour.

<a id="dod"></a>
**Depth of discharge (DoD)**: how much of the battery's capacity is used: 1 minus the [state of charge](#soc). Batteries last longer if the depth of discharge stays below an allowed value, which differs per [mission phase](#mission-phase).

<a id="duty-cycle"></a>
**Duty cycle**: the share of time a unit is actually drawing its power in a mode (0 to 1). Effective average power = average power × duty cycle.

## E

<a id="ebn0"></a>
**Eb/N0**: energy per bit over noise density, in dB. A given modulation and coding needs a **required** Eb/N0 to decode reliably (from `config/ebn0_table.yaml`); the difference between what you have and what is required is the [link margin](#link-margin).

<a id="ecss"></a>
**ECSS**: European Cooperation for Space Standardization, the source of many space engineering standards (for example margin rules). The tool ships none of their numbers; where an equation should cite one, it is marked `SOURCE_MISSING` until the text is attached ([specification](SPEC.md)).

<a id="eclipse"></a>
**Eclipse**: the time the satellite is in the Earth's shadow, so the solar array produces nothing. The tool computes eclipses from the orbit.

<a id="eirp"></a>
**EIRP**: effective isotropic radiated power: transmit power, minus line loss, plus antenna gain, in dBW. How strong the transmitter looks, as if it radiated equally in all directions.

<a id="elevation"></a>
**Elevation**: the angle of the satellite above the horizon as seen from a ground station. Low elevation means a long path and more atmospheric loss.

<a id="expendable"></a>
**Expendable**: something whose mass changes during the mission, such as propellant or jettisoned equipment. It has a mass for every [mission phase](#mission-phase).

## F

<a id="file-kind"></a>
**`kind` and schema version**: the first two lines of every project file. `kind` says what the file is (`unit`, `link`…); the [schema version](#schema-version) says which version of the format it uses.

## G

<a id="gt"></a>
**G/T**: receiver figure of merit in dB/K: antenna gain minus the system noise temperature expressed in dB. A higher G/T means a more sensitive receiver.

<a id="golden-file"></a>
**Golden file**: a stored expected output used by tests: the test generates a report and compares it with the golden copy. For developers ([developer docs](developer/README.md)).

## H

<a id="heat-dissipation"></a>
**Heat dissipation ratio**: the share of a unit's electrical power that becomes heat inside it (1.0 unless the unit sends power out, for example as RF). See [thermal budget](user-manual/thermal-budget.md).

## I

<a id="icd"></a>
**ICD**: interface control document: the agreed description of an interface between two parts. Not used by this tool; named in [tips](tips.md) because "ICD Studio" is a sibling tool.

<a id="incomplete"></a>
**INCOMPLETE**: the banner at the top of a report when at least one input the results need is a [placeholder](#placeholder). It means: *do not use this report as evidence yet*.

<a id="inertia"></a>
**Inertia tensor**: how hard a body is to rotate about each axis. The tool combines the inertia of each unit about the spacecraft's centre of gravity with the parallel-axis theorem.

## L

<a id="link-margin"></a>
**Link margin**: the [Eb/N0](#ebn0) you have minus the Eb/N0 required, in dB. A link **closes** at a data rate when its margin is at least the **required margin** you set in the link file (a safety allowance). See [link budget](user-manual/link-budget.md).

## M

<a id="margin-policy"></a>
**Margin policy**: the rules that add safety allowance to numbers: a power and a mass margin per [maturity class](#maturity-class), and a system margin on top. Kept in `config/margin_policy.yaml`; the values are yours (placeholders until supplied).

<a id="maturity-class"></a>
**Maturity class**: how well a unit's numbers are known (for example a flight-proven unit versus a concept). Each class has its own margin in the [margin policy](#margin-policy); each unit names its class (`maturity`).

<a id="mission-phase"></a>
**Mission phase**: a stage of the mission, with a name you choose (launch, bol, eol…). Phases select the mass, the mass limit and the allowed [depth of discharge](#dod).

## N

<a id="na"></a>
**n/a**: "not available". A result the tool could not compute because an input is missing or a [placeholder](#placeholder). It is never shown as zero.

<a id="node"></a>
**Node (thermal)**: one lumped temperature in the thermal model, with conduction to other nodes and radiation to space. Units sit in nodes. See [thermal budget](user-manual/thermal-budget.md).

**NCR**: non-conformance report. Not used by this tool.

## O

<a id="orbit-balance"></a>
**Orbit balance**: energy generated minus energy demanded over one complete orbit. Negative means the battery drains a little more every orbit.

## P

<a id="pass"></a>
**Pass**: the time a satellite is above a ground station's minimum elevation, between [AOS and LOS](#aos-los). Data is sent during passes.

<a id="path-loss"></a>
**Path loss (free-space)**: how much the signal weakens just by spreading out over the distance, in dB; it grows with range and frequency.

<a id="peak-power"></a>
**Peak power**: the largest power a unit (or the sum of units) draws, as opposed to the average. The power system must be able to supply the peak.

<a id="placeholder"></a>
**Placeholder / TBD**: a number whose `source` is `TBD`, or with no value: the project owner has not supplied it yet. Results that need it show [n/a](#na) and the report is [INCOMPLETE](#incomplete). See [placeholders and sources](user-manual/placeholders-and-sources.md).

<a id="power-mode"></a>
**Power mode**: one operating state of a *unit* with its own average and peak power (off, nominal, downlink…). Not the same as a [spacecraft mode](#spacecraft-mode).

<a id="problem"></a>
**Problem**: a message with a code, a file and field, and a hint, at severity error, warning or info. A **finding** (or violation) is a problem produced by a computed result, such as a limit exceeded. See [read and fix problems](user-manual/read-and-fix-problems.md).

<a id="provenance"></a>
**Provenance**: the record of where an output came from: tool and library versions, project name and revision, scenario, generation time and user. Every report and CSV set carries it.

## R

<a id="raan"></a>
**RAAN**: right ascension of the ascending node, an angle that says where in inertial space the orbit plane crosses the equator going north. With inclination and altitude it fixes the orbit's orientation, and so when the satellite is in sunlight.

<a id="revision"></a>
**Revision**: the `revision` field of `project.yaml`: your label for a version of the project, printed on every output and used by [compare](user-manual/compare.md).

## S

<a id="sbom"></a>
**SBOM**: software bill of materials: a list of the libraries a build contains. Releases ship one in CycloneDX format.

<a id="scenario"></a>
**Scenario**: an orbit, a start time, a duration and a time step, plus rules for which spacecraft mode is active when. The time-domain budgets and the link passes run on a scenario. See [scenarios](user-manual/scenarios.md).

<a id="schema-version"></a>
**Schema version**: the version of a file's format. An older file is upgraded in memory (`FILE_MIGRATED`); a newer file is refused (`SCHEMA_TOO_NEW`).

<a id="sgp4"></a>
**SGP4**: the standard algorithm that turns a [TLE](#tle) or mean orbital elements into a satellite position. The tool uses the `sgp4` library.

<a id="soc"></a>
**State of charge (SoC)**: how full the battery is, as a share of its capacity.

<a id="source"></a>
**Source**: the `source` text next to every sourced number: where the number comes from (document, data sheet, test). Printed in the reports.

<a id="spacecraft-mode"></a>
**Spacecraft mode**: a state of the whole spacecraft (safe, nominal, imaging, downlink, charging) that says which [power mode](#power-mode) each unit is in. A scenario switches between them.

**SpaceMissionStudio**: a sibling tool that computes orbits, eclipses and passes. This tool can read its exported files (an interim format, see [scenarios](user-manual/scenarios.md#how-do-i-use-orbit-data-from-spacemissionstudio)).

<a id="static-budget"></a>
**Static budget**: a budget per mode without an orbit: the classic table for early design. Compare **time-domain budget**: over a scenario.

<a id="steady-state"></a>
**Steady state**: temperatures after everything has settled, with constant heat loads. The thermal model computes only this.

<a id="system-margin"></a>
**System margin**: the extra allowance applied to the whole sum, after each unit's own margin.

## T

<a id="tle"></a>
**TLE (two-line element set)**: a standard 2-line text description of a satellite's orbit, published for tracked objects and used with [SGP4](#sgp4).

## U

<a id="umbra-penumbra"></a>
**Umbra and penumbra**: the full shadow behind the Earth (umbra) and the partial shadow around it (penumbra), where only part of the Sun is blocked.

<a id="unit"></a>
**Unit**: one piece of equipment: an on-board computer, a radio, a camera. One file in `units/`, with mass, bus, maturity class and power modes. (Do not confuse it with a *measurement unit*, which is part of a field name: `power_w`.)

## V

<a id="violation"></a>
**Violation**: a computed result that breaks a limit, with a time stamp where it applies: for example `PEAK_POWER_EXCEEDED`. See [power budget](user-manual/power-budget.md#what-are-the-violations).

Next: [FAQ](faq.md) · [Tips](tips.md).
