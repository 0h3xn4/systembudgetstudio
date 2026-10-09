"""Hand-calculated reference cases for the static mass budget, CG, inertia and phases.

Conventions (decisions D-048 to D-050): masses in kg, positions in m in one body frame, inertia
entries are tensor entries (Ixy = tensor element, i.e. minus the product of inertia). Margins:
item margin by maturity, then a system margin on the margined sum. CG and inertia use nominal
masses of items that have a position. Tolerance: relative 1e-12 (plain double arithmetic).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from budget_core.mass.static_mass import PhaseMass, StaticMassResult, static_mass_budget
from budget_core.model import (
    Bus,
    Expendable,
    Inertia,
    MarginPolicy,
    MassLimit,
    MassLimits,
    MassProperties,
    MaturityClass,
    PowerMode,
    Project,
    ProjectConfig,
    ProjectMeta,
    Sourced,
    Spacecraft,
    Unit,
)

REL = 1e-12
SRC = "hand calculation"
Vec = tuple[float, float, float]


def s(value: float | None, source: str = SRC) -> Sourced:
    return Sourced(value=value, source=source)


@dataclass
class U:
    mass: float
    subsystem: str = "A"
    maturity: str = "m1"
    pos: Vec | None = None
    inertia: tuple[float, float, float, float, float, float] | None = (
        None  # ixx iyy izz ixy ixz iyz
    )
    phases: list[str] | None = None


@dataclass
class E:
    masses: dict[str, float]
    pos: Vec | None = None
    maturity: str = "m1"
    subsystem: str = "PROP"


def props(pos: Vec | None, inertia: tuple[float, ...] | None) -> MassProperties | None:
    if pos is None:
        return None
    inert = None
    if inertia is not None:
        ixx, iyy, izz, ixy, ixz, iyz = inertia
        inert = Inertia(
            ixx_kgm2=ixx, iyy_kgm2=iyy, izz_kgm2=izz, ixy_kgm2=ixy, ixz_kgm2=ixz, iyz_kgm2=iyz
        )
    return MassProperties(position_m=list(pos), inertia=inert)


def project(
    units: dict[str, U],
    expendables: dict[str, E] | None = None,
    phases: list[str] | None = None,
    margins: dict[str, float | None] | None = None,
    system: float | None = 0.0,
    limits: list[tuple[str, str | None, float | None]] | None = None,
    config: bool = True,
) -> Project:
    margins = margins if margins is not None else {"m1": 0.0, "m2": 0.0}
    unit_models = {
        uid: Unit(
            name=uid.upper(),
            subsystem=u.subsystem,
            mass_kg=u.mass,
            bus="main",
            maturity=u.maturity,
            modes=[PowerMode(name="on", avg_power_w=1.0, peak_power_w=1.0)],
            mass_properties=props(u.pos, u.inertia),
            phases=u.phases,
        )
        for uid, u in units.items()
    }
    exp_models = {
        eid: Expendable(
            name=eid.upper(),
            subsystem=e.subsystem,
            maturity=e.maturity,
            masses_kg=e.masses,
            mass_properties=props(e.pos, None),
        )
        for eid, e in (expendables or {}).items()
    }
    cfg = (
        ProjectConfig(
            margin_policy=MarginPolicy(
                classes={
                    k: MaturityClass(power_margin_ratio=s(0.0), mass_margin_ratio=s(v))
                    for k, v in margins.items()
                },
                system_power_margin_ratio=s(0.0),
                system_mass_margin_ratio=s(system),
            ),
            mass_limits=MassLimits(
                limits=[MassLimit(name=n, phase=p, limit_kg=s(v)) for n, p, v in (limits or [])]
            ),
        )
        if config
        else ProjectConfig()
    )
    return Project(
        root=Path("."),
        meta=ProjectMeta(name="t", revision="1"),
        spacecraft=Spacecraft(
            name="T",
            buses=[Bus(name="main", nominal_voltage_v=28.0)],
            mission_phases=phases or [],
            body_frame="test frame",
        ),
        units=unit_models,
        modes={},
        config=cfg,
        expendables=exp_models,
    )


def phase(result: StaticMassResult, name: str = "all") -> PhaseMass:
    return next(p for p in result.phases if p.phase == name)


def tensor(p: PhaseMass, where: str = "cg") -> tuple[float, ...]:
    assert p.cog is not None
    t = p.cog.inertia_cg if where == "cg" else p.cog.inertia_origin
    return (t.ixx, t.iyy, t.izz, t.ixy, t.ixz, t.iyz)


def approx(*values: float) -> tuple[object, ...]:
    return tuple(pytest.approx(v, rel=REL, abs=1e-12) for v in values)


# ---- roll-up with margins (cases R1-R6) ----------------------------------------------------


def test_r1_rollup_with_unit_and_system_margin() -> None:
    p = phase(
        static_mass_budget(
            project(
                {"u1": U(2.0, maturity="m1"), "u2": U(3.0, maturity="m2")},
                margins={"m1": 0.10, "m2": 0.20},
                system=0.05,
            )
        )
    )
    assert p.total_kg == pytest.approx(5.0, rel=REL)
    assert p.unit_margined_kg == pytest.approx(2.2 + 3.6, rel=REL)
    assert p.system_margined_kg == pytest.approx((2.2 + 3.6) * 1.05, rel=REL)
    assert [r.margined_mass_kg for r in p.rows] == [pytest.approx(2.2), pytest.approx(3.6)]


def test_r2_subsystem_subtotals() -> None:
    p = phase(
        static_mass_budget(
            project(
                {"u1": U(2.0, "A"), "u2": U(3.0, "B"), "u3": U(1.5, "A")},
                margins={"m1": 0.10, "m2": 0.0},
            )
        )
    )
    a = next(x for x in p.subsystems if x.subsystem == "A")
    assert a.mass_kg == pytest.approx(3.5, rel=REL)
    assert a.margined_kg == pytest.approx(3.5 * 1.1, rel=REL)
    assert [x.subsystem for x in p.subsystems] == ["A", "B"]


def test_r3_placeholder_margin_gives_none_but_nominal_is_computed() -> None:
    p = phase(
        static_mass_budget(
            project(
                {"u1": U(2.0, maturity="m1"), "u2": U(3.0, maturity="m2")},
                margins={"m1": None, "m2": 0.2},
                system=0.05,
            )
        )
    )
    assert p.total_kg == pytest.approx(5.0, rel=REL)
    assert p.rows[0].margined_mass_kg is None and p.rows[1].margined_mass_kg == pytest.approx(3.6)
    assert p.unit_margined_kg is None and p.system_margined_kg is None


def test_r4_limits_exceeded_ok_and_not_available() -> None:
    result = static_mass_budget(
        project(
            {"u1": U(2.0, maturity="m1"), "u2": U(3.0, maturity="m2")},
            margins={"m1": 0.10, "m2": 0.20},
            system=0.05,
            limits=[("tight", None, 6.0), ("loose", None, 7.0), ("tbd", None, None)],
        )
    )
    by = {c.name: c for c in phase(result).limits}
    assert by["tight"].status == "exceeded" and by["tight"].margin_kg == pytest.approx(6.0 - 6.09)
    assert by["loose"].status == "ok" and by["loose"].margin_kg == pytest.approx(7.0 - 6.09)
    assert by["tbd"].status == "n/a" and by["tbd"].limit_kg is None
    assert any(
        p.code == "MASS_LIMIT_EXCEEDED" and p.severity.value == "error" for p in result.problems
    )


def test_r5_phase_specific_limits_only_apply_to_their_phase() -> None:
    result = static_mass_budget(
        project({"u1": U(2.0)}, phases=["launch", "eol"], limits=[("launch limit", "launch", 1.0)])
    )
    assert [c.name for c in phase(result, "launch").limits] == ["launch limit"]
    assert phase(result, "eol").limits == ()


def test_r6_limit_check_needs_the_system_margined_total() -> None:
    result = static_mass_budget(
        project({"u1": U(2.0)}, margins={"m1": None, "m2": None}, limits=[("l", None, 10.0)])
    )
    assert phase(result).limits[0].status == "n/a"


# ---- phases (cases P1-P6) ------------------------------------------------------------------


def test_p1_expendable_mass_changes_per_phase() -> None:
    result = static_mass_budget(
        project(
            {"u1": U(10.0)},
            {"fuel": E({"launch": 10.0, "bol": 6.0, "eol": 1.0})},
            phases=["launch", "bol", "eol"],
        )
    )
    assert [phase(result, n).total_kg for n in ("launch", "bol", "eol")] == [
        pytest.approx(20.0),
        pytest.approx(16.0),
        pytest.approx(11.0),
    ]


def test_p2_unit_present_only_in_listed_phases() -> None:
    result = static_mass_budget(
        project({"keep": U(10.0), "adapter": U(4.0, phases=["launch"])}, phases=["launch", "bol"])
    )
    assert phase(result, "launch").total_kg == pytest.approx(14.0)
    assert phase(result, "bol").total_kg == pytest.approx(10.0)
    assert [r.item_id for r in phase(result, "bol").rows] == ["keep"]


def test_p3_phase_order_follows_the_project_not_the_alphabet() -> None:
    result = static_mass_budget(project({"u": U(1.0)}, phases=["launch", "bol", "eol"]))
    assert [p.phase for p in result.phases] == ["launch", "bol", "eol"]


def test_p4_no_phases_means_one_phase_all() -> None:
    result = static_mass_budget(project({"u": U(1.0)}))
    assert [p.phase for p in result.phases] == ["all"]


def test_p5_expendable_uses_its_maturity_margin() -> None:
    result = static_mass_budget(
        project(
            {"u": U(10.0, maturity="m1")},
            {"fuel": E({"all": 5.0}, maturity="m2")},
            margins={"m1": 0.0, "m2": 0.5},
        )
    )
    p = phase(result)
    assert p.unit_margined_kg == pytest.approx(10.0 + 5.0 * 1.5)
    assert [r.kind for r in p.rows] == ["unit", "expendable"]


def test_p6_missing_config_gives_none_and_incomplete_problems() -> None:
    result = static_mass_budget(project({"u": U(10.0)}, config=False))
    p = phase(result)
    assert p.total_kg == 10.0 and p.system_margined_kg is None
    codes = {x.code for x in result.problems}
    assert "RESULT_INCOMPLETE" in codes and codes <= {"RESULT_INCOMPLETE", "MASS_PROPS_MISSING"}


# ---- centre of gravity (cases C1-C9) -------------------------------------------------------


def cog(units: dict[str, U], **kw):  # type: ignore[no-untyped-def]
    return phase(static_mass_budget(project(units, **kw))).cog


def test_c1_two_masses_on_an_axis() -> None:
    c = cog({"a": U(1.0, pos=(0, 0, 0)), "b": U(3.0, pos=(4, 0, 0))})
    assert c is not None and c.position_m == approx(3.0, 0.0, 0.0)


def test_c2_symmetric_masses_have_cg_at_the_origin() -> None:
    c = cog({"a": U(2.0, pos=(1, 0, 0)), "b": U(2.0, pos=(-1, 0, 0))})
    assert c is not None and c.position_m == approx(0.0, 0.0, 0.0)


def test_c3_three_unit_masses_on_the_axes() -> None:
    c = cog({"a": U(1.0, pos=(1, 0, 0)), "b": U(1.0, pos=(0, 1, 0)), "c": U(1.0, pos=(0, 0, 1))})
    assert c is not None and c.position_m == approx(1 / 3, 1 / 3, 1 / 3)


def test_c4_single_item() -> None:
    c = cog({"a": U(2.0, pos=(1, 2, 3))})
    assert c is not None and c.position_m == approx(1, 2, 3) and c.mass_kg == 2.0


def test_c5_item_without_position_is_excluded_and_reported() -> None:
    result = static_mass_budget(project({"a": U(2.0, pos=(1, 0, 0)), "b": U(2.0)}))
    c = phase(result).cog
    assert c is not None and c.position_m == approx(1.0, 0.0, 0.0)
    assert c.coverage_ratio == pytest.approx(0.5) and c.excluded_ids == ("b",)
    missing = [p for p in result.problems if p.code == "MASS_PROPS_MISSING"]
    assert len(missing) == 1 and missing[0].file == "units/b.yaml"


def test_c6_cg_uses_nominal_not_margined_masses() -> None:
    c = cog(
        {"a": U(1.0, maturity="m1", pos=(0, 0, 0)), "b": U(1.0, maturity="m2", pos=(2, 0, 0))},
        margins={"m1": 0.0, "m2": 0.5},
    )
    assert c is not None and c.position_m == approx(1.0, 0.0, 0.0)


def test_c7_propellant_moves_the_cg_between_phases() -> None:
    result = static_mass_budget(
        project(
            {"bus": U(10.0, pos=(0, 0, 0))},
            {"fuel": E({"launch": 10.0, "eol": 0.0}, pos=(0, 0, 2))},
            phases=["launch", "eol"],
        )
    )
    assert phase(result, "launch").cog.position_m == approx(0.0, 0.0, 1.0)  # type: ignore[union-attr]
    assert phase(result, "eol").cog.position_m == approx(0.0, 0.0, 0.0)  # type: ignore[union-attr]


def test_c8_no_positions_at_all_gives_no_cg() -> None:
    assert cog({"a": U(1.0), "b": U(2.0)}) is None


def test_c9_zero_mass_in_a_phase_gives_no_cg() -> None:
    result = static_mass_budget(
        project(
            {}, {"fuel": E({"launch": 5.0, "eol": 0.0}, pos=(0, 0, 1))}, phases=["launch", "eol"]
        )
    )
    assert phase(result, "eol").cog is None and phase(result, "launch").cog is not None


# ---- inertia (cases I1-I9) -----------------------------------------------------------------


def test_i1_point_mass_about_the_origin() -> None:
    p = phase(static_mass_budget(project({"a": U(2.0, pos=(3, 0, 0))})))
    assert tensor(p, "origin") == approx(0.0, 18.0, 18.0, 0.0, 0.0, 0.0)
    assert tensor(p, "cg") == approx(0, 0, 0, 0, 0, 0)  # the point is its own CG


def test_i2_off_axis_point_mass_has_a_product_term() -> None:
    p = phase(static_mass_budget(project({"a": U(1.0, pos=(1, 1, 0))})))
    assert tensor(p, "origin") == approx(1.0, 1.0, 2.0, -1.0, 0.0, 0.0)


def test_i3_two_equal_masses_about_their_cg() -> None:
    p = phase(
        static_mass_budget(project({"a": U(1.0, pos=(1, 0, 0)), "b": U(1.0, pos=(-1, 0, 0))}))
    )
    assert tensor(p, "cg") == approx(0.0, 2.0, 2.0, 0.0, 0.0, 0.0)


def test_i4_own_inertia_at_the_origin() -> None:
    p = phase(
        static_mass_budget(project({"a": U(2.0, pos=(0, 0, 0), inertia=(0.5, 0.5, 0.5, 0, 0, 0))}))
    )
    assert tensor(p, "origin") == approx(0.5, 0.5, 0.5, 0.0, 0.0, 0.0)


def test_i5_parallel_axis_theorem_with_own_inertia() -> None:
    p = phase(
        static_mass_budget(project({"a": U(2.0, pos=(3, 0, 0), inertia=(0.5, 0.5, 0.5, 0, 0, 0))}))
    )
    assert tensor(p, "origin") == approx(0.5, 18.5, 18.5, 0.0, 0.0, 0.0)
    assert tensor(p, "cg") == approx(0.5, 0.5, 0.5, 0.0, 0.0, 0.0)


def test_i6_two_masses_through_the_origin_in_a_general_direction() -> None:
    p = phase(
        static_mass_budget(project({"a": U(1.0, pos=(1, 2, 3)), "b": U(1.0, pos=(-1, -2, -3))}))
    )
    assert tensor(p, "cg") == approx(26.0, 20.0, 10.0, -4.0, -6.0, -12.0)


def test_i7_origin_inertia_equals_cg_inertia_plus_the_transfer_term() -> None:
    p = phase(static_mass_budget(project({"a": U(1.0, pos=(2, 0, 0)), "b": U(3.0, pos=(0, 4, 0))})))
    c = p.cog
    assert c is not None
    r, m = c.position_m, c.mass_kg
    d2 = sum(x * x for x in r)
    transfer = (
        m * (d2 - r[0] ** 2),
        m * (d2 - r[1] ** 2),
        m * (d2 - r[2] ** 2),
        -m * r[0] * r[1],
        -m * r[0] * r[2],
        -m * r[1] * r[2],
    )
    expected = tuple(a + b for a, b in zip(tensor(p, "cg"), transfer, strict=True))
    assert tensor(p, "origin") == approx(*expected)


def test_i8_trace_of_point_mass_inertia_is_twice_the_second_moment() -> None:
    p = phase(
        static_mass_budget(project({"a": U(1.0, pos=(1, 2, 3)), "b": U(1.0, pos=(-1, -2, -3))}))
    )
    t = tensor(p, "origin")
    assert t[0] + t[1] + t[2] == pytest.approx(2 * (14 + 14), rel=REL)


def test_i9_items_without_own_inertia_are_listed_as_point_masses() -> None:
    result = static_mass_budget(
        project(
            {
                "a": U(1.0, pos=(1, 0, 0), inertia=(0.1, 0.1, 0.1, 0, 0, 0)),
                "b": U(1.0, pos=(2, 0, 0)),
            }
        )
    )
    c = phase(result).cog
    assert c is not None and c.point_mass_ids == ("b",)
    assert any(
        p.code == "MASS_INERTIA_POINT_MASS" and p.severity.value == "info" for p in result.problems
    )


def test_i10_inertia_changes_with_the_phase() -> None:
    result = static_mass_budget(
        project(
            {"bus": U(10.0, pos=(0, 0, 0))},
            {"fuel": E({"launch": 4.0, "eol": 0.0}, pos=(1, 0, 0))},
            phases=["launch", "eol"],
        )
    )
    launch, eol = phase(result, "launch"), phase(result, "eol")
    assert launch.cog is not None and eol.cog is not None
    assert tensor(eol, "origin") == approx(0, 0, 0, 0, 0, 0)
    assert tensor(launch, "origin") == approx(0.0, 4.0, 4.0, 0.0, 0.0, 0.0)


def test_determinism() -> None:
    p = project({"a": U(1.0, pos=(1, 2, 3)), "b": U(2.0)}, {"f": E({"all": 1.0}, pos=(0, 0, 1))})
    assert static_mass_budget(p) == static_mass_budget(p)
