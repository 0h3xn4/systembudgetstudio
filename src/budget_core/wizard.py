"""Guided mode, headless part: turns a few answers into a complete project folder.

The project is a copy of one of the synthetic sample spacecraft with the user's name, orbit and
scenario length. Every number of the sample stays invented (the project description says so); the
Problems panel and the INCOMPLETE banner keep showing what must still be replaced.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from budget_core.environment.constants import EARTH_RADIUS
from budget_core.examples import EXAMPLES
from budget_core.io.project_loader import write_project
from budget_core.model import Elements, Orbit, ProjectMeta

SAMPLES = {
    "cubesat_3u_eps": "3U CubeSat with complete example inputs (all results computed)",
    "microsat_150kg": "150 kg microsatellite with two links",
    "cubesat_3u": "3U CubeSat with placeholder inputs (results stay n/a until you fill them in)",
}
ECCENTRICITY_RATIO = 0.001  # near circular, as in the sample orbits
MAX_STEPS = 8640  # a longer scenario gets a coarser step so the first run stays quick
ALTITUDE_RANGE_KM = (160.0, 2000.0)
MAX_DAYS = 30.0


class WizardError(Exception):
    """A plain-language reason why the project could not be created."""


@dataclass(frozen=True)
class Issue:
    field: str
    message: str


@dataclass(frozen=True)
class WizardAnswers:
    project_name: str
    sample: str = "cubesat_3u_eps"
    altitude_km: float = 550.0
    inclination_deg: float = 97.6
    raan_deg: float = 100.0
    duration_days: float = 1.0
    start_utc: str = "2026-06-01T00:00:00Z"


def _start(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def check_answers(answers: WizardAnswers) -> list[Issue]:
    issues: list[Issue] = []
    if not answers.project_name.strip():
        issues.append(Issue("project_name", "Give the project a name."))
    if answers.sample not in SAMPLES:
        issues.append(Issue("sample", "Choose one of the sample spacecraft."))
    low, high = ALTITUDE_RANGE_KM
    if not low <= answers.altitude_km <= high:
        issues.append(
            Issue("altitude_km", f"The altitude must be between {low:g} and {high:g} km.")
        )
    if not 0.0 <= answers.inclination_deg <= 180.0:
        issues.append(
            Issue("inclination_deg", "The inclination must be between 0 and 180 degrees.")
        )
    if not 0.0 <= answers.raan_deg < 360.0:
        issues.append(Issue("raan_deg", "The RAAN must be at least 0 and less than 360 degrees."))
    if not 0.0 < answers.duration_days <= MAX_DAYS:
        issues.append(
            Issue(
                "duration_days",
                f"The scenario length must be above 0 and at most {MAX_DAYS:g} days.",
            )
        )
    if _start(answers.start_utc) is None:
        issues.append(
            Issue("start_utc", "The start must be a date and time such as 2026-06-01T00:00:00Z.")
        )
    return issues


def folder_name(project_name: str) -> str:
    """A safe folder name: ASCII letters and digits separated by single hyphens."""
    folded = unicodedata.normalize("NFKD", project_name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug or "project"


def create_project(answers: WizardAnswers, parent: Path) -> Path:
    """Write the project into `parent/<folder name>` and return that folder. An existing folder
    is never touched."""
    issues = check_answers(answers)
    if issues:
        raise WizardError(issues[0].message)
    folder = Path(parent) / folder_name(answers.project_name)
    if folder.exists():
        raise WizardError(
            f"The folder '{folder.name}' already exists. Choose another project name or folder."
        )
    start = _start(answers.start_utc)
    assert start is not None
    start_text = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    sample = EXAMPLES[answers.sample]()
    scenario_id = sorted(sample.scenarios)[0]
    scenario = sample.scenarios[scenario_id]
    orbit_id = scenario.orbit or sorted(sample.orbits)[0]
    orbit = Orbit(
        name=f"{answers.altitude_km:g} km, {answers.inclination_deg:g} deg inclination",
        elements=Elements(
            epoch_utc=start_text,
            semi_major_axis_m=EARTH_RADIUS.value + answers.altitude_km * 1000.0,
            eccentricity_ratio=ECCENTRICITY_RATIO,
            inclination_deg=answers.inclination_deg,
            raan_deg=answers.raan_deg,
            arg_perigee_deg=90.0,
            mean_anomaly_deg=0.0,
        ),
    )
    duration_s = answers.duration_days * 86400.0
    scenario = scenario.model_copy(
        update={
            "name": "First scenario (guided mode)",
            "orbit": orbit_id,
            "start_utc": start_text,
            "duration_s": duration_s,
            "step_s": max(scenario.step_s, float(math.ceil(duration_s / MAX_STEPS))),
        }
    )
    meta = ProjectMeta(
        name=answers.project_name.strip(),
        revision="1",
        description=f"Started in guided mode from the synthetic sample '{answers.sample}'. "
        "All numbers are invented placeholders; replace them with your own sourced values.",
    )
    project = replace(
        sample,
        root=folder,
        meta=meta,
        orbits={orbit_id: orbit},
        scenarios={scenario_id: scenario},
    )
    try:
        write_project(project, folder)
    except OSError as exc:
        raise WizardError(
            "The project could not be written. Check that the folder exists and that you may "
            "write to it."
        ) from exc
    return folder
