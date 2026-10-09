"""Pure mass-property functions and their properties."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from budget_core.mass.mass_properties import (
    MassItem,
    Tensor,
    center_of_gravity,
    inertia_about,
    parallel_axis,
)
from budget_core.model import inertia_is_physical

coord = st.floats(min_value=-50, max_value=50, allow_nan=False)
mass = st.floats(min_value=0.1, max_value=500, allow_nan=False)
point = st.tuples(coord, coord, coord)
items = st.lists(st.tuples(mass, point), min_size=1, max_size=8)


def test_parallel_axis_of_a_sphere_like_body() -> None:
    t = parallel_axis(Tensor(0.5, 0.5, 0.5, 0, 0, 0), 2.0, (3.0, 0.0, 0.0))
    assert (t.ixx, t.iyy, t.izz) == (0.5, 18.5, 18.5)


def test_cog_of_nothing_is_none() -> None:
    assert center_of_gravity([]) is None
    assert center_of_gravity([(0.0, (1.0, 1.0, 1.0))]) is None


@given(items)
def test_cg_lies_inside_the_bounding_box(
    data: list[tuple[float, tuple[float, float, float]]],
) -> None:
    result = center_of_gravity(data)
    assert result is not None
    _, c = result
    for axis in range(3):
        values = [p[axis] for _, p in data]
        assert min(values) - 1e-9 <= c[axis] <= max(values) + 1e-9


@given(items, point)
def test_cg_translates_with_the_items(data, shift) -> None:  # type: ignore[no-untyped-def]
    moved = [(m, (p[0] + shift[0], p[1] + shift[1], p[2] + shift[2])) for m, p in data]
    a, b = center_of_gravity(data), center_of_gravity(moved)
    assert a is not None and b is not None
    for i in range(3):
        assert math.isclose(b[1][i], a[1][i] + shift[i], rel_tol=1e-9, abs_tol=1e-6)


@given(items)
def test_point_mass_inertia_is_physical_and_symmetric_by_construction(data) -> None:  # type: ignore[no-untyped-def]
    mass_items = [MassItem(m, p, None) for m, p in data]
    cg = center_of_gravity(data)
    assert cg is not None
    t = inertia_about(cg[1], mass_items)
    assert inertia_is_physical(t.ixx, t.iyy, t.izz, t.ixy, t.ixz, t.iyz)


@given(items, point)
def test_inertia_about_cg_is_invariant_under_translation(data, shift) -> None:  # type: ignore[no-untyped-def]
    def about_cg(d):  # type: ignore[no-untyped-def]
        cg = center_of_gravity(d)
        assert cg is not None
        return inertia_about(cg[1], [MassItem(m, p, None) for m, p in d])

    moved = [(m, (p[0] + shift[0], p[1] + shift[1], p[2] + shift[2])) for m, p in data]
    a, b = about_cg(data), about_cg(moved)
    for x, y in zip(
        (a.ixx, a.iyy, a.izz, a.ixy, a.ixz, a.iyz),
        (b.ixx, b.iyy, b.izz, b.ixy, b.ixz, b.iyz),
        strict=True,
    ):
        assert math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-4)


@given(items)
def test_adding_an_item_never_lowers_total_mass_or_trace(data) -> None:  # type: ignore[no-untyped-def]
    base = [MassItem(m, p, None) for m, p in data]
    more = [*base, MassItem(1.0, (0.0, 0.0, 0.0), None)]
    origin = (0.0, 0.0, 0.0)
    a, b = inertia_about(origin, base), inertia_about(origin, more)
    assert b.ixx + b.iyy + b.izz >= a.ixx + a.iyy + a.izz - 1e-9


@pytest.mark.parametrize(
    ("entries", "physical"),
    [
        ((1, 1, 1, 0, 0, 0), True),
        ((0.4, 0.4, 0.4, 0, 0, 0), True),
        ((1, 1, 3, 0, 0, 0), False),  # violates the triangle inequality
        ((1, 1, 1, 0.9, 0, 0), False),  # product too large for the diagonal
        ((0, 18, 18, 0, 0, 0), True),  # point mass on an axis
    ],
)
def test_inertia_physical_check(entries: tuple[float, ...], physical: bool) -> None:
    assert inertia_is_physical(*entries) is physical
