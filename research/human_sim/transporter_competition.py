"""Competitive multi-compound transporter interactions for HumanSim.

This module adds shared-transporter coupling without changing the single-compound
transporter path.

Substrates compete automatically when their TransporterProcess objects share the same
non-empty interaction_group.

For one shared site:

    substrate_weight_j = Cu_j / Km_j
    inhibitor_weight_k = Cu_k / Ki_k
    D = 1 + sum_j substrate_weight_j + sum_k inhibitor_weight_k
    rate_j = Vmax_j * substrate_weight_j / D

A compound already present as a substrate in a group must not also be listed as an
explicit inhibitor for that same group; its substrate weight already contributes
competitive occupancy.

Ungrouped transporter processes keep ordinary Michaelis-Menten kinetics.

This is a competitive shared-site approximation. It does not model noncompetitive,
uncompetitive, mixed, time-dependent, induction, or transporter-abundance effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.physiology import Physiology
from research.human_sim.transporters import (
    TransportFlux,
    TransportRoute,
    TransporterProcess,
    _route_endpoints,
    _source_unbound_concentration,
    michaelis_menten_rate,
)


@dataclass(frozen=True)
class TransporterInhibition:
    inhibitor_name: str
    interaction_group: str
    ki_concentration: float
    source_compartment: str = "central"
    source_unbound_fraction: float | None = None
    source_id: str = ""
    mode: str = "competitive"

    def validate(self, physiology: Physiology | None = None) -> None:
        if not self.inhibitor_name:
            raise ValueError("inhibitor_name cannot be blank")
        if not self.interaction_group:
            raise ValueError("interaction_group cannot be blank")
        if self.ki_concentration <= 0:
            raise ValueError("ki_concentration must be positive")
        if self.mode != "competitive":
            raise ValueError("only competitive transporter inhibition is supported")
        if not self.source_id:
            raise ValueError("source_id cannot be blank")
        if self.source_compartment != "central":
            if physiology is not None and self.source_compartment not in physiology.tissue_map:
                raise ValueError(
                    f"unknown inhibitor source compartment: {self.source_compartment}"
                )
            if self.source_unbound_fraction is None:
                raise ValueError(
                    "tissue-source inhibitor requires source_unbound_fraction"
                )
            if not 0.0 < self.source_unbound_fraction <= 1.0:
                raise ValueError("source_unbound_fraction must be in (0,1]")
        elif self.source_unbound_fraction is not None:
            if not 0.0 < self.source_unbound_fraction <= 1.0:
                raise ValueError("source_unbound_fraction must be in (0,1]")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompetitiveTransportFlux:
    ligand_name: str
    process: str
    route: str
    source: str
    sink: str
    interaction_group: str
    source_unbound_concentration: float
    substrate_weight: float
    inhibitor_weight: float
    denominator: float
    requested_amount: float
    transferred_amount: float

    def to_dict(self) -> dict:
        return asdict(self)


def _inhibitor_unbound_concentration(
    inhibition: TransporterInhibition,
    *,
    central_amount: float,
    tissue_amounts: Mapping[str, float],
    physiology: Physiology,
    disposition: CompoundDisposition,
) -> float:
    inhibition.validate(physiology)

    if inhibition.source_compartment == "central":
        blood_concentration = central_amount / physiology.central_volume_l
        return float(
            blood_concentration
            * disposition.plasma_unbound_fraction
            / disposition.blood_to_plasma_ratio
        )

    tissue = physiology.tissue_map[inhibition.source_compartment]
    total = tissue_amounts[inhibition.source_compartment] / tissue.volume_l
    return float(total * float(inhibition.source_unbound_fraction))


def competitive_transporter_flux_rates(
    *,
    central_amounts: Mapping[str, float],
    tissue_amounts_by_ligand: Mapping[str, Mapping[str, float]],
    physiology: Physiology,
    dispositions: Mapping[str, CompoundDisposition],
    inhibitions_by_ligand: Mapping[str, tuple[TransporterInhibition, ...]] | None = None,
) -> tuple[CompetitiveTransportFlux, ...]:
    """Return instantaneous amount/hour rates for all ligands."""

    ligand_names = set(dispositions)
    if set(central_amounts) != ligand_names:
        raise ValueError("central amount ligand set must match dispositions")
    if set(tissue_amounts_by_ligand) != ligand_names:
        raise ValueError("tissue amount ligand set must match dispositions")

    inhibitions_by_ligand = dict(inhibitions_by_ligand or {})
    unknown_inhibitors = set(inhibitions_by_ligand) - ligand_names
    if unknown_inhibitors:
        raise ValueError(
            f"inhibition entries for unknown ligands: {sorted(unknown_inhibitors)}"
        )

    substrate_records = []
    grouped: dict[str, list[dict]] = {}

    for ligand_name, disposition in dispositions.items():
        disposition.validate(set(physiology.tissue_map))
        tissues = tissue_amounts_by_ligand[ligand_name]

        for process in disposition.transporter_processes:
            process.validate()
            route = TransportRoute(process.route)
            source, sink = _route_endpoints(route)
            concentration = _source_unbound_concentration(
                process,
                source=source,
                central_amount=float(central_amounts[ligand_name]),
                tissue_amounts=tissues,
                physiology=physiology,
                plasma_unbound_fraction=disposition.plasma_unbound_fraction,
                blood_to_plasma_ratio=disposition.blood_to_plasma_ratio,
            )
            record = {
                "ligand_name": ligand_name,
                "process": process,
                "route": route,
                "source": source,
                "sink": sink,
                "concentration": concentration,
            }
            substrate_records.append(record)
            if process.interaction_group:
                grouped.setdefault(process.interaction_group, []).append(record)

    inhibitor_weights: dict[str, float] = {}
    explicit_inhibitors_by_group: dict[str, set[str]] = {}

    for ligand_name, inhibitions in inhibitions_by_ligand.items():
        disposition = dispositions[ligand_name]
        for inhibition in inhibitions:
            if inhibition.inhibitor_name != ligand_name:
                raise ValueError(
                    f"inhibition key {ligand_name!r} disagrees with "
                    f"inhibitor_name {inhibition.inhibitor_name!r}"
                )
            inhibition.validate(physiology)
            concentration = _inhibitor_unbound_concentration(
                inhibition,
                central_amount=float(central_amounts[ligand_name]),
                tissue_amounts=tissue_amounts_by_ligand[ligand_name],
                physiology=physiology,
                disposition=disposition,
            )
            group = inhibition.interaction_group
            inhibitor_weights[group] = inhibitor_weights.get(group, 0.0) + (
                concentration / inhibition.ki_concentration
            )
            explicit_inhibitors_by_group.setdefault(group, set()).add(ligand_name)

    for group, records in grouped.items():
        substrate_ligands = {record["ligand_name"] for record in records}
        overlap = substrate_ligands & explicit_inhibitors_by_group.get(group, set())
        if overlap:
            raise ValueError(
                f"ligands cannot be both substrate and explicit inhibitor in "
                f"interaction group {group!r}: {sorted(overlap)}"
            )

    group_denominators: dict[str, tuple[float, float]] = {}
    for group, records in grouped.items():
        substrate_weight = sum(
            record["concentration"] / record["process"].km_concentration
            for record in records
        )
        inhibitor_weight = inhibitor_weights.get(group, 0.0)
        group_denominators[group] = (
            1.0 + substrate_weight + inhibitor_weight,
            inhibitor_weight,
        )

    fluxes = []
    for record in substrate_records:
        ligand_name = record["ligand_name"]
        process: TransporterProcess = record["process"]
        concentration = float(record["concentration"])

        if process.interaction_group:
            substrate_weight = concentration / process.km_concentration
            denominator, inhibitor_weight = group_denominators[
                process.interaction_group
            ]
            rate = (
                process.vmax_amount_per_h * substrate_weight / denominator
                if substrate_weight > 0 and process.vmax_amount_per_h > 0
                else 0.0
            )
        else:
            substrate_weight = concentration / process.km_concentration
            inhibitor_weight = 0.0
            denominator = 1.0 + substrate_weight
            rate = michaelis_menten_rate(
                concentration,
                vmax_amount_per_h=process.vmax_amount_per_h,
                km_concentration=process.km_concentration,
            )

        fluxes.append(
            CompetitiveTransportFlux(
                ligand_name=ligand_name,
                process=process.name,
                route=record["route"].value,
                source=record["source"],
                sink=record["sink"],
                interaction_group=process.interaction_group,
                source_unbound_concentration=concentration,
                substrate_weight=float(substrate_weight),
                inhibitor_weight=float(inhibitor_weight),
                denominator=float(denominator),
                requested_amount=float(rate),
                transferred_amount=float(rate),
            )
        )

    return tuple(fluxes)


def apply_competitive_transporter_step(
    *,
    central_amounts: Mapping[str, float],
    tissue_amounts_by_ligand: Mapping[str, Mapping[str, float]],
    eliminated_amounts: Mapping[str, float],
    physiology: Physiology,
    dispositions: Mapping[str, CompoundDisposition],
    inhibitions_by_ligand: Mapping[str, tuple[TransporterInhibition, ...]] | None = None,
    dt_h: float,
) -> tuple[
    dict[str, float],
    dict[str, dict[str, float]],
    dict[str, float],
    tuple[CompetitiveTransportFlux, ...],
]:
    """Apply a shared-site competitive transporter operator for one timestep."""

    if dt_h < 0:
        raise ValueError("dt_h cannot be negative")
    ligand_names = set(dispositions)
    if set(eliminated_amounts) != ligand_names:
        raise ValueError("eliminated amount ligand set must match dispositions")

    rates = competitive_transporter_flux_rates(
        central_amounts=central_amounts,
        tissue_amounts_by_ligand=tissue_amounts_by_ligand,
        physiology=physiology,
        dispositions=dispositions,
        inhibitions_by_ligand=inhibitions_by_ligand,
    )

    central = {name: float(value) for name, value in central_amounts.items()}
    tissues = {
        ligand: {name: float(value) for name, value in amounts.items()}
        for ligand, amounts in tissue_amounts_by_ligand.items()
    }
    eliminated = {
        name: float(value) for name, value in eliminated_amounts.items()
    }

    outgoing: dict[tuple[str, str], float] = {}
    requested = []
    for flux in rates:
        amount = flux.requested_amount * dt_h
        key = (flux.ligand_name, flux.source)
        outgoing[key] = outgoing.get(key, 0.0) + amount
        requested.append((flux, amount))

    def available(ligand: str, source: str) -> float:
        return central[ligand] if source == "central" else tissues[ligand][source]

    scales = {
        key: (
            1.0
            if amount <= available(*key) or amount <= 0
            else available(*key) / amount
        )
        for key, amount in outgoing.items()
    }

    applied = []
    before = {
        ligand: (
            central[ligand]
            + sum(tissues[ligand].values())
            + eliminated[ligand]
        )
        for ligand in ligand_names
    }

    for flux, amount in requested:
        ligand = flux.ligand_name
        moved = float(amount * scales[(ligand, flux.source)])

        if flux.source == "central":
            central[ligand] -= moved
        else:
            tissues[ligand][flux.source] -= moved

        if flux.sink == "central":
            central[ligand] += moved
        elif flux.sink == "eliminated":
            eliminated[ligand] += moved
        else:
            tissues[ligand][flux.sink] += moved

        applied.append(
            CompetitiveTransportFlux(
                ligand_name=flux.ligand_name,
                process=flux.process,
                route=flux.route,
                source=flux.source,
                sink=flux.sink,
                interaction_group=flux.interaction_group,
                source_unbound_concentration=flux.source_unbound_concentration,
                substrate_weight=flux.substrate_weight,
                inhibitor_weight=flux.inhibitor_weight,
                denominator=flux.denominator,
                requested_amount=float(amount),
                transferred_amount=moved,
            )
        )

    for ligand in ligand_names:
        if central[ligand] < -1e-10:
            raise RuntimeError(f"{ligand}: competitive transport made central negative")
        if any(value < -1e-10 for value in tissues[ligand].values()):
            raise RuntimeError(f"{ligand}: competitive transport made tissue negative")
        central[ligand] = max(central[ligand], 0.0)
        tissues[ligand] = {
            name: max(value, 0.0)
            for name, value in tissues[ligand].items()
        }

        after = (
            central[ligand]
            + sum(tissues[ligand].values())
            + eliminated[ligand]
        )
        if not np.isclose(before[ligand], after, rtol=0.0, atol=1e-10):
            raise RuntimeError(
                f"{ligand}: competitive transporter mass balance failure "
                f"before={before[ligand]} after={after}"
            )

    return central, tissues, eliminated, tuple(applied)
