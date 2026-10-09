"""Battery model: capacity and an energy-based state-of-charge integration (TDP-SOC).

The battery is an energy store with constant charge and discharge efficiencies. Within a step the
net power is constant, so saturation (full or empty) is exact for the step. No voltage, current
limit or temperature effect is modelled (DEVIATIONS DV-P4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

NDArray = np.ndarray[Any, np.dtype[np.float64]]


def pack_capacity_wh(
    cell_capacity_ah: float,
    cell_voltage_v: float,
    cells_in_series: int,
    cells_in_parallel: int,
    annual_fade_ratio: float,
    years: float,
) -> float:
    """TDP-CAP: usable energy of the pack after `years` of capacity fade."""
    if not 0.0 <= annual_fade_ratio < 1.0 or years < 0.0:
        raise ValueError("annual fade must be in [0, 1) and years not negative")
    nominal = cell_capacity_ah * cell_voltage_v * cells_in_series * cells_in_parallel
    return float(nominal * (1.0 - annual_fade_ratio) ** years)


@dataclass(frozen=True, eq=False)
class BatteryTrace:
    energy_wh: NDArray  # stored energy at the step edges, shape (N + 1,)
    battery_power_w: NDArray  # bus-side power into the battery (negative: discharging), (N,)
    unmet_w: NDArray  # demand the battery could not supply (average over the step), (N,)
    curtailed_w: NDArray  # generation neither used nor stored (average over the step), (N,)


def integrate_battery(
    dt_s: NDArray,
    generation_w: NDArray,
    demand_w: NDArray,
    capacity_wh: float,
    charge_efficiency_ratio: float,
    discharge_efficiency_ratio: float,
    initial_energy_wh: float,
) -> BatteryTrace:
    """Integrate the stored energy over the steps.

    Surplus (generation minus demand) charges: stored += eta_c * accepted, limited by free
    capacity. Deficit discharges: stored -= supplied / eta_d, limited by what is stored. Powers
    are at the bus (before the battery's own efficiencies)."""
    if not 0.0 < charge_efficiency_ratio <= 1.0 or not 0.0 < discharge_efficiency_ratio <= 1.0:
        raise ValueError("battery efficiencies must be in (0, 1]")
    if capacity_wh < 0.0 or not 0.0 <= initial_energy_wh <= capacity_wh * (1.0 + 1e-12):
        raise ValueError("the initial energy must lie between 0 and the capacity")
    n = len(dt_s)
    steps = np.asarray(dt_s, dtype=np.float64).tolist()
    net = np.asarray(generation_w, dtype=np.float64) - np.asarray(demand_w, dtype=np.float64)
    net_list = net.tolist()
    energy = [0.0] * (n + 1)
    battery = [0.0] * n
    unmet = [0.0] * n
    curtailed = [0.0] * n
    e = min(initial_energy_wh, capacity_wh)
    energy[0] = e
    eta_c, eta_d = charge_efficiency_ratio, discharge_efficiency_ratio
    for i in range(n):
        hours = steps[i] / 3600.0
        p = net_list[i]
        if p >= 0.0:
            offered = p * hours  # Wh at the bus
            room = (capacity_wh - e) / eta_c
            accepted = offered if offered <= room else room
            if accepted < 0.0:
                accepted = 0.0
            e += eta_c * accepted
            if e > capacity_wh:
                e = capacity_wh
            battery[i] = accepted / hours
            curtailed[i] = (offered - accepted) / hours
        else:
            needed = -p * hours
            available = e * eta_d
            supplied = needed if needed <= available else available
            e -= supplied / eta_d
            if e < 0.0:
                e = 0.0
            battery[i] = -supplied / hours
            unmet[i] = (needed - supplied) / hours
        energy[i + 1] = e
    return BatteryTrace(np.array(energy), np.array(battery), np.array(unmet), np.array(curtailed))
