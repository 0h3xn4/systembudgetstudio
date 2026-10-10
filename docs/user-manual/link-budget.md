# Link budget

This page shows how to get the margin of a radio link at a chosen range and elevation, and the data volume you can send over every ground-station pass.

**Contents:** [Describe a link](#how-do-i-describe-a-link) · [Static table](#how-do-i-get-the-margin-at-a-chosen-range) · [Passes](#how-do-i-get-the-data-volume-over-the-passes) · [Antennas](#how-do-i-give-an-antenna-gain) · [Findings](#what-does-link_not_closed-mean)

## How do I describe a link?

One file per direction of one link: `links/<id>.yaml`. Cut down to the shape (the numbers are placeholders for yours, each with a source):

```yaml
schema_version: 1
kind: link
name: S-band telemetry downlink
direction: downlink              # or uplink
peer: gs_north                   # ground station id; leave out for static points only
frequency_hz: 2.2 GHz
transmitter:
  power_w: {value: 2.0, source: "…"}        # RF output power
  line_loss_db: {value: 1.0, source: "…"}
  antenna:
    gain_dbi: {value: 5.0, source: "…"}
  polarisation: RHCP
receiver:
  g_over_t_dbk: {value: 18.0, source: "…"}  # or: antenna + system_noise_temperature_k + feed_loss_db
modulation: QPSK                 # with coding: an entry of config/ebn0_table.yaml
coding: rate 1/2
data_rates_bps: [32000, 128000, 512000]
required_margin_db: {value: 3.0, source: "…"}
pointing_loss_db: {value: 0.5, source: "…"}
polarisation_loss_db: {value: 0.3, source: "…"}
implementation_loss_db: {value: 1.0, source: "…"}
attenuation: [gas_s]             # names in config/attenuation_table.yaml
active_modes: [downlink]         # spacecraft modes in which the link is used (empty: always)
static_points:
  - {name: 5 deg elevation, elevation_deg: 5, range_m: 2200000}
```

The required [Eb/N0](../glossary.md#ebn0) comes from `config/ebn0_table.yaml` (an entry with the same modulation and coding); losses by name from `config/attenuation_table.yaml`. A project can hold several links (telemetry, payload data, inter-satellite), uplink and downlink. Every field is in the [file format](../FILE_FORMAT.md#links-decisions-d-077-to-d-083).

## How do I get the margin at a chosen range?

```bash
budget run my_satellite --budget link --out out
```

For each **static point** (an [elevation](../glossary.md#elevation) and slant range you choose) and each listed data rate the table shows [EIRP](../glossary.md#eirp), [path loss](../glossary.md#path-loss), [G/T](../glossary.md#gt), other losses, [C/N0](../glossary.md#cn0), Eb/N0 and the [**margin**](../glossary.md#link-margin) over the required Eb/N0, and the highest rate that closes with the required margin. In the window: the **Link budget** tab.

## How do I get the data volume over the passes?

```bash
budget link-passes my_satellite --out out
```

This needs a [scenario](scenarios.md) that lists the link's ground station under `sites`. For every pass the tool evaluates the link at each time step (the spacecraft antenna angle follows from the geometry, measured from nadir) and selects the **highest listed rate whose margin meets the required margin**. That gives the margin, the time with a usable rate and the data volume per pass, per scenario and per day:

```text
sband_down: 11 pass(es) over gs_north, 4438.17 MByte in the scenario (4438.17 MByte per day).
```

A sample counts for the part of its step that lies inside the pass and, if you set `active_modes`, for the time its part of the pass overlaps those spacecraft modes. Not modelled: hysteresis, protocol overhead, acquisition time. In the window: the **Link passes** tab (select a pass to zoom the plot to it).

## How do I give an antenna gain?

Use exactly one of: a constant `gain_dbi`; a `pattern` table (angles from nadir and gains, linearly interpolated, ends held); or a `pattern_file` CSV with columns `angle_deg,gain_dbi` and a `pattern_source`. The file must lie inside the project folder. A ground antenna must have a constant gain (it tracks).

## What does LINK_NOT_CLOSED mean?

No listed data rate meets the required margin at any static point, or at any active sample of the passes. Lower the data rates, raise the transmit power or gain, or check the losses and the required margin. `n/a` instead of numbers means an input (power, gain, Eb/N0 entry…) is still a [placeholder](placeholders-and-sources.md).

Next: [Scenarios](scenarios.md).
