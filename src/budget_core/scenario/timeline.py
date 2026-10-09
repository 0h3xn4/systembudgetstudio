"""Mode timeline of a scenario (decision D-056).

Layers, later wins: the default mode over the whole scenario, then each rule in the order listed,
then the hand-built segments. Segments are half-open [start, end).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from budget_core.environment.data import EnvironmentData
from budget_core.model import Scenario

NDArray = np.ndarray[Any, np.dtype[Any]]
EPS = 1e-9


@dataclass(frozen=True)
class TimelineSegment:
    start_s: float
    end_s: float
    mode: str

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def _paint(
    segments: list[TimelineSegment], start: float, end: float, mode: str, limit: float
) -> list[TimelineSegment]:
    """Overwrite [start, end) (clipped to [0, limit]) with `mode`."""
    start, end = max(start, 0.0), min(end, limit)
    if end - start <= EPS:
        return segments
    for seg in segments:  # snap to a nearby boundary so no sliver gap remains
        if seg.start_s < start and start - seg.start_s <= EPS:
            start = seg.start_s
        if seg.end_s > end and seg.end_s - end <= EPS:
            end = seg.end_s
    out: list[TimelineSegment] = []
    for seg in segments:
        if seg.end_s <= start + EPS or seg.start_s >= end - EPS:
            out.append(seg)
            continue
        if seg.start_s < start - EPS:
            out.append(TimelineSegment(seg.start_s, start, seg.mode))
        if seg.end_s > end + EPS:
            out.append(TimelineSegment(end, seg.end_s, seg.mode))
    out.append(TimelineSegment(start, end, mode))
    return sorted(out, key=lambda s: s.start_s)


def _merge(segments: list[TimelineSegment]) -> tuple[TimelineSegment, ...]:
    merged: list[TimelineSegment] = []
    for seg in segments:
        if merged and merged[-1].mode == seg.mode:
            merged[-1] = TimelineSegment(merged[-1].start_s, seg.end_s, seg.mode)
        else:
            merged.append(seg)
    return tuple(merged)


def build_timeline(scenario: Scenario, env: EnvironmentData) -> tuple[TimelineSegment, ...]:
    """The mode timeline over [0, duration]; contiguous, no gaps, no overlaps."""
    limit = scenario.duration_s
    segments = [TimelineSegment(0.0, limit, scenario.default_mode)]
    for rule in scenario.rules:
        if rule.kind == "during_pass":
            assert rule.site is not None
            if rule.site not in env.sites:
                raise ValueError(f"the environment has no results for site '{rule.site}'")
            for p in env.sites[rule.site].passes:
                segments = _paint(
                    segments, p.aos_s - rule.lead_s, p.los_s + rule.lag_s, rule.mode, limit
                )
        elif rule.kind == "in_eclipse":
            for e in env.eclipses:
                segments = _paint(segments, e.start_s, e.end_s, rule.mode, limit)
        else:  # in_sunlight: the complement of the eclipses
            cursor = 0.0
            for e in sorted(env.eclipses, key=lambda x: x.start_s):
                segments = _paint(segments, cursor, e.start_s, rule.mode, limit)
                cursor = max(cursor, e.end_s)
            segments = _paint(segments, cursor, limit, rule.mode, limit)
    for seg in scenario.segments:
        segments = _paint(segments, seg.start_s, seg.start_s + seg.duration_s, seg.mode, limit)
    return _merge(segments)


def mode_index_on_grid(
    timeline: tuple[TimelineSegment, ...], times_s: NDArray, mode_ids: list[str]
) -> NDArray:
    """Index into `mode_ids` of the mode active at each time (segments are [start, end))."""
    starts = np.array([s.start_s for s in timeline])
    positions = np.clip(np.searchsorted(starts, times_s, side="right") - 1, 0, len(timeline) - 1)
    lookup = {mode: i for i, mode in enumerate(mode_ids)}
    return np.array([lookup[timeline[p].mode] for p in positions], dtype=np.int64)
