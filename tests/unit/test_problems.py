from budget_core.problems import Problem, Severity, sort_problems


def _p(code: str, file: str | None, line: int | None, sev: Severity = Severity.ERROR) -> Problem:
    return Problem(sev, code, "msg", file=file, path="a.b", line=line)


def test_sort_is_deterministic_and_by_file_then_line() -> None:
    items = [_p("B", "units/b.yaml", 3), _p("A", "units/a.yaml", 9), _p("C", "units/a.yaml", 2)]
    assert [p.code for p in sort_problems(items)] == ["C", "A", "B"]
    assert sort_problems(items) == sort_problems(list(reversed(items)))


def test_problems_without_file_sort_first() -> None:
    items = [_p("B", "x.yaml", 1), _p("A", None, None)]
    assert sort_problems(items)[0].code == "A"


def test_format_text_has_location_and_hint() -> None:
    p = Problem(
        Severity.ERROR,
        "FIELD_MISSING",
        "Required field 'x' is missing.",
        file="units/obc.yaml",
        path="modes[0]",
        line=7,
        hint="Add 'x'.",
    )
    text = p.format()
    assert text.startswith("units/obc.yaml:7: error FIELD_MISSING:")
    assert "modes[0]" in text and "Add 'x'." in text


def test_to_dict_is_json_ready() -> None:
    d = _p("A", "f.yaml", 1).to_dict()
    assert d == {
        "severity": "error",
        "code": "A",
        "message": "msg",
        "file": "f.yaml",
        "path": "a.b",
        "line": 1,
        "hint": "",
    }
