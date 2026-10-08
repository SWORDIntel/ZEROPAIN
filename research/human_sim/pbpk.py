"""Positive, mass-conserving perfusion-limited PBPK research kernel.

The kernel evolves amounts rather than directly integrating concentrations.

For each tissue, the perfusion-limited exchange equation is:

    dA_t/dt = Q_t * (C_c - C_t / Kp_t)

which is equivalent to a two-compartment linear exchange with:

    k_c_to_t = Q_t / V_c
    k_t_to_c = Q_t / (V_t * Kp_t)

Each pairwise exchange is solved analytically and composed with a symmetric
forward/reverse half-sweep around the clearance operator. This reduces directional
operator-splitting bias while retaining non-negative amounts and exact conservation
during exchange. Clearance is applied analytically and accumulated into an explicit
eliminated-amount state.

External input is an arbitrary amount/time callback. It is intentionally not a
dose-conversion interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.physiology import Physiology


InputRate = Callable[[float], float]


@dataclass(frozen=True)
class PBPKState:
    time_h: float
    central_amount: float
    tissue_amounts: Mapping[str, float]
    eliminated_amount: float
    cumulative_input: float

    @property
    def body_amount(self) -> float:
        return self.central_amount + sum(self.tissue_amounts.values())

    @property
    def accounted_amount(self) -> float:
        return self.body_amount + self.eliminated_amount


@dataclass(frozen=True)
class PBPKTrace:
    times_h: np.ndarray
    central_amount: np.ndarray
    tissue_amounts: Mapping[str, np.ndarray]
    eliminated_amount: np.ndarray
    cumulative_input: np.ndarray
    mass_balance_error: np.ndarray
    central_concentration: np.ndarray
    brain_total_concentration: np.ndarray
    brain_free_concentration: np.ndarray

    def summary(self) -> dict[str, float]:
        return {
            "final_body_amount": float(
                self.central_amount[-1]
                + sum(values[-1] for values in self.tissue_amounts.values())
            ),
            "final_eliminated_amount": float(self.eliminated_amount[-1]),
            "cumulative_input": float(self.cumulative_input[-1]),
            "max_abs_mass_balance_error": float(np.max(np.abs(self.mass_balance_error))),
            "peak_central_concentration": float(np.max(self.central_concentration)),
            "peak_brain_total_concentration": float(np.max(self.brain_total_concentration)),
            "peak_brain_free_concentration": float(np.max(self.brain_free_concentration)),
        }


def _exchange_pair(
    central: float,
    tissue: float,
    k_forward: float,
    k_reverse: float,
    dt: float,
) -> tuple[float, float]:
    """Exact two-state exchange update preserving positivity and total amount."""

    rate = k_forward + k_reverse
    if rate <= 0.0:
        return central, tissue

    total = central + tissue
    equilibrium_central = (k_reverse / rate) * total
    updated_central = equilibrium_central + (
        central - equilibrium_central
    ) * np.exp(-rate * dt)
    updated_tissue = total - updated_central

    if updated_central < 0 and updated_central > -1e-12:
        updated_central = 0.0
        updated_tissue = total
    if updated_tissue < 0 and updated_tissue > -1e-12:
        updated_tissue = 0.0
        updated_central = total
    return float(updated_central), float(updated_tissue)


def _clear_amount(amount: float, clearance_rate_per_h: float, dt: float) -> tuple[float, float]:
    if clearance_rate_per_h <= 0:
        return amount, 0.0
    remaining = amount * np.exp(-clearance_rate_per_h * dt)
    removed = amount - remaining
    return float(remaining), float(removed)


def _exchange_sweep(
    central: float,
    tissue_state: dict[str, float],
    *,
    physiology: Physiology,
    disposition: CompoundDisposition,
    dt: float,
    reverse: bool = False,
) -> tuple[float, dict[str, float]]:
    """Apply one ordered analytical pairwise-exchange sweep.

    A forward half-sweep followed later by a reverse half-sweep gives a symmetric
    Strang-style composition and removes most directional operator-splitting bias.
    """

    tissues = physiology.tissue_map
    names = list(tissues)
    if reverse:
        names.reverse()

    for name in names:
        tissue = tissues[name]
        k_forward = tissue.blood_flow_l_per_h / physiology.central_volume_l
        k_reverse = (
            tissue.blood_flow_l_per_h
            / (
                tissue.volume_l
                * disposition.tissue_partition_coefficients[name]
            )
        )
        central, tissue_state[name] = _exchange_pair(
            central,
            tissue_state[name],
            k_forward,
            k_reverse,
            dt,
        )
    return central, tissue_state


def simulate_pbpk(
    physiology: Physiology,
    disposition: CompoundDisposition,
    *,
    duration_h: float,
    dt_h: float,
    initial_central_amount: float = 0.0,
    initial_tissue_amounts: Mapping[str, float] | None = None,
    input_rate: InputRate | None = None,
) -> PBPKTrace:
    """Simulate the compartment system using arbitrary amount units."""

    physiology.validate()
    tissues = physiology.tissue_map
    disposition.validate(set(tissues))
    if duration_h <= 0 or dt_h <= 0:
        raise ValueError("duration_h and dt_h must be positive")
    if initial_central_amount < 0:
        raise ValueError("initial_central_amount cannot be negative")

    n_steps = int(np.ceil(duration_h / dt_h))
    times = np.minimum(np.arange(n_steps + 1) * dt_h, duration_h)
    initial_tissue_amounts = dict(initial_tissue_amounts or {})

    unknown = set(initial_tissue_amounts) - set(tissues)
    if unknown:
        raise ValueError(f"unknown initial tissue compartments: {sorted(unknown)}")
    if any(value < 0 for value in initial_tissue_amounts.values()):
        raise ValueError("initial tissue amounts cannot be negative")

    central = float(initial_central_amount)
    tissue_state = {
        name: float(initial_tissue_amounts.get(name, 0.0))
        for name in tissues
    }
    eliminated = 0.0
    cumulative_input = 0.0
    initial_total = central + sum(tissue_state.values())

    central_history = [central]
    tissue_history = {name: [amount] for name, amount in tissue_state.items()}
    eliminated_history = [eliminated]
    input_history = [cumulative_input]
    error_history = [0.0]

    for step in range(n_steps):
        t0 = times[step]
        t1 = times[step + 1]
        dt = float(t1 - t0)
        if dt <= 0:
            continue

        # Symmetric source/exchange/clearance composition.
        #
        # Source is split across the beginning/end of the step using endpoint rates;
        # pairwise exchange is half-stepped forward then reverse; clearance is the
        # central full operator. This substantially reduces tissue-order bias while
        # retaining positivity and exact pairwise conservation.
        if input_rate is None:
            rate_start = rate_end = 0.0
        else:
            rate_start = float(input_rate(float(t0)))
            rate_end = float(input_rate(float(t1)))
            if rate_start < 0 or rate_end < 0:
                raise ValueError("input_rate cannot return a negative value")

        added_start = 0.5 * rate_start * dt
        central += added_start
        cumulative_input += added_start

        central, tissue_state = _exchange_sweep(
            central,
            tissue_state,
            physiology=physiology,
            disposition=disposition,
            dt=0.5 * dt,
            reverse=False,
        )

        liver = tissues.get("liver")
        if liver is not None and disposition.hepatic_clearance_l_per_h > 0:
            # Backward-compatible legacy tissue-concentration clearance.
            rate_h = disposition.hepatic_clearance_l_per_h / liver.volume_l
            tissue_state["liver"], removed = _clear_amount(
                tissue_state["liver"], rate_h, dt
            )
            eliminated += removed

        if (
            liver is not None
            and disposition.hepatic_intrinsic_unbound_clearance_l_per_h > 0
        ):
            # Mechanistic tissue-side metabolism:
            # rate = CLint,u * fu_liver * C_liver,total.
            effective_clearance = (
                disposition.hepatic_intrinsic_unbound_clearance_l_per_h
                * float(disposition.liver_unbound_fraction)
            )
            rate_h = effective_clearance / liver.volume_l
            tissue_state["liver"], removed = _clear_amount(
                tissue_state["liver"], rate_h, dt
            )
            eliminated += removed

        kidney = tissues.get("kidney")
        if kidney is not None and disposition.renal_clearance_l_per_h > 0:
            # Backward-compatible legacy tissue-concentration clearance.
            rate_h = disposition.renal_clearance_l_per_h / kidney.volume_l
            tissue_state["kidney"], removed = _clear_amount(
                tissue_state["kidney"], rate_h, dt
            )
            eliminated += removed

        if disposition.renal_gfr_l_per_h > 0:
            # Glomerular filtration acts on unbound plasma concentration. Central
            # concentration is treated as whole blood, so:
            # Cu,plasma = Cblood * fu_plasma / (Cblood/Cplasma).
            fu_blood_equivalent = (
                disposition.plasma_unbound_fraction
                / disposition.blood_to_plasma_ratio
            )
            filtration_clearance = (
                disposition.renal_gfr_l_per_h * fu_blood_equivalent
            )
            rate_h = filtration_clearance / physiology.central_volume_l
            central, removed = _clear_amount(central, rate_h, dt)
            eliminated += removed

        central, tissue_state = _exchange_sweep(
            central,
            tissue_state,
            physiology=physiology,
            disposition=disposition,
            dt=0.5 * dt,
            reverse=True,
        )

        added_end = 0.5 * rate_end * dt
        central += added_end
        cumulative_input += added_end

        accounted = central + sum(tissue_state.values()) + eliminated
        expected = initial_total + cumulative_input
        error = accounted - expected

        central_history.append(central)
        for name in tissues:
            tissue_history[name].append(tissue_state[name])
        eliminated_history.append(eliminated)
        input_history.append(cumulative_input)
        error_history.append(error)

    central_arr = np.asarray(central_history, dtype=float)
    brain_arr = np.asarray(tissue_history["brain"], dtype=float)
    central_conc = central_arr / physiology.central_volume_l
    brain_total = brain_arr / tissues["brain"].volume_l
    brain_free = brain_total * disposition.brain_unbound_fraction

    return PBPKTrace(
        times_h=np.asarray(times, dtype=float),
        central_amount=central_arr,
        tissue_amounts={
            name: np.asarray(values, dtype=float)
            for name, values in tissue_history.items()
        },
        eliminated_amount=np.asarray(eliminated_history, dtype=float),
        cumulative_input=np.asarray(input_history, dtype=float),
        mass_balance_error=np.asarray(error_history, dtype=float),
        central_concentration=central_conc,
        brain_total_concentration=brain_total,
        brain_free_concentration=brain_free,
    )
