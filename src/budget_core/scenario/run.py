"""Run a scenario: compute its environment and mode timeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from budget_core.environment.data import (
    Environment,
    EnvironmentData,
    PropagationError,
    SiteDef,
    TimeGrid,
)
from budget_core.environment.elements import ElementsPropagator
from budget_core.environment.spacemissionstudio import (
    EnvironmentInputError,
    SpaceMissionStudioImport,
)
from budget_core.io.project_loader import model_to_data
from budget_core.model import Project, Scenario
from budget_core.problems import Problem, Severity
from budget_core.scenario.timeline import TimelineSegment, build_timeline
from budget_core.timeutil import parse_utc


class ScenarioRunError(Exception):
    """A scenario cannot be run; `problem` explains why in plain words."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.message)
        self.problem = problem


@dataclass(frozen=True, eq=False)
class ScenarioRun:
    scenario_id: str
    scenario: Scenario
    env: EnvironmentData
    timeline: tuple[TimelineSegment, ...]
    notes: tuple[str, ...]


def grid_for(scenario: Scenario) -> TimeGrid:
    return TimeGrid(parse_utc(scenario.start_utc), scenario.duration_s, scenario.step_s)


def sites_for(project: Project, scenario: Scenario) -> list[SiteDef]:
    out: list[SiteDef] = []
    for site_id in scenario.sites:
        if site_id in project.ground_stations:
            g = project.ground_stations[site_id]
            out.append(
                SiteDef(
                    site_id,
                    "ground_station",
                    g.latitude_deg,
                    g.longitude_deg,
                    g.altitude_m,
                    g.min_elevation_deg,
                )
            )
        else:
            t = project.targets[site_id]
            out.append(
                SiteDef(
                    site_id,
                    "target",
                    t.latitude_deg,
                    t.longitude_deg,
                    t.altitude_m,
                    t.min_elevation_deg,
                )
            )
    return out


def environment_for(project: Project, scenario: Scenario) -> Environment:
    if scenario.environment_source == "spacemissionstudio":
        assert scenario.import_dir is not None
        return SpaceMissionStudioImport(project.root / scenario.import_dir)
    assert scenario.orbit is not None
    return ElementsPropagator(project.orbits[scenario.orbit])


def run_scenario(project: Project, scenario_id: str) -> ScenarioRun:
    """Compute the environment and the mode timeline. The project must be valid."""
    if scenario_id not in project.scenarios:
        known = ", ".join(sorted(project.scenarios)) or "none"
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "SCENARIO_UNKNOWN",
                f"Scenario '{scenario_id}' does not exist.",
                hint=f"Defined scenarios: {known}.",
            )
        )
    scenario = project.scenarios[scenario_id]
    adapter = environment_for(project, scenario)
    try:
        env = adapter.compute(
            grid_for(scenario), sites_for(project, scenario), scenario.shadow_model
        )
    except EnvironmentInputError as exc:
        base = scenario.import_dir or ""
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "ENV_INPUT_INVALID",
                f"{exc}.",
                file=f"{base}/{exc.file}",
                line=exc.line,
                hint="See docs/ENVIRONMENT_FORMAT.md for the expected files.",
            )
        ) from None
    except PropagationError as exc:
        raise ScenarioRunError(
            Problem(
                Severity.ERROR,
                "ENV_PROPAGATION_FAILED",
                f"{exc}.",
                file=f"orbits/{scenario.orbit}.yaml",
                hint="Check the orbit; very low or very eccentric orbits decay.",
            )
        ) from None
    notes = tuple(getattr(adapter, "notes", ()))
    return ScenarioRun(scenario_id, scenario, env, build_timeline(scenario, env), notes)


def environment_key(project: Project, scenario: Scenario) -> str:
    """Fingerprint of everything the environment depends on. Rules, segments, the default mode
    and the name only change the timeline, so they are not part of it. Equal keys allow reusing a
    computed environment."""
    parts: dict[str, object] = {
        "source": scenario.environment_source,
        "start_utc": scenario.start_utc,
        "duration_s": scenario.duration_s,
        "step_s": scenario.step_s,
        "shadow_model": scenario.shadow_model,
        "sites": [
            [site_id, model_to_data((project.ground_stations | project.targets)[site_id])]
            for site_id in scenario.sites
            if site_id in project.ground_stations or site_id in project.targets
        ],
    }
    if scenario.environment_source == "elements" and scenario.orbit in project.orbits:
        parts["orbit"] = model_to_data(project.orbits[scenario.orbit])
    if scenario.environment_source == "spacemissionstudio" and scenario.import_dir:
        folder = project.root / scenario.import_dir
        files = sorted(folder.glob("*.csv")) if folder.is_dir() else []
        parts["import"] = [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in files]
    text = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rebuild_timeline(run: ScenarioRun, scenario: Scenario) -> ScenarioRun:
    """The same environment with the timeline of an edited scenario (rules, segments, default)."""
    return ScenarioRun(
        run.scenario_id, scenario, run.env, build_timeline(scenario, run.env), run.notes
    )
