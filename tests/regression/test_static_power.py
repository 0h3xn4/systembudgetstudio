"""Hand-calculated reference cases for the static power budget (decision D-040).

Conventions: effective = avg * duty; unit margin by maturity; system margin on the sum of margined
loads; source power = load / (eta_bus * (1 - distribution_loss)). Tolerance: relative 1e-12 (pure
double-precision arithmetic, no iteration).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.model import (
    Bus,
    MarginPolicy,
    MaturityClass,
    PowerConfig,
    PowerMode,
    Project,
    ProjectConfig,
    ProjectMeta,
    Sourced,
    Spacecraft,
    SpacecraftMode,
    Unit,
)
from budget_core.power.static_budget import (
    ModePowerResult,
    effective_power_w,
    source_power_w,
    static_power_budget,
    with_margin_w,
)

REL = 1e-12
SRC = "hand calculation"

# unit id -> (subsystem, bus, maturity, {mode: (avg_w, peak_w, duty)})
UnitSpec = tuple[str, str, str, dict[str, tuple[float, float, float]]]


def s(value: float | None, source: str = SRC) -> Sourced:
    return Sourced(value=value, source=source)


def project(
    units: dict[str, UnitSpec],
    margins: dict[str, float | None] | None = None,
    system: float | None = 0.0,
    eta: dict[str, float | None] | None = None,
    loss: float | None = 0.0,
    modes: tuple[str, ...] = ("nominal",),
) -> Project:
    buses = sorted({spec[1] for spec in units.values()})
    margins = margins if margins is not None else {"m1": 0.0, "m2": 0.0}
    eta = eta if eta is not None else {b: 1.0 for b in buses}
    unit_models = {
        uid: Unit(
            name=uid.upper(),
            subsystem=sub,
            mass_kg=1.0,
            bus=bus,
            maturity=mat,
            modes=[
                PowerMode(name=m, avg_power_w=a, peak_power_w=p, duty_cycle_ratio=d)
                for m, (a, p, d) in mm.items()
            ],
        )
        for uid, (sub, bus, mat, mm) in units.items()
    }

    def pick(uid: str, mode: str) -> str:
        names = [x.name for x in unit_models[uid].modes]
        return mode if mode in names else names[0]

    spacecraft_modes = {
        m: SpacecraftMode(name=m.capitalize(), assignments={uid: pick(uid, m) for uid in units})
        for m in modes
    }
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="t", revision="1"),
        spacecraft=Spacecraft(name="T", buses=[Bus(name=b, nominal_voltage_v=28.0) for b in buses]),
        units=unit_models,
        modes=spacecraft_modes,
        config=ProjectConfig(
            margin_policy=MarginPolicy(
                classes={k: MaturityClass(margin_ratio=s(v)) for k, v in margins.items()},
                system_margin_ratio=s(system),
            ),
            power_config=PowerConfig(
                distribution_loss_ratio=s(loss),
                converter_efficiency_ratio={b: s(e) for b, e in eta.items()},
            ),
        ),
    )


def mode_result(p: Project, mode: str = "nominal") -> ModePowerResult:
    result = static_power_budget(p)
    return next(m for m in result.modes if m.mode_id == mode)


def row(m: ModePowerResult, uid: str):  # type: ignore[no-untyped-def]
    return next(r for r in m.rows if r.unit_id == uid)


# ---- scalar helpers (cases 1-4) ------------------------------------------------------------


def test_case01_effective_power_is_avg_times_duty() -> None:
    assert effective_power_w(2.0, 0.5) == pytest.approx(1.0, rel=REL)
    assert effective_power_w(7.3, 0.0) == 0.0
    assert effective_power_w(7.3, 1.0) == pytest.approx(7.3, rel=REL)


def test_case02_margin_is_multiplicative() -> None:
    assert with_margin_w(10.0, 0.2) == pytest.approx(12.0, rel=REL)
    assert with_margin_w(10.0, 0.0) == pytest.approx(10.0, rel=REL)


def test_case03_source_power_divides_by_efficiency_and_distribution() -> None:
    assert source_power_w(9.0, 0.9, 0.0) == pytest.approx(10.0, rel=REL)
    assert source_power_w(9.0, 1.0, 0.1) == pytest.approx(10.0, rel=REL)  # 9 / 0.9
    assert source_power_w(5.0, 0.9, 0.02) == pytest.approx(5.0 / 0.882, rel=REL)


def test_case04_missing_inputs_give_none_not_zero() -> None:
    assert with_margin_w(10.0, None) is None
    assert source_power_w(9.0, None, 0.0) is None
    assert source_power_w(9.0, 0.9, None) is None


# ---- full chain (cases 5-9) ----------------------------------------------------------------

THREE = {
    "u1": ("A", "main", "m1", {"nominal": (2.0, 3.0, 0.5)}),
    "u2": ("B", "main", "m2", {"nominal": (4.0, 5.0, 1.0)}),
    "u3": ("A", "aux", "m1", {"nominal": (1.0, 1.5, 1.0)}),
}


@pytest.fixture
def three() -> ModePowerResult:
    return mode_result(
        project(
            THREE,
            margins={"m1": 0.10, "m2": 0.20},
            system=0.05,
            eta={"main": 0.9, "aux": 0.8},
            loss=0.02,
        )
    )


def test_case05_unit_rows(three: ModePowerResult) -> None:
    u1 = row(three, "u1")
    assert u1.effective_power_w == pytest.approx(1.0, rel=REL)
    assert u1.margin_ratio == 0.10
    assert u1.margined_power_w == pytest.approx(1.1, rel=REL)
    assert row(three, "u2").margined_power_w == pytest.approx(4.0 * 1.2, rel=REL)


def test_case06_totals_with_unit_and_system_margin(three: ModePowerResult) -> None:
    t = three.average
    assert t.load_w == pytest.approx(1.0 + 4.0 + 1.0, rel=REL)
    assert t.unit_margined_w == pytest.approx(1.1 + 4.8 + 1.1, rel=REL)
    assert t.system_margined_w == pytest.approx((1.1 + 4.8 + 1.1) * 1.05, rel=REL)


def test_case07_bus_source_power(three: ModePowerResult) -> None:
    main = next(b for b in three.buses if b.bus == "main")
    aux = next(b for b in three.buses if b.bus == "aux")
    assert main.average.load_w == pytest.approx(5.0, rel=REL)
    assert main.average.source_w == pytest.approx(5.0 / (0.9 * 0.98), rel=REL)
    assert main.average.source_margined_w == pytest.approx(
        (1.1 + 4.8) * 1.05 / (0.9 * 0.98), rel=REL
    )
    assert aux.average.source_w == pytest.approx(1.0 / (0.8 * 0.98), rel=REL)
    t = three.average
    assert t.source_w == pytest.approx(5.0 / (0.9 * 0.98) + 1.0 / (0.8 * 0.98), rel=REL)
    assert t.source_margined_w == pytest.approx(
        (1.1 + 4.8) * 1.05 / (0.9 * 0.98) + 1.1 * 1.05 / (0.8 * 0.98), rel=REL
    )


def test_case08_peak_is_sum_of_unit_peaks_with_same_chain(three: ModePowerResult) -> None:
    p = three.peak
    assert p.load_w == pytest.approx(3.0 + 5.0 + 1.5, rel=REL)
    assert p.system_margined_w == pytest.approx((3.3 + 6.0 + 1.65) * 1.05, rel=REL)
    assert p.source_margined_w == pytest.approx(
        (3.3 + 6.0) * 1.05 / (0.9 * 0.98) + 1.65 * 1.05 / (0.8 * 0.98), rel=REL
    )


def test_case09_subsystem_subtotals(three: ModePowerResult) -> None:
    a = next(x for x in three.subsystems if x.subsystem == "A")
    b = next(x for x in three.subsystems if x.subsystem == "B")
    assert a.effective_w == pytest.approx(1.0 + 1.0, rel=REL)
    assert a.margined_w == pytest.approx(1.1 + 1.1, rel=REL)
    assert b.peak_w == pytest.approx(5.0, rel=REL)
    assert [x.subsystem for x in three.subsystems] == ["A", "B"]


# ---- edge cases (cases 10-14) --------------------------------------------------------------


def test_case10_zero_duty_unit_contributes_nothing() -> None:
    m = mode_result(project({"u": ("A", "main", "m1", {"nominal": (50.0, 60.0, 0.0)})}))
    assert m.average.load_w == 0.0 and m.peak.load_w == 60.0  # peak ignores duty (D-040)


def test_case11_placeholder_margin_gives_none_but_nominal_is_computed() -> None:
    p = project(
        THREE,
        margins={"m1": None, "m2": 0.20},
        system=0.05,
        eta={"main": 0.9, "aux": 0.8},
        loss=0.02,
    )
    m = mode_result(p)
    assert row(m, "u1").margined_power_w is None
    assert row(m, "u2").margined_power_w == pytest.approx(4.8, rel=REL)
    assert m.average.load_w == pytest.approx(6.0, rel=REL)
    assert m.average.unit_margined_w is None and m.average.system_margined_w is None
    assert m.average.source_w == pytest.approx(5.0 / (0.9 * 0.98) + 1.0 / (0.8 * 0.98), rel=REL)


def test_case12_tbd_source_is_a_placeholder_even_with_a_value() -> None:
    p = project(THREE, margins={"m1": 0.1, "m2": 0.2}, system=0.05, loss=0.02)
    cfg = p.config.margin_policy
    assert cfg is not None
    tbd = MarginPolicy(
        classes={**cfg.classes, "m1": MaturityClass(margin_ratio=Sourced(value=0.1, source="TBD"))},
        system_margin_ratio=cfg.system_margin_ratio,
    )
    p2 = Project(
        p.root,
        p.meta,
        p.spacecraft,
        p.units,
        p.modes,
        ProjectConfig(margin_policy=tbd, power_config=p.config.power_config),
    )
    assert row(mode_result(p2), "u1").margin_ratio is None


def test_case13_missing_config_files_give_none_margins_and_sources() -> None:
    p = project(THREE)
    bare = Project(p.root, p.meta, p.spacecraft, p.units, p.modes, ProjectConfig())
    m = mode_result(bare)
    assert m.average.load_w == pytest.approx(6.0, rel=REL)
    assert m.average.system_margined_w is None and m.average.source_w is None


def test_case14_unit_off_in_a_mode() -> None:
    units = {
        "a": ("A", "main", "m1", {"nominal": (2.0, 2.0, 1.0), "off": (0.0, 0.0, 1.0)}),
        "b": ("A", "main", "m1", {"nominal": (3.0, 3.0, 1.0), "off": (0.0, 0.0, 1.0)}),
    }
    p = project(units, modes=("nominal", "off"))
    result = static_power_budget(p)
    by_id = {m.mode_id: m for m in result.modes}
    assert by_id["nominal"].average.load_w == pytest.approx(5.0, rel=REL)
    assert by_id["off"].average.load_w == 0.0


def test_case15_mode_order_follows_mode_ids_and_rows_follow_unit_ids() -> None:
    p = project(THREE, modes=("nominal", "alpha"))
    result = static_power_budget(p)
    assert [m.mode_id for m in result.modes] == ["alpha", "nominal"]
    assert [r.unit_id for r in result.modes[0].rows] == ["u1", "u2", "u3"]


def test_case16_missing_inputs_become_problems_not_zero() -> None:
    p = project(
        THREE,
        margins={"m1": None, "m2": 0.2},
        system=None,
        eta={"main": None, "aux": 0.8},
        loss=None,
    )
    codes = [(x.code, x.severity.value) for x in static_power_budget(p).problems]
    assert codes and {c for c, _ in codes} == {"RESULT_INCOMPLETE"}
    text = " ".join(x.message for x in static_power_budget(p).problems)
    for needle in ("m1", "system margin", "distribution", "main"):
        assert needle in text
    assert "m2" not in text and "aux" not in text  # only what is actually missing


def test_case17_result_is_deterministic() -> None:
    p = project(THREE, margins={"m1": 0.1, "m2": 0.2}, system=0.05, loss=0.02)
    assert static_power_budget(p) == static_power_budget(p)
