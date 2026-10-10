"""Problem codes that no other test reached: each has a message that names no project value."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.environment.elements import PropagationError
from budget_core.io.project_loader import load_project
from budget_core.link.evaluate import link_static_budget
from budget_core.scenario import run as scenario_run
from tests.link_helpers import downlink, link_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_a_failing_propagation_is_an_environment_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    project = load_project(EXAMPLES / "cubesat_3u_eps").project
    assert project is not None

    class Decayed:
        def compute(self, *args: object) -> None:
            raise PropagationError("the satellite decayed")

    monkeypatch.setattr(scenario_run, "environment_for", lambda *_: Decayed())
    with pytest.raises(scenario_run.ScenarioRunError) as caught:
        scenario_run.run_scenario(project, sorted(project.scenarios)[0])
    problem = caught.value.problem
    assert problem.code == "ENV_PROPAGATION_FAILED"
    assert problem.file is not None and problem.file.startswith("orbits/")
    assert problem.hint


def test_a_link_without_static_points_is_noted() -> None:
    link = downlink().model_copy(update={"static_points": []})
    result = link_static_budget(link_project(links={"dl": link}))
    (problem,) = [p for p in result.problems if p.code == "LINK_NO_STATIC_POINTS"]
    assert problem.file == "links/dl.yaml" and problem.path == "static_points"
    assert result.rows == ()
