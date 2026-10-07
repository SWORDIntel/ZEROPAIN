"""Receptor occupancy and target-effect primitives.

This module deliberately separates binding occupancy, effect gain, receptor surface
availability, and intracellular coupling availability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class ReceptorTarget:
    name: str
    kd_concentration: float
    hill_coefficient: float = 1.0
    effect_gain: float = 1.0
    effect_polarity: int = 1

    def validate(self) -> None:
        if not self.name:
            raise ValueError("target name cannot be blank")
        if self.kd_concentration <= 0:
            raise ValueError(f"{self.name}: kd_concentration must be positive")
        if self.hill_coefficient <= 0:
            raise ValueError(f"{self.name}: hill_coefficient must be positive")
        if not 0.0 <= self.effect_gain <= 1.0:
            raise ValueError(f"{self.name}: effect_gain must be in [0,1]")
        if self.effect_polarity not in (-1, 1):
            raise ValueError(f"{self.name}: effect_polarity must be -1 or +1")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReceptorState:
    occupancy: float
    effective_signal_magnitude: float
    signed_effect: float
    surface_fraction: float
    coupling_fraction: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def hill_occupancy(
    free_concentration: float,
    kd_concentration: float,
    hill_coefficient: float = 1.0,
) -> float:
    if free_concentration < 0:
        raise ValueError("free_concentration cannot be negative")
    if kd_concentration <= 0 or hill_coefficient <= 0:
        raise ValueError("kd_concentration and hill_coefficient must be positive")
    if free_concentration == 0:
        return 0.0

    c = free_concentration ** hill_coefficient
    kd = kd_concentration ** hill_coefficient
    return float(c / (kd + c))


def receptor_state(
    free_concentration: float,
    target: ReceptorTarget,
    *,
    surface_fraction: float = 1.0,
    coupling_fraction: float = 1.0,
) -> ReceptorState:
    target.validate()
    if not 0.0 <= surface_fraction <= 1.0:
        raise ValueError("surface_fraction must be in [0,1]")
    if not 0.0 <= coupling_fraction <= 1.0:
        raise ValueError("coupling_fraction must be in [0,1]")

    occupancy = hill_occupancy(
        free_concentration,
        target.kd_concentration,
        target.hill_coefficient,
    )
    magnitude = (
        occupancy
        * target.effect_gain
        * surface_fraction
        * coupling_fraction
    )
    magnitude = float(np.clip(magnitude, 0.0, 1.0))
    return ReceptorState(
        occupancy=occupancy,
        effective_signal_magnitude=magnitude,
        signed_effect=target.effect_polarity * magnitude,
        surface_fraction=surface_fraction,
        coupling_fraction=coupling_fraction,
    )
