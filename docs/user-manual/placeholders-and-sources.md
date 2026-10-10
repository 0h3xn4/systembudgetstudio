# Placeholders and sources

This page explains why some results say *n/a*, why a report may start with an INCOMPLETE banner, and how to enter a number the way the tool wants it.

**Contents:** [The rule](#the-rule-the-tool-never-invents-a-number) · [Enter a sourced number](#how-do-i-enter-a-sourced-number) · [Find what is open](#how-do-i-find-what-is-still-open) · [Where the numbers live](#which-numbers-need-a-source)

## The rule: the tool never invents a number

Margins, efficiencies, degradation factors, flux values, required Eb/N0 and similar numbers decide whether a budget passes, so a plausible-looking default would be dangerous. The tool ships **none**. Instead every such number lives in a file under `config/` (or in a link, or a thermal file) written with a [`source`](../glossary.md#source). A number whose source is `TBD`, or that has no value, is a **[placeholder](../glossary.md#placeholder)**.

What a placeholder does:

- the project still loads, with the warning `CONFIG_PLACEHOLDER` (and `RESULT_INCOMPLETE` where a result needs it);
- every result that depends on it shows **n/a** (never a silent zero);
- the report starts with the [**INCOMPLETE**](../glossary.md#incomplete) banner: *"some inputs are placeholders (source TBD or missing) … Do not use this report as evidence until the placeholders are replaced with sourced values."*

## How do I enter a sourced number?

Write the number, and where it comes from:

```yaml
power_margin_ratio:
  value: 0.15
  source: "Programme margin policy, section 4"
  note: "optional free text"
```

- `value` is in the unit of the field name (`_ratio` is a plain number: 0.15 means 15 %; `50 %` is also accepted).
- `source` is free text: a document, a data sheet and page, a test report. It is printed next to the number in every report. Write something someone else could look up.
- To mark a number as not yet known, write `value: null` and `source: TBD`.

Do not copy a number from a standard unless you have the text and can cite it. The example projects use `Synthetic example value; not from a data sheet or a standard.` as their source, which is the honest description of invented numbers.

## How do I find what is still open?

- `budget validate <project>` lists every placeholder (`CONFIG_PLACEHOLDER`) and empty table (`CONFIG_EMPTY_TABLE`).
- Every report ends with a **Configuration numbers used** table: each number with its value, source and status (`sourced` or `PLACEHOLDER`).
- In the window, the **Problems** panel lists them; double-click to jump to the field.
- When no placeholder is left that a result needs, the INCOMPLETE banner disappears.

## Which numbers need a source?

| File | Numbers |
|---|---|
| `config/margin_policy.yaml` | power and mass margin per maturity class; system power and mass margin |
| `config/power_config.yaml` | converter efficiency per bus; distribution loss |
| `config/power_system.yaml` | solar array (irradiance, cell area and efficiency, temperatures, losses, degradation), battery (capacity, voltage, efficiencies, fade, initial charge, allowed depth of discharge per phase), peak power limit, design life |
| `config/mass_limits.yaml` | mass limits per phase |
| `config/thermal_model.yaml`, `config/thermal_environment.yaml` | conductances, emissivity and absorptivity, view ratios, solar flux, albedo, Earth infrared, required temperature margin |
| `config/ebn0_table.yaml`, `config/attenuation_table.yaml` | required Eb/N0 per modulation and coding; atmospheric and rain losses |
| `links/<id>.yaml` | RF power, line loss, antenna gain, G/T, required margin and other losses |

The user guide chapter *Equations and sources* lists every equation the tool uses and its source, or `SOURCE_MISSING` where the reference text is still to be attached ([how to build the guide](reports-and-exports.md#how-do-i-get-the-user-guide)). Treat results that rest on such an equation as engineering estimates until your team has confirmed it.

Next: [Power budget](power-budget.md).
