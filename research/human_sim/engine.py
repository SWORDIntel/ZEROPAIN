"""First executable HumanSim multiscale chain.

physiology -> PBPK -> free brain concentration -> receptor occupancy/effect
           -> activity-dependent receptor/coupling adaptation

The target parameters in this module are generic. Human calibration belongs in a
future source-backed parameter layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

import numpy as np

from research.human_sim.adaptation import (
    AdaptationParameters,
    AdaptationState,
    step_adaptation,
)
from research.human_sim.pbpk import PBPKTrace, simulate_pbpk
from research.human_sim.physiology import Physiology
from research.human_sim.receptors import ReceptorState, ReceptorTarget, receptor_state


@dataclass(frozen=True)
class TargetTrace:
    occupancy: np.ndarray
    signal_magnitude: np.ndarray
    signed_effect: np.ndarray
    surface_fraction: np.ndarray
    coupling_fraction: np.ndarray

    def summary(self, times_h: np.ndarray) -> dict[str, float]:
        return {
            "peak_occupancy": float(np.max(self.occupancy)),
            "mean_occupancy": float(np.mean(self.occupancy)),
            "peak_signal_magnitude": float(np.max(self.signal_magnitude)),
            "mean_signal_magnitude": float(np.mean(self.signal_magnitude)),
            "signed_effect_auc": float(np.trapz(self.signed_effect, times_h)),
            "final_surface_fraction": float(self.surface_fraction[-1]),
            "final_coupling_fraction": float(self.coupling_fraction[-1]),
        }


@dataclass(frozen=True)
class HumanSimResult:
    pbpk: PBPKTrace
    targets: Mapping[str, TargetTrace]

    def summary(self) -> dict:
        return {
            "pbpk": self.pbpk.summary(),
            "targets": {
                name: trace.summary(self.pbpk.times_h)
                for name, trace in self.targets.items()
            },
        }

    def to_dict(self, *, include_trace: bool = False) -> dict:
        payload = {
            "summary": self.summary(),
        }
        if include_trace:
            payload["trace"] = {
                "times_h": self.pbpk.times_h.tolist(),
                "central_amount": self.pbpk.central_amount.tolist(),
                "tissue_amounts": {
                    name: values.tolist()
                    for name, values in self.pbpk.tissue_amounts.items()
                },
                "eliminated_amount": self.pbpk.eliminated_amount.tolist(),
                "cumulative_input": self.pbpk.cumulative_input.tolist(),
                "mass_balance_error": self.pbpk.mass_balance_error.tolist(),
                "central_concentration": self.pbpk.central_concentration.tolist(),
                "brain_total_concentration": self.pbpk.brain_total_concentration.tolist(),
                "brain_free_concentration": self.pbpk.brain_free_concentration.tolist(),
                "targets": {
                    name: {
                        "occupancy": trace.occupancy.tolist(),
                        "signal_magnitude": trace.signal_magnitude.tolist(),
                        "signed_effect": trace.signed_effect.tolist(),
                        "surface_fraction": trace.surface_fraction.tolist(),
                        "coupling_fraction": trace.coupling_fraction.tolist(),
                    }
                    for name, trace in self.targets.items()
                },
            }
        return payload


def simulate_human_chain(
    physiology: Physiology,
    targets: Mapping[str, ReceptorTarget],
    *,
    duration_h: float,
    dt_h: float,
    initial_central_amount: float = 0.0,
    input_rate=None,
    adaptation_parameters: Mapping[str, AdaptationParameters] | None = None,
) -> HumanSimResult:
    if not targets:
        raise ValueError("at least one receptor/target model is required")
    for name, target in targets.items():
        target.validate()
        if name != target.name:
            raise ValueError(f"target mapping key {name!r} must match target.name {target.name!r}")

    pbpk = simulate_pbpk(
        physiology,
        duration_h=duration_h,
        dt_h=dt_h,
        initial_central_amount=initial_central_amount,
        input_rate=input_rate,
    )
    adaptation_parameters = dict(adaptation_parameters or {})
    unknown = set(adaptation_parameters) - set(targets)
    if unknown:
        raise ValueError(f"adaptation parameters supplied for unknown targets: {sorted(unknown)}")

    histories = {}
    for name, target in targets.items():
        adaptation = AdaptationState()
        params = adaptation_parameters.get(name, AdaptationParameters())

        occupancy = []
        signal = []
        signed = []
        surface = []
        coupling = []

        for index, concentration in enumerate(pbpk.brain_free_concentration):
            state: ReceptorState = receptor_state(
                float(concentration),
                target,
                surface_fraction=adaptation.surface_fraction,
                coupling_fraction=adaptation.coupling_fraction,
            )
            occupancy.append(state.occupancy)
            signal.append(state.effective_signal_magnitude)
            signed.append(state.signed_effect)
            surface.append(state.surface_fraction)
            coupling.append(state.coupling_fraction)

            if index + 1 < len(pbpk.times_h):
                dt = float(pbpk.times_h[index + 1] - pbpk.times_h[index])
                adaptation = step_adaptation(
                    adaptation,
                    state.effective_signal_magnitude,
                    dt_h=dt,
                    params=params,
                )

        histories[name] = TargetTrace(
            occupancy=np.asarray(occupancy, dtype=float),
            signal_magnitude=np.asarray(signal, dtype=float),
            signed_effect=np.asarray(signed, dtype=float),
            surface_fraction=np.asarray(surface, dtype=float),
            coupling_fraction=np.asarray(coupling, dtype=float),
        )

    return HumanSimResult(pbpk=pbpk, targets=histories)


def synthetic_target_panel() -> dict[str, ReceptorTarget]:
    """Synthetic target fixture for software testing only; values are not literature data."""

    return {
        "MOR_SYNTH": ReceptorTarget(
            "MOR_SYNTH", kd_concentration=0.12, effect_gain=0.65, effect_polarity=1
        ),
        "KOR_SYNTH": ReceptorTarget(
            "KOR_SYNTH", kd_concentration=0.30, effect_gain=0.55, effect_polarity=1
        ),
        "NOP_SYNTH": ReceptorTarget(
            "NOP_SYNTH", kd_concentration=0.22, effect_gain=0.50, effect_polarity=1
        ),
        "NMDAR_SYNTH": ReceptorTarget(
            "NMDAR_SYNTH", kd_concentration=0.45, effect_gain=0.70, effect_polarity=-1
        ),
    }
