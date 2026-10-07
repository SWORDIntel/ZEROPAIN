"""Competitive multi-ligand receptor binding for HumanSim.

This is a same-site equilibrium competition model:

    w_i = (C_i / Kd_i)^n_i
    occupancy_i = w_i / (1 + sum_j w_j)

The unbound receptor fraction is therefore:

    1 / (1 + sum_j w_j)

Each ligand then contributes:

    signed signal_i = occupancy_i * efficacy_i * polarity_i

before receptor-surface/coupling availability is applied.

No dosing or clinical exposure model is defined here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class LigandInteraction:
    ligand_name: str
    kd_concentration: float
    efficacy: float
    polarity: int = 1
    hill_coefficient: float = 1.0

    def validate(self) -> None:
        if not self.ligand_name:
            raise ValueError("ligand_name cannot be blank")
        if self.kd_concentration <= 0:
            raise ValueError("kd_concentration must be positive")
        if not 0.0 <= self.efficacy <= 1.0:
            raise ValueError("efficacy must be in [0,1]")
        if self.polarity not in (-1, 1):
            raise ValueError("polarity must be -1 or +1")
        if self.hill_coefficient <= 0:
            raise ValueError("hill_coefficient must be positive")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompetitionState:
    occupancy_by_ligand: Mapping[str, float]
    unbound_fraction: float
    signed_signal: float
    signal_magnitude: float
    surface_fraction: float
    coupling_fraction: float

    def to_dict(self) -> dict:
        return {
            "occupancy_by_ligand": dict(self.occupancy_by_ligand),
            "unbound_fraction": self.unbound_fraction,
            "signed_signal": self.signed_signal,
            "signal_magnitude": self.signal_magnitude,
            "surface_fraction": self.surface_fraction,
            "coupling_fraction": self.coupling_fraction,
        }


def competitive_state(
    concentrations: Mapping[str, float],
    interactions: Mapping[str, LigandInteraction],
    *,
    surface_fraction: float = 1.0,
    coupling_fraction: float = 1.0,
) -> CompetitionState:
    if set(concentrations) != set(interactions):
        raise ValueError("concentration and interaction ligand sets must match")
    if not 0.0 <= surface_fraction <= 1.0:
        raise ValueError("surface_fraction must be in [0,1]")
    if not 0.0 <= coupling_fraction <= 1.0:
        raise ValueError("coupling_fraction must be in [0,1]")

    weights = {}
    for name, interaction in interactions.items():
        interaction.validate()
        concentration = float(concentrations[name])
        if concentration < 0:
            raise ValueError("concentrations cannot be negative")
        weights[name] = (
            (concentration / interaction.kd_concentration)
            ** interaction.hill_coefficient
            if concentration > 0
            else 0.0
        )

    denominator = 1.0 + sum(weights.values())
    occupancy = {
        name: float(weight / denominator)
        for name, weight in weights.items()
    }
    unbound = float(1.0 / denominator)

    intrinsic_signed = sum(
        occupancy[name] * interactions[name].efficacy * interactions[name].polarity
        for name in interactions
    )
    signed = intrinsic_signed * surface_fraction * coupling_fraction
    magnitude = float(np.clip(abs(signed), 0.0, 1.0))

    return CompetitionState(
        occupancy_by_ligand=occupancy,
        unbound_fraction=unbound,
        signed_signal=float(np.clip(signed, -1.0, 1.0)),
        signal_magnitude=magnitude,
        surface_fraction=surface_fraction,
        coupling_fraction=coupling_fraction,
    )
