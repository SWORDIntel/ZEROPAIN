"""History-dependent receptor adaptation.

This models surface receptor availability and downstream coupling as bounded state
variables with activity-dependent loss and recovery.

It does NOT claim one parameter set applies across receptor families or humans.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class AdaptationParameters:
    internalization_rate_per_h: float = 0.15
    recycling_rate_per_h: float = 0.08
    desensitization_rate_per_h: float = 0.12
    resensitization_rate_per_h: float = 0.06

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class AdaptationState:
    surface_fraction: float = 1.0
    coupling_fraction: float = 1.0

    def validate(self) -> None:
        if not 0.0 <= self.surface_fraction <= 1.0:
            raise ValueError("surface_fraction must be in [0,1]")
        if not 0.0 <= self.coupling_fraction <= 1.0:
            raise ValueError("coupling_fraction must be in [0,1]")


def step_adaptation(
    state: AdaptationState,
    signal_magnitude: float,
    *,
    dt_h: float,
    params: AdaptationParameters = AdaptationParameters(),
) -> AdaptationState:
    state.validate()
    params.validate()
    if dt_h <= 0:
        raise ValueError("dt_h must be positive")
    if not 0.0 <= signal_magnitude <= 1.0:
        raise ValueError("signal_magnitude must be in [0,1]")

    dsurface = (
        params.recycling_rate_per_h * (1.0 - state.surface_fraction)
        - params.internalization_rate_per_h * signal_magnitude * state.surface_fraction
    )
    dcoupling = (
        params.resensitization_rate_per_h * (1.0 - state.coupling_fraction)
        - params.desensitization_rate_per_h * signal_magnitude * state.coupling_fraction
    )

    return AdaptationState(
        surface_fraction=float(np.clip(state.surface_fraction + dt_h * dsurface, 0.0, 1.0)),
        coupling_fraction=float(np.clip(state.coupling_fraction + dt_h * dcoupling, 0.0, 1.0)),
    )
