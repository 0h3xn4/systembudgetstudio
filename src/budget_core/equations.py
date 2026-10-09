"""Registry of every equation the tool uses, with its source (spec constraint 16).

An equation with `source=None` is flagged SOURCE_MISSING: the formula slot exists, but the text
to cite is not available yet. The "Equations and sources" chapter and the report assumptions list
are generated from this registry plus the configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_MISSING = "SOURCE_MISSING"


@dataclass(frozen=True)
class Equation:
    id: str
    name: str
    formula: str
    source: str | None
    notes: str = ""

    @property
    def source_text(self) -> str:
        return self.source or SOURCE_MISSING


_CONVENTION = (
    "Project convention (decision D-040). ECSS-E-ST-20C margin philosophy is the intended "
    "reference but its text is not available to the tool; owner to confirm."
)

EQUATIONS: dict[str, Equation] = {
    e.id: e
    for e in (
        Equation(
            "PWR-EFF",
            "Effective unit power",
            "P_eff = P_avg * duty_cycle_ratio",
            None,
            _CONVENTION,
        ),
        Equation(
            "PWR-MARGIN",
            "Unit power with maturity margin",
            "P_m = P_eff * (1 + margin_ratio(maturity))",
            None,
            _CONVENTION,
        ),
        Equation(
            "PWR-SYSMARGIN",
            "System margin on the sum of margined loads",
            "P_sys = (sum P_m) * (1 + system_margin_ratio)",
            None,
            _CONVENTION,
        ),
        Equation(
            "PWR-SOURCE",
            "Source power through converter and distribution",
            "P_source = P_load / (eta_converter(bus) * (1 - distribution_loss_ratio))",
            None,
            _CONVENTION,
        ),
        Equation(
            "PWR-PEAK",
            "Peak power",
            "P_peak = sum of unit peak_power_w (all units at peak at once, conservative)",
            None,
            _CONVENTION,
        ),
    )
}
