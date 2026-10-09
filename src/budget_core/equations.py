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


_TD_NOTE = (
    "Textbook relation, project convention (decision D-061); the reference text is not "
    "available to the tool, owner to confirm (for example the power chapter of a spacecraft "
    "systems engineering handbook)."
)


def _time_domain_equations() -> tuple[Equation, ...]:
    return (
        Equation(
            "TDP-ARRAY",
            "Array output power per step",
            "P_gen = E * (sum_faces N_cells * max(0, cos theta)) * A_cell * eta_ref * k_T "
            "* (1 - l_pack) * (1 - l_harness) * k_age * f_lit",
            None,
            _TD_NOTE + " Constant irradiance E, no albedo (DEVIATIONS DV-P4).",
        ),
        Equation(
            "TDP-TEMP",
            "Cell efficiency at the operating temperature",
            "k_T = max(0, 1 + alpha * (T_cell - T_ref))",
            None,
            _TD_NOTE,
        ),
        Equation(
            "TDP-AGE",
            "Array degradation over life",
            "k_age = (1 - annual_degradation_ratio) ^ years",
            None,
            _TD_NOTE,
        ),
        Equation(
            "TDP-COS",
            "Sun incidence on a face",
            "cos theta = n_face . s_body (unit vectors), zero on the back side",
            None,
            "Geometry. The Sun direction in the body frame follows the pointing of the mode "
            "(decision D-064).",
        ),
        Equation(
            "TDP-LIT",
            "Sunlit share of a step",
            "f_lit = 1 - (eclipse time inside the step) / step; trapezoid of the shadow ratio for "
            "a soft shadow",
            None,
            "Exact overlap of the eclipse intervals with the step (decision D-063).",
        ),
        Equation(
            "TDP-DEMAND",
            "Demand per step",
            "P_dem = sum over modes of overlap(mode segment, step) * P_source(mode) / step",
            None,
            "Source power per mode from the static budget (PWR-SOURCE, PWR-MARGIN).",
        ),
        Equation(
            "TDP-CAP",
            "Battery capacity",
            "E_cap = C_cell * V_cell * N_series * N_parallel * (1 - annual_capacity_fade_ratio) "
            "^ years",
            None,
            _TD_NOTE,
        ),
        Equation(
            "TDP-SOC",
            "Battery state of charge",
            "surplus: E += eta_c * min(P*dt, (E_cap - E) / eta_c); deficit: E -= min(P*dt, E * "
            "eta_d) / eta_d (P = generation - demand)",
            None,
            _TD_NOTE + " Energy model without voltage, current limit or temperature (DV-P4).",
        ),
        Equation(
            "TDP-DOD",
            "Depth of discharge",
            "DoD = 1 - E / E_cap; violation when DoD > allowed depth of discharge of the phase",
            None,
            "Definition; the allowed values come from configuration.",
        ),
        Equation(
            "TDP-BALANCE",
            "Orbit energy balance",
            "balance = integral(P_gen - P_dem) dt over one revolution; negative is a violation",
            None,
            "Revolutions are found from the position vectors (decision D-065).",
        ),
        Equation(
            "TDP-PEAK",
            "Peak power at the source",
            "P_peak,source = sum of unit peaks through converter and distribution losses; "
            "violation when above the power limit during the mode",
            None,
            _TD_NOTE,
        ),
    )


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
        Equation(
            "MASS-MARGIN",
            "Item mass with maturity margin",
            "m_m = m * (1 + mass_margin_ratio(maturity))",
            None,
            _CONVENTION,
        ),
        Equation(
            "MASS-SYSMARGIN",
            "System mass margin on the margined total",
            "m_sys = (sum m_m) * (1 + system_mass_margin_ratio)",
            None,
            _CONVENTION,
        ),
        Equation(
            "MASS-COG",
            "Centre of gravity",
            "r_cg = sum(m_i r_i) / sum(m_i), nominal masses of items with a position",
            None,
            "Classical mechanics (definition); no standards text cited. Margin mass has no "
            "position (DEVIATIONS DV-M1).",
        ),
        Equation(
            "ENV-SUN",
            "Sun direction and distance (low precision)",
            "lambda = L + 1.915 sin g + 0.020 sin 2g; unit vector (cos lambda, cos eps sin lambda, "
            "sin eps sin lambda); R = 1.00014 - 0.01671 cos g - 0.00014 cos 2g (AU)",
            None,
            "Astronomical Almanac low-precision Sun, reproduced from memory (text not available); "
            "checked against the published 2000 equinox and solstice instants in the tests "
            "(about 0.01 degree). Owner to verify against the Almanac.",
        ),
        Equation(
            "ENV-GMST",
            "Greenwich mean sidereal time (IAU-82)",
            "theta = 67310.54841 + (876600 h + 8640184.812866) T + 0.093104 T^2 - 6.2e-6 T^3 s",
            "sgp4 library, sgp4.propagation.gstime (IAU-82 GMST, Vallado)",
            "Checked against the library function in the tests.",
        ),
        Equation(
            "ENV-SHADOW-CYL",
            "Cylindrical Earth shadow",
            "in shadow when r.s < 0 and |r - (r.s) s| < R_Earth (s: unit vector to the Sun)",
            None,
            "Textbook geometry; no standards text cited.",
        ),
        Equation(
            "ENV-SHADOW-CON",
            "Conical Earth shadow (umbra, penumbra, annular)",
            "apparent disk radii a (Sun), b (Earth), separation c; visible Sun fraction from the "
            "overlap area of two discs",
            None,
            "Montenbruck and Gill, Satellite Orbits, 3.4.2, reproduced from memory (text not "
            "available); checked by geometric tests (umbra, monotonic penumbra, annular limit).",
        ),
        Equation(
            "ENV-GEODETIC",
            "WGS-84 geodetic to Earth-fixed coordinates",
            "N = a / sqrt(1 - e2 sin2 phi); x = (N + h) cos phi cos lam; "
            "z = (N (1 - e2) + h) sin phi",
            "WGS 84 (NIMA TR8350.2) ellipsoid definition",
            "Constants in budget_core.environment.constants (decision D-054).",
        ),
        Equation(
            "ENV-TOPO",
            "Elevation, azimuth and range from a site",
            "local east-north-up basis at the geodetic latitude and longitude of the site",
            None,
            "Textbook geometry; no refraction (DEVIATIONS DV-E1).",
        ),
        Equation(
            "MASS-PARALLEL",
            "Parallel-axis (Huygens-Steiner) theorem",
            "I = sum(I_i + m_i (|d_i|^2 E - d_i d_i^T)), d_i = r_i - r_ref",
            None,
            "Classical rigid-body mechanics; tensor entries convention in DECISIONS D-048.",
        ),
        *_time_domain_equations(),
    )
}
