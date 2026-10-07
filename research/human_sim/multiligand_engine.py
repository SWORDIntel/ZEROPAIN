"""Couple independent PBPK traces to competitive receptor occupancy.

PK interactions are NOT modeled yet: each ligand gets its own linear PBPK trace through
the same physiology. Receptor-level competition is then computed from simultaneous
free-brain concentrations.

This makes the limitation explicit:
    PK independence + PD competition
not:
    full drug-drug interaction simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from research.human_sim.adaptation import (
    AdaptationParameters,
    AdaptationState,
    step_adaptation,
)
from research.human_sim.competition import CompetitionState, LigandInteraction, competitive_state
from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import PBPKTrace, simulate_pbpk
from research.human_sim.physiology import Physiology


@dataclass(frozen=True)
class LigandSpec:
    name: str
    disposition: CompoundDisposition
    target_interactions: Mapping[str, LigandInteraction]

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ligand name cannot be blank")
        if not self.target_interactions:
            raise ValueError(f"{self.name}: at least one target interaction is required")
        for interaction in self.target_interactions.values():
            interaction.validate()
            if interaction.ligand_name != self.name:
                raise ValueError(
                    f"{self.name}: interaction ligand name {interaction.ligand_name!r} does not match"
                )


@dataclass(frozen=True)
class CompetitiveTargetTrace:
    occupancy_by_ligand: Mapping[str, np.ndarray]
    unbound_fraction: np.ndarray
    signed_signal: np.ndarray
    signal_magnitude: np.ndarray
    surface_fraction: np.ndarray
    coupling_fraction: np.ndarray

    def summary(self, times_h: np.ndarray) -> dict:
        return {
            "peak_occupancy_by_ligand": {
                name: float(np.max(values))
                for name, values in self.occupancy_by_ligand.items()
            },
            "minimum_unbound_fraction": float(np.min(self.unbound_fraction)),
            "peak_signal_magnitude": float(np.max(self.signal_magnitude)),
            "mean_signal_magnitude": float(np.mean(self.signal_magnitude)),
            "signed_effect_auc": float(np.trapz(self.signed_signal, times_h)),
            "final_surface_fraction": float(self.surface_fraction[-1]),
            "final_coupling_fraction": float(self.coupling_fraction[-1]),
        }


@dataclass(frozen=True)
class MultiLigandResult:
    pbpk_by_ligand: Mapping[str, PBPKTrace]
    targets: Mapping[str, CompetitiveTargetTrace]

    @property
    def times_h(self) -> np.ndarray:
        return next(iter(self.pbpk_by_ligand.values())).times_h

    def summary(self) -> dict:
        return {
            "ligands": {
                name: trace.summary()
                for name, trace in self.pbpk_by_ligand.items()
            },
            "targets": {
                name: trace.summary(self.times_h)
                for name, trace in self.targets.items()
            },
        }


def simulate_multiligand_chain(
    physiology: Physiology,
    ligands: Mapping[str, LigandSpec],
    *,
    initial_central_amounts: Mapping[str, float],
    duration_h: float,
    dt_h: float,
    adaptation_parameters: Mapping[str, AdaptationParameters] | None = None,
) -> MultiLigandResult:
    if not ligands:
        raise ValueError("at least one ligand is required")
    if set(ligands) != set(initial_central_amounts):
        raise ValueError("initial amount map must match ligand set")

    pbpk = {}
    target_interactions: dict[str, dict[str, LigandInteraction]] = {}

    for name, ligand in ligands.items():
        ligand.validate()
        if name != ligand.name:
            raise ValueError("ligand mapping key must match LigandSpec.name")
        amount = float(initial_central_amounts[name])
        if amount < 0:
            raise ValueError("initial central amounts cannot be negative")
        pbpk[name] = simulate_pbpk(
            physiology,
            ligand.disposition,
            duration_h=duration_h,
            dt_h=dt_h,
            initial_central_amount=amount,
        )
        for target_name, interaction in ligand.target_interactions.items():
            target_interactions.setdefault(target_name, {})[name] = interaction

    lengths = {len(trace.times_h) for trace in pbpk.values()}
    if len(lengths) != 1:
        raise RuntimeError("PBPK traces are not aligned")
    times = next(iter(pbpk.values())).times_h

    adaptation_parameters = dict(adaptation_parameters or {})
    unknown = set(adaptation_parameters) - set(target_interactions)
    if unknown:
        raise ValueError(f"adaptation parameters for unknown targets: {sorted(unknown)}")

    target_traces = {}
    for target_name, interactions in target_interactions.items():
        adaptation = AdaptationState()
        params = adaptation_parameters.get(target_name, AdaptationParameters())

        occupancy_history = {name: [] for name in interactions}
        unbound_history = []
        signed_history = []
        magnitude_history = []
        surface_history = []
        coupling_history = []

        for index in range(len(times)):
            concentrations = {
                ligand_name: float(pbpk[ligand_name].brain_free_concentration[index])
                for ligand_name in interactions
            }
            state: CompetitionState = competitive_state(
                concentrations,
                interactions,
                surface_fraction=adaptation.surface_fraction,
                coupling_fraction=adaptation.coupling_fraction,
            )
            for ligand_name, value in state.occupancy_by_ligand.items():
                occupancy_history[ligand_name].append(value)
            unbound_history.append(state.unbound_fraction)
            signed_history.append(state.signed_signal)
            magnitude_history.append(state.signal_magnitude)
            surface_history.append(state.surface_fraction)
            coupling_history.append(state.coupling_fraction)

            if index + 1 < len(times):
                adaptation = step_adaptation(
                    adaptation,
                    state.signal_magnitude,
                    dt_h=float(times[index + 1] - times[index]),
                    params=params,
                )

        target_traces[target_name] = CompetitiveTargetTrace(
            occupancy_by_ligand={
                name: np.asarray(values, dtype=float)
                for name, values in occupancy_history.items()
            },
            unbound_fraction=np.asarray(unbound_history, dtype=float),
            signed_signal=np.asarray(signed_history, dtype=float),
            signal_magnitude=np.asarray(magnitude_history, dtype=float),
            surface_fraction=np.asarray(surface_history, dtype=float),
            coupling_fraction=np.asarray(coupling_history, dtype=float),
        )

    return MultiLigandResult(pbpk_by_ligand=pbpk, targets=target_traces)
