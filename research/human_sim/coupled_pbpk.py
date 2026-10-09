"""Synchronous multi-ligand PBPK with transporter-mediated PK interactions.

Perfusion exchange and non-transporter elimination remain compound-specific.
Only shared transporter interaction groups couple ligands.

The time-step composition mirrors the single-compound production solver:

    exchange half-step
    competitive transporter half-step
    non-transporter elimination full-step
    competitive transporter half-step
    reverse exchange half-step

Each ligand keeps its own eliminated pool and mass-balance audit.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import PBPKTrace, _clear_amount, _exchange_sweep
from research.human_sim.physiology import Physiology
from research.human_sim.transporter_competition import (
    TransporterInhibition,
    apply_competitive_transporter_step,
)


def _apply_nontransporter_elimination(
    *,
    central: float,
    tissue_state: dict[str, float],
    eliminated: float,
    physiology: Physiology,
    disposition: CompoundDisposition,
    dt: float,
) -> tuple[float, dict[str, float], float]:
    tissues = physiology.tissue_map

    liver = tissues.get("liver")
    if liver is not None and disposition.hepatic_clearance_l_per_h > 0:
        rate_h = disposition.hepatic_clearance_l_per_h / liver.volume_l
        tissue_state["liver"], removed = _clear_amount(
            tissue_state["liver"], rate_h, dt
        )
        eliminated += removed

    if (
        liver is not None
        and disposition.hepatic_intrinsic_unbound_clearance_l_per_h > 0
    ):
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
        rate_h = disposition.renal_clearance_l_per_h / kidney.volume_l
        tissue_state["kidney"], removed = _clear_amount(
            tissue_state["kidney"], rate_h, dt
        )
        eliminated += removed

    if disposition.renal_gfr_l_per_h > 0:
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

    return central, tissue_state, eliminated


def simulate_coupled_pbpk(
    physiology: Physiology,
    dispositions: Mapping[str, CompoundDisposition],
    *,
    initial_central_amounts: Mapping[str, float],
    duration_h: float,
    dt_h: float,
    inhibitions_by_ligand: Mapping[str, tuple[TransporterInhibition, ...]] | None = None,
    initial_tissue_amounts_by_ligand: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, PBPKTrace]:
    """Simulate multiple compounds with shared-transporter PK interactions."""

    physiology.validate()
    tissue_names = set(physiology.tissue_map)
    ligand_names = set(dispositions)
    if not ligand_names:
        raise ValueError("at least one disposition is required")
    if set(initial_central_amounts) != ligand_names:
        raise ValueError("initial central amount map must match disposition ligand set")
    if duration_h <= 0 or dt_h <= 0:
        raise ValueError("duration_h and dt_h must be positive")

    for name, disposition in dispositions.items():
        disposition.validate(tissue_names)
        if float(initial_central_amounts[name]) < 0:
            raise ValueError("initial central amounts cannot be negative")

    initial_tissue_amounts_by_ligand = dict(
        initial_tissue_amounts_by_ligand or {}
    )
    unknown_ligands = set(initial_tissue_amounts_by_ligand) - ligand_names
    if unknown_ligands:
        raise ValueError(
            f"initial tissue amounts for unknown ligands: {sorted(unknown_ligands)}"
        )

    central = {
        name: float(initial_central_amounts[name])
        for name in ligand_names
    }
    tissues = {}
    for ligand in ligand_names:
        supplied = dict(initial_tissue_amounts_by_ligand.get(ligand, {}))
        unknown_tissues = set(supplied) - tissue_names
        if unknown_tissues:
            raise ValueError(
                f"{ligand}: unknown initial tissues {sorted(unknown_tissues)}"
            )
        if any(value < 0 for value in supplied.values()):
            raise ValueError("initial tissue amounts cannot be negative")
        tissues[ligand] = {
            tissue: float(supplied.get(tissue, 0.0))
            for tissue in physiology.tissue_map
        }

    eliminated = {name: 0.0 for name in ligand_names}
    initial_total = {
        name: central[name] + sum(tissues[name].values())
        for name in ligand_names
    }

    n_steps = int(np.ceil(duration_h / dt_h))
    times = np.minimum(np.arange(n_steps + 1) * dt_h, duration_h)

    central_history = {name: [central[name]] for name in ligand_names}
    tissue_history = {
        ligand: {
            tissue: [tissues[ligand][tissue]]
            for tissue in physiology.tissue_map
        }
        for ligand in ligand_names
    }
    eliminated_history = {name: [0.0] for name in ligand_names}
    error_history = {name: [0.0] for name in ligand_names}

    for step in range(n_steps):
        dt = float(times[step + 1] - times[step])
        if dt <= 0:
            continue

        for ligand in ligand_names:
            central[ligand], tissues[ligand] = _exchange_sweep(
                central[ligand],
                tissues[ligand],
                physiology=physiology,
                disposition=dispositions[ligand],
                dt=0.5 * dt,
                reverse=False,
            )

        central, tissues, eliminated, _ = apply_competitive_transporter_step(
            central_amounts=central,
            tissue_amounts_by_ligand=tissues,
            eliminated_amounts=eliminated,
            physiology=physiology,
            dispositions=dispositions,
            inhibitions_by_ligand=inhibitions_by_ligand,
            dt_h=0.5 * dt,
        )

        for ligand in ligand_names:
            central[ligand], tissues[ligand], eliminated[ligand] = (
                _apply_nontransporter_elimination(
                    central=central[ligand],
                    tissue_state=tissues[ligand],
                    eliminated=eliminated[ligand],
                    physiology=physiology,
                    disposition=dispositions[ligand],
                    dt=dt,
                )
            )

        central, tissues, eliminated, _ = apply_competitive_transporter_step(
            central_amounts=central,
            tissue_amounts_by_ligand=tissues,
            eliminated_amounts=eliminated,
            physiology=physiology,
            dispositions=dispositions,
            inhibitions_by_ligand=inhibitions_by_ligand,
            dt_h=0.5 * dt,
        )

        for ligand in ligand_names:
            central[ligand], tissues[ligand] = _exchange_sweep(
                central[ligand],
                tissues[ligand],
                physiology=physiology,
                disposition=dispositions[ligand],
                dt=0.5 * dt,
                reverse=True,
            )

            accounted = (
                central[ligand]
                + sum(tissues[ligand].values())
                + eliminated[ligand]
            )
            error = accounted - initial_total[ligand]

            central_history[ligand].append(central[ligand])
            for tissue in physiology.tissue_map:
                tissue_history[ligand][tissue].append(
                    tissues[ligand][tissue]
                )
            eliminated_history[ligand].append(eliminated[ligand])
            error_history[ligand].append(error)

    traces = {}
    brain_volume = physiology.tissue_map["brain"].volume_l
    for ligand in ligand_names:
        central_arr = np.asarray(central_history[ligand], dtype=float)
        tissue_arrays = {
            tissue: np.asarray(values, dtype=float)
            for tissue, values in tissue_history[ligand].items()
        }
        brain_total = tissue_arrays["brain"] / brain_volume
        traces[ligand] = PBPKTrace(
            times_h=np.asarray(times, dtype=float),
            central_amount=central_arr,
            tissue_amounts=tissue_arrays,
            eliminated_amount=np.asarray(
                eliminated_history[ligand], dtype=float
            ),
            cumulative_input=np.zeros(len(times), dtype=float),
            mass_balance_error=np.asarray(
                error_history[ligand], dtype=float
            ),
            central_concentration=(
                central_arr / physiology.central_volume_l
            ),
            brain_total_concentration=brain_total,
            brain_free_concentration=(
                brain_total
                * dispositions[ligand].brain_unbound_fraction
            ),
        )

    return traces
