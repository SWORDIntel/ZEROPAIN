"""Independent PBPK reference integrator for verification.

This module intentionally does NOT reuse the pairwise analytical exchange update from
pbpk.py. It integrates the coupled amount ODEs with classical RK4 and a smaller
sub-step, providing an algorithmically independent check for the ECC 0x20 bit.

It is a verifier/reference path, not the production solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import PBPKTrace
from research.human_sim.physiology import Physiology


@dataclass(frozen=True)
class ReferenceComparison:
    central_nrmse: float
    brain_total_nrmse: float
    brain_free_nrmse: float
    eliminated_nrmse: float
    max_metric: float

    def to_dict(self) -> dict[str, float]:
        return {
            "central_nrmse": self.central_nrmse,
            "brain_total_nrmse": self.brain_total_nrmse,
            "brain_free_nrmse": self.brain_free_nrmse,
            "eliminated_nrmse": self.eliminated_nrmse,
            "max_metric": self.max_metric,
        }


def _derivative(
    state: np.ndarray,
    t: float,
    *,
    physiology: Physiology,
    disposition: CompoundDisposition,
    tissue_names: list[str],
    input_rate: Callable[[float], float] | None,
) -> np.ndarray:
    tissues = physiology.tissue_map
    central = state[0]
    tissue_amounts = state[1 : 1 + len(tissue_names)]

    d = np.zeros_like(state)
    central_concentration = central / physiology.central_volume_l

    for index, name in enumerate(tissue_names):
        tissue = tissues[name]
        amount = tissue_amounts[index]
        tissue_concentration = amount / tissue.volume_l
        kp = disposition.tissue_partition_coefficients[name]
        flux = tissue.blood_flow_l_per_h * (
            central_concentration - tissue_concentration / kp
        )
        d[0] -= flux
        d[1 + index] += flux

        if name == "liver" and disposition.hepatic_clearance_l_per_h > 0:
            cleared = disposition.hepatic_clearance_l_per_h * tissue_concentration
            d[1 + index] -= cleared
            d[-1] += cleared

        if (
            name == "liver"
            and disposition.hepatic_intrinsic_unbound_clearance_l_per_h > 0
        ):
            cleared = (
                disposition.hepatic_intrinsic_unbound_clearance_l_per_h
                * float(disposition.liver_unbound_fraction)
                * tissue_concentration
            )
            d[1 + index] -= cleared
            d[-1] += cleared

        if name == "kidney" and disposition.renal_clearance_l_per_h > 0:
            cleared = disposition.renal_clearance_l_per_h * tissue_concentration
            d[1 + index] -= cleared
            d[-1] += cleared

    if disposition.renal_gfr_l_per_h > 0:
        central_concentration = central / physiology.central_volume_l
        unbound_plasma_concentration = (
            central_concentration
            * disposition.plasma_unbound_fraction
            / disposition.blood_to_plasma_ratio
        )
        filtered = disposition.renal_gfr_l_per_h * unbound_plasma_concentration
        d[0] -= filtered
        d[-1] += filtered

    if input_rate is not None:
        rate = float(input_rate(t))
        if rate < 0:
            raise ValueError("input_rate cannot return a negative value")
        d[0] += rate

    return d


def simulate_pbpk_reference(
    physiology: Physiology,
    disposition: CompoundDisposition,
    *,
    duration_h: float,
    output_dt_h: float,
    substeps: int = 20,
    initial_central_amount: float = 0.0,
    input_rate: Callable[[float], float] | None = None,
) -> PBPKTrace:
    physiology.validate()
    disposition.validate(set(physiology.tissue_map))
    if duration_h <= 0 or output_dt_h <= 0:
        raise ValueError("duration_h and output_dt_h must be positive")
    if substeps < 2:
        raise ValueError("substeps must be >= 2")

    tissue_names = list(physiology.tissue_map)
    n_outputs = int(np.ceil(duration_h / output_dt_h))
    times = np.minimum(np.arange(n_outputs + 1) * output_dt_h, duration_h)

    # central, each tissue, eliminated
    state = np.zeros(2 + len(tissue_names), dtype=float)
    state[0] = initial_central_amount

    central_history = [state[0]]
    tissue_history = {name: [0.0] for name in tissue_names}
    eliminated_history = [0.0]
    cumulative_input_history = [0.0]
    mass_error_history = [0.0]
    cumulative_input = 0.0
    initial_total = initial_central_amount

    for output_index in range(n_outputs):
        t0 = float(times[output_index])
        t1 = float(times[output_index + 1])
        interval = t1 - t0
        h = interval / substeps
        t = t0

        for _ in range(substeps):
            kwargs = dict(
                physiology=physiology,
                disposition=disposition,
                tissue_names=tissue_names,
                input_rate=input_rate,
            )
            k1 = _derivative(state, t, **kwargs)
            k2 = _derivative(state + 0.5 * h * k1, t + 0.5 * h, **kwargs)
            k3 = _derivative(state + 0.5 * h * k2, t + 0.5 * h, **kwargs)
            k4 = _derivative(state + h * k3, t + h, **kwargs)
            state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            # Reference solver should not need clipping; reject meaningful negativity.
            if np.min(state[:-1]) < -1e-9:
                raise RuntimeError("reference RK4 produced negative compartment amount")
            state[:-1] = np.maximum(state[:-1], 0.0)

            if input_rate is not None:
                # Simpson-compatible accumulation using midpoint.
                cumulative_input += (
                    h
                    * (
                        float(input_rate(t))
                        + 4.0 * float(input_rate(t + 0.5 * h))
                        + float(input_rate(t + h))
                    )
                    / 6.0
                )
            t += h

        central_history.append(float(state[0]))
        for idx, name in enumerate(tissue_names):
            tissue_history[name].append(float(state[1 + idx]))
        eliminated_history.append(float(state[-1]))
        cumulative_input_history.append(float(cumulative_input))
        accounted = float(np.sum(state))
        mass_error_history.append(accounted - (initial_total + cumulative_input))

    central_arr = np.asarray(central_history)
    brain_arr = np.asarray(tissue_history["brain"])
    brain_volume = physiology.tissue_map["brain"].volume_l
    brain_total = brain_arr / brain_volume

    return PBPKTrace(
        times_h=np.asarray(times),
        central_amount=central_arr,
        tissue_amounts={
            name: np.asarray(values)
            for name, values in tissue_history.items()
        },
        eliminated_amount=np.asarray(eliminated_history),
        cumulative_input=np.asarray(cumulative_input_history),
        mass_balance_error=np.asarray(mass_error_history),
        central_concentration=central_arr / physiology.central_volume_l,
        brain_total_concentration=brain_total,
        brain_free_concentration=brain_total * disposition.brain_unbound_fraction,
    )


def _nrmse(reference: np.ndarray, candidate: np.ndarray) -> float:
    if len(reference) != len(candidate):
        raise ValueError("trace lengths differ")
    scale = max(float(np.max(np.abs(reference))), 1e-12)
    return float(np.sqrt(np.mean((candidate - reference) ** 2)) / scale)


def compare_to_reference(
    primary: PBPKTrace,
    reference: PBPKTrace,
) -> ReferenceComparison:
    metrics = {
        "central_nrmse": _nrmse(reference.central_concentration, primary.central_concentration),
        "brain_total_nrmse": _nrmse(
            reference.brain_total_concentration, primary.brain_total_concentration
        ),
        "brain_free_nrmse": _nrmse(
            reference.brain_free_concentration, primary.brain_free_concentration
        ),
        "eliminated_nrmse": _nrmse(
            reference.eliminated_amount, primary.eliminated_amount
        ),
    }
    return ReferenceComparison(
        **metrics,
        max_metric=max(metrics.values()),
    )
