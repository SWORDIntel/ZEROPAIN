"""Independent coupled-PBPK RK4 verifier for transporter DDIs.

This module intentionally re-derives transporter competition rather than calling
the production competitive transporter-rate function.

It verifies the same shared-site approximation:

    D_g = 1 + sum_substrates(Cu/Km) + sum_inhibitors(Cu/Ki)
    v_s = Vmax_s * (Cu_s/Km_s) / D_g

Perfusion, elimination and transporter terms are integrated together with classical
RK4 at a finer internal step.

This is a verification path, not the production multi-ligand solver.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import PBPKTrace
from research.human_sim.pbpk_reference import compare_to_reference
from research.human_sim.physiology import Physiology
from research.human_sim.transporter_competition import TransporterInhibition
from research.human_sim.transporters import TransportRoute


def _endpoints(route: TransportRoute) -> tuple[str, str]:
    return {
        TransportRoute.HEPATIC_UPTAKE: ("central", "liver"),
        TransportRoute.HEPATIC_EFFLUX_TO_BLOOD: ("liver", "central"),
        TransportRoute.BILIARY_EFFLUX: ("liver", "eliminated"),
        TransportRoute.RENAL_UPTAKE: ("central", "kidney"),
        TransportRoute.RENAL_EFFLUX_TO_URINE: ("kidney", "eliminated"),
        TransportRoute.TUBULAR_REABSORPTION: ("kidney", "central"),
    }[route]


def _source_concentration(
    *,
    source: str,
    central: float,
    tissue_amounts: Mapping[str, float],
    physiology: Physiology,
    disposition: CompoundDisposition,
    tissue_unbound_fraction: float | None,
) -> float:
    if source == "central":
        return float(
            central
            / physiology.central_volume_l
            * disposition.plasma_unbound_fraction
            / disposition.blood_to_plasma_ratio
        )
    if tissue_unbound_fraction is None:
        raise ValueError("tissue-source process missing source_unbound_fraction")
    return float(
        tissue_amounts[source]
        / physiology.tissue_map[source].volume_l
        * tissue_unbound_fraction
    )


def _inhibitor_concentration(
    inhibition: TransporterInhibition,
    *,
    central: float,
    tissue_amounts: Mapping[str, float],
    physiology: Physiology,
    disposition: CompoundDisposition,
) -> float:
    inhibition.validate(physiology)
    if inhibition.source_compartment == "central":
        return float(
            central
            / physiology.central_volume_l
            * disposition.plasma_unbound_fraction
            / disposition.blood_to_plasma_ratio
        )
    return float(
        tissue_amounts[inhibition.source_compartment]
        / physiology.tissue_map[inhibition.source_compartment].volume_l
        * float(inhibition.source_unbound_fraction)
    )


def _derivative(
    state: np.ndarray,
    *,
    physiology: Physiology,
    ligand_names: list[str],
    dispositions: Mapping[str, CompoundDisposition],
    inhibitions_by_ligand: Mapping[str, tuple[TransporterInhibition, ...]],
) -> np.ndarray:
    tissue_names = list(physiology.tissue_map)
    block = len(tissue_names) + 2
    d = np.zeros_like(state)

    central_by_ligand = {}
    tissue_by_ligand = {}

    for ligand_index, ligand in enumerate(ligand_names):
        offset = ligand_index * block
        central = float(state[offset])
        tissues = {
            tissue: float(state[offset + 1 + index])
            for index, tissue in enumerate(tissue_names)
        }
        central_by_ligand[ligand] = central
        tissue_by_ligand[ligand] = tissues

        disposition = dispositions[ligand]
        central_conc = central / physiology.central_volume_l

        for tissue_index, tissue_name in enumerate(tissue_names):
            tissue_spec = physiology.tissue_map[tissue_name]
            tissue_amount = tissues[tissue_name]
            tissue_conc = tissue_amount / tissue_spec.volume_l
            kp = disposition.tissue_partition_coefficients[tissue_name]
            flux = tissue_spec.blood_flow_l_per_h * (
                central_conc - tissue_conc / kp
            )
            d[offset] -= flux
            d[offset + 1 + tissue_index] += flux

            if tissue_name == "liver":
                if disposition.hepatic_clearance_l_per_h > 0:
                    cleared = (
                        disposition.hepatic_clearance_l_per_h * tissue_conc
                    )
                    d[offset + 1 + tissue_index] -= cleared
                    d[offset + block - 1] += cleared

                if (
                    disposition.hepatic_intrinsic_unbound_clearance_l_per_h > 0
                ):
                    cleared = (
                        disposition.hepatic_intrinsic_unbound_clearance_l_per_h
                        * float(disposition.liver_unbound_fraction)
                        * tissue_conc
                    )
                    d[offset + 1 + tissue_index] -= cleared
                    d[offset + block - 1] += cleared

            if (
                tissue_name == "kidney"
                and disposition.renal_clearance_l_per_h > 0
            ):
                cleared = disposition.renal_clearance_l_per_h * tissue_conc
                d[offset + 1 + tissue_index] -= cleared
                d[offset + block - 1] += cleared

        if disposition.renal_gfr_l_per_h > 0:
            cu_plasma = (
                central_conc
                * disposition.plasma_unbound_fraction
                / disposition.blood_to_plasma_ratio
            )
            filtered = disposition.renal_gfr_l_per_h * cu_plasma
            d[offset] -= filtered
            d[offset + block - 1] += filtered

    substrate_records = []
    grouped: dict[str, list[dict]] = {}

    for ligand in ligand_names:
        disposition = dispositions[ligand]
        for process in disposition.transporter_processes:
            process.validate()
            route = TransportRoute(process.route)
            source, sink = _endpoints(route)
            concentration = _source_concentration(
                source=source,
                central=central_by_ligand[ligand],
                tissue_amounts=tissue_by_ligand[ligand],
                physiology=physiology,
                disposition=disposition,
                tissue_unbound_fraction=process.source_unbound_fraction,
            )
            record = {
                "ligand": ligand,
                "process": process,
                "source": source,
                "sink": sink,
                "concentration": concentration,
            }
            substrate_records.append(record)
            if process.interaction_group:
                grouped.setdefault(process.interaction_group, []).append(record)

    inhibitor_weight = {}
    inhibitors_by_group: dict[str, set[str]] = {}
    for ligand, inhibitions in inhibitions_by_ligand.items():
        if ligand not in dispositions:
            raise ValueError(f"unknown inhibitor ligand: {ligand}")
        for inhibition in inhibitions:
            if inhibition.inhibitor_name != ligand:
                raise ValueError("inhibitor mapping/name mismatch")
            concentration = _inhibitor_concentration(
                inhibition,
                central=central_by_ligand[ligand],
                tissue_amounts=tissue_by_ligand[ligand],
                physiology=physiology,
                disposition=dispositions[ligand],
            )
            group = inhibition.interaction_group
            inhibitor_weight[group] = inhibitor_weight.get(group, 0.0) + (
                concentration / inhibition.ki_concentration
            )
            inhibitors_by_group.setdefault(group, set()).add(ligand)

    denominator = {}
    for group, records in grouped.items():
        substrates = {record["ligand"] for record in records}
        overlap = substrates & inhibitors_by_group.get(group, set())
        if overlap:
            raise ValueError(
                f"substrate/inhibitor double count in group {group}: {sorted(overlap)}"
            )
        substrate_weight = sum(
            record["concentration"] / record["process"].km_concentration
            for record in records
        )
        denominator[group] = (
            1.0 + substrate_weight + inhibitor_weight.get(group, 0.0)
        )

    ligand_index = {name: index for index, name in enumerate(ligand_names)}
    tissue_index = {name: index for index, name in enumerate(tissue_names)}

    for record in substrate_records:
        ligand = record["ligand"]
        process = record["process"]
        concentration = record["concentration"]
        weight = concentration / process.km_concentration

        if process.interaction_group:
            denom = denominator[process.interaction_group]
            rate = (
                process.vmax_amount_per_h * weight / denom
                if weight > 0 and process.vmax_amount_per_h > 0
                else 0.0
            )
        else:
            rate = (
                process.vmax_amount_per_h
                * concentration
                / (process.km_concentration + concentration)
                if concentration > 0 and process.vmax_amount_per_h > 0
                else 0.0
            )

        offset = ligand_index[ligand] * block
        source = record["source"]
        sink = record["sink"]

        if source == "central":
            d[offset] -= rate
        else:
            d[offset + 1 + tissue_index[source]] -= rate

        if sink == "central":
            d[offset] += rate
        elif sink == "eliminated":
            d[offset + block - 1] += rate
        else:
            d[offset + 1 + tissue_index[sink]] += rate

    return d


def simulate_coupled_pbpk_reference(
    physiology: Physiology,
    dispositions: Mapping[str, CompoundDisposition],
    *,
    initial_central_amounts: Mapping[str, float],
    duration_h: float,
    output_dt_h: float,
    substeps: int = 25,
    inhibitions_by_ligand: Mapping[str, tuple[TransporterInhibition, ...]] | None = None,
) -> dict[str, PBPKTrace]:
    physiology.validate()
    ligand_names = list(dispositions)
    if not ligand_names:
        raise ValueError("at least one disposition is required")
    if set(initial_central_amounts) != set(ligand_names):
        raise ValueError("initial amount ligand set mismatch")
    if duration_h <= 0 or output_dt_h <= 0:
        raise ValueError("duration_h and output_dt_h must be positive")
    if substeps < 2:
        raise ValueError("substeps must be >= 2")

    for disposition in dispositions.values():
        disposition.validate(set(physiology.tissue_map))

    inhibitions_by_ligand = dict(inhibitions_by_ligand or {})
    tissue_names = list(physiology.tissue_map)
    block = len(tissue_names) + 2

    n_outputs = int(np.ceil(duration_h / output_dt_h))
    times = np.minimum(np.arange(n_outputs + 1) * output_dt_h, duration_h)

    state = np.zeros(block * len(ligand_names), dtype=float)
    initial_totals = {}
    for index, ligand in enumerate(ligand_names):
        amount = float(initial_central_amounts[ligand])
        if amount < 0:
            raise ValueError("initial central amounts cannot be negative")
        state[index * block] = amount
        initial_totals[ligand] = amount

    central_history = {ligand: [float(state[i * block])] for i, ligand in enumerate(ligand_names)}
    tissue_history = {
        ligand: {tissue: [0.0] for tissue in tissue_names}
        for ligand in ligand_names
    }
    eliminated_history = {ligand: [0.0] for ligand in ligand_names}
    error_history = {ligand: [0.0] for ligand in ligand_names}

    for output_index in range(n_outputs):
        t0 = float(times[output_index])
        t1 = float(times[output_index + 1])
        h = (t1 - t0) / substeps

        for _ in range(substeps):
            kwargs = dict(
                physiology=physiology,
                ligand_names=ligand_names,
                dispositions=dispositions,
                inhibitions_by_ligand=inhibitions_by_ligand,
            )
            k1 = _derivative(state, **kwargs)
            k2 = _derivative(state + 0.5 * h * k1, **kwargs)
            k3 = _derivative(state + 0.5 * h * k2, **kwargs)
            k4 = _derivative(state + h * k3, **kwargs)
            state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            if np.min(state) < -1e-8:
                raise RuntimeError(
                    "coupled reference RK4 produced negative amount"
                )
            state = np.maximum(state, 0.0)

        for ligand_index, ligand in enumerate(ligand_names):
            offset = ligand_index * block
            central = float(state[offset])
            central_history[ligand].append(central)
            tissue_total = 0.0
            for index, tissue in enumerate(tissue_names):
                amount = float(state[offset + 1 + index])
                tissue_history[ligand][tissue].append(amount)
                tissue_total += amount
            eliminated = float(state[offset + block - 1])
            eliminated_history[ligand].append(eliminated)
            error_history[ligand].append(
                central + tissue_total + eliminated - initial_totals[ligand]
            )

    traces = {}
    for ligand_index, ligand in enumerate(ligand_names):
        disposition = dispositions[ligand]
        central = np.asarray(central_history[ligand], dtype=float)
        tissue_arrays = {
            tissue: np.asarray(values, dtype=float)
            for tissue, values in tissue_history[ligand].items()
        }
        brain_total = (
            tissue_arrays["brain"]
            / physiology.tissue_map["brain"].volume_l
        )
        traces[ligand] = PBPKTrace(
            times_h=np.asarray(times, dtype=float),
            central_amount=central,
            tissue_amounts=tissue_arrays,
            eliminated_amount=np.asarray(
                eliminated_history[ligand], dtype=float
            ),
            cumulative_input=np.zeros(len(times), dtype=float),
            mass_balance_error=np.asarray(
                error_history[ligand], dtype=float
            ),
            central_concentration=(
                central / physiology.central_volume_l
            ),
            brain_total_concentration=brain_total,
            brain_free_concentration=(
                brain_total * disposition.brain_unbound_fraction
            ),
        )

    return traces


def compare_coupled_to_reference(
    primary: Mapping[str, PBPKTrace],
    reference: Mapping[str, PBPKTrace],
) -> dict:
    if set(primary) != set(reference):
        raise ValueError("primary/reference ligand sets differ")

    by_ligand = {
        ligand: compare_to_reference(primary[ligand], reference[ligand]).to_dict()
        for ligand in primary
    }
    return {
        "by_ligand": by_ligand,
        "max_metric": max(
            metrics["max_metric"]
            for metrics in by_ligand.values()
        ),
    }
