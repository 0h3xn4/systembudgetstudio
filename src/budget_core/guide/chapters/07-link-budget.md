# Link budget

A link file describes one direction of one radio link: frequency, transmitter, receiver, modulation and coding, the data rates, the required margin, losses and the atmospheric attenuation entries it uses. A project can hold several links (telemetry, payload data, inter-satellite).

## Static table

For every *static point* (a chosen elevation and slant range) and every listed data rate the table shows EIRP, path loss, G/T, other losses, C/N0, Eb/N0 and the margin over the required Eb/N0 from `config/ebn0_table.yaml`, and the highest rate that closes with the required margin.

## Pass series

**Link passes > Compute** evaluates the link over every pass of the scenario for the link's ground station. The spacecraft antenna angle follows from the geometry (angle from nadir). For each time step the highest listed rate whose margin is at least the required margin is selected, which gives the data volume per pass and per day. A pass-by-pass table and a plot of the margin and the selected rate are shown; selecting a pass zooms the plot to it.

## Antennas

Use a constant `gain_dbi`, a `pattern` table (angle from nadir to gain, linear interpolation) or a `pattern_file` CSV with its `pattern_source`. A ground antenna must have a constant gain.

## What stays open

Transmit powers, gains, G/T, losses, required Eb/N0 and attenuation are your numbers; the examples contain invented values.
