import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from budget_core.io.yamlio import YamlSyntaxError, dump_yaml, format_path, load_yaml_text


def test_load_returns_plain_python_and_lines() -> None:
    text = "schema_version: 1\nmodes:\n  - name: a\n    avg_power_w: 1.5\n  - name: b\n"
    loaded = load_yaml_text(text)
    assert loaded.data == {
        "schema_version": 1,
        "modes": [{"name": "a", "avg_power_w": 1.5}, {"name": "b"}],
    }
    assert type(loaded.data) is dict
    assert type(loaded.data["modes"]) is list
    assert loaded.lines.lookup(("schema_version",)) == 1
    assert loaded.lines.lookup(("modes", 0, "avg_power_w")) == 4
    assert loaded.lines.lookup(("modes", 1)) == 5


def test_lookup_falls_back_to_nearest_existing_ancestor() -> None:
    loaded = load_yaml_text("a:\n  b: 1\n")
    assert loaded.lines.lookup(("a", "missing")) == 2  # the existing parent key
    assert loaded.lines.lookup(("nothing", "here")) == 1  # falls back to the document start


def test_syntax_error_has_line_and_no_content() -> None:
    with pytest.raises(YamlSyntaxError) as exc:
        load_yaml_text("a: 1\nb: [unclosed SECRETVALUE\n")
    assert exc.value.line is not None
    assert "SECRETVALUE" not in str(exc.value)


def test_duplicate_keys_are_an_error_without_echoing_them() -> None:
    with pytest.raises(YamlSyntaxError) as exc:
        load_yaml_text("secretkey: 1\nsecretkey: 2\n")
    assert exc.value.line == 2
    assert "secretkey" not in str(exc.value)


def test_dump_is_canonical() -> None:
    data = {"schema_version": 1, "name": "x", "items": [{"a": 1.0, "b": None}], "z": {"k": "v"}}
    text = dump_yaml(data)
    assert text == ("schema_version: 1\nname: x\nitems:\n  - a: 1.0\n    b: null\nz:\n  k: v\n")
    assert dump_yaml(load_yaml_text(text).data) == text


def test_dump_keeps_insertion_order_and_lf() -> None:
    text = dump_yaml({"b": 1, "a": 2})
    assert text.splitlines() == ["b: 1", "a: 2"]
    assert "\r" not in text


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_float_round_trip_exact(x: float) -> None:
    back = load_yaml_text(dump_yaml({"v": x})).data["v"]
    assert back == x or (math.isclose(back, x, rel_tol=0) and back == x)


def test_format_path() -> None:
    assert format_path(("modes", 0, "avg_power_w")) == "modes[0].avg_power_w"
    assert format_path(()) == ""
    assert format_path(("assignments", "obc")) == "assignments.obc"
