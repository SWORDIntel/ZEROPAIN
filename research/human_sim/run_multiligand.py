"""Synthetic multi-ligand HumanSim receptor-competition demonstration.

All amounts, affinities, partition values and efficacies are synthetic research units.
There is no clinical dose mapping.
"""

from __future__ import annotations

import argparse

from research.human_sim.competition import LigandInteraction
from research.human_sim.coupled_pbpk_reference import simulate_coupled_pbpk_reference
from research.human_sim.disposition import CompoundDisposition, synthetic_reference_disposition
from research.human_sim.multiligand_engine import LigandSpec, simulate_multiligand_chain
from research.human_sim.physiology import synthetic_reference_physiology
from research.human_sim.transporter_competition import TransporterInhibition
from research.human_sim.transporters import TransporterProcess
from zeropain.verified_io import write_json


def _ligand(name: str, *, kd: float, efficacy: float) -> LigandSpec:
    base = synthetic_reference_disposition()
    disposition = CompoundDisposition(
        label=f"{name}_SYNTH",
        tissue_partition_coefficients=dict(base.tissue_partition_coefficients),
        hepatic_clearance_l_per_h=base.hepatic_clearance_l_per_h,
        renal_clearance_l_per_h=base.renal_clearance_l_per_h,
        plasma_unbound_fraction=base.plasma_unbound_fraction,
        brain_unbound_fraction=base.brain_unbound_fraction,
        evidence_status="synthetic_fixture",
    )
    return LigandSpec(
        name=name,
        disposition=disposition,
        target_interactions={
            "MOR_SYNTH": LigandInteraction(
                ligand_name=name,
                kd_concentration=kd,
                efficacy=efficacy,
            )
        },
    )


def _transport_ligands() -> tuple[LigandSpec, LigandSpec]:
    victim, inhibitor = _transport_ligands()

    transport_control = simulate_multiligand_chain(
        physiology,
        {"victim": victim},
        initial_central_amounts={"victim": 1.0},
        duration_h=args.duration_h,
        dt_h=args.dt_h,
    )
    transport_inhibited = simulate_multiligand_chain(
        physiology,
        {"victim": victim, "inhibitor": inhibitor},
        initial_central_amounts={"victim": 1.0, "inhibitor": 1.0},
        duration_h=args.duration_h,
        dt_h=args.dt_h,
    )

    transport_payload = {
        "control_victim_final_central": float(
            transport_control.pbpk_by_ligand["victim"].central_amount[-1]
        ),
        "inhibited_victim_final_central": float(
            transport_inhibited.pbpk_by_ligand["victim"].central_amount[-1]
        ),
        "control_victim_final_liver": float(
            transport_control.pbpk_by_ligand["victim"].tissue_amounts["liver"][-1]
        ),
        "inhibited_victim_final_liver": float(
            transport_inhibited.pbpk_by_ligand["victim"].tissue_amounts["liver"][-1]
        ),
        "control_mass_error": float(
            abs(transport_control.pbpk_by_ligand["victim"].mass_balance_error).max()
        ),
        "inhibited_mass_error": float(
            max(
                abs(trace.mass_balance_error).max()
                for trace in transport_inhibited.pbpk_by_ligand.values()
            )
        ),
    }

    return {
        "schema_version": 1,
        "model": "human_sim_multiligand_competition",
        "warning": (
            "Synthetic arbitrary-unit demonstration only. "
            "No human dosing or validated pharmacology."
        ),
        "control": control.summary(),
        "competition": competed.summary(),
        "transporter_ddi": transport_payload,
    }


def _relations(payload: dict):
    failures = []
    c = payload["control"]["targets"]["MOR_SYNTH"]
    x = payload["competition"]["targets"]["MOR_SYNTH"]
    if x["mean_signal_magnitude"] >= c["mean_signal_magnitude"]:
        failures.append("synthetic antagonist failed to reduce target signal")
    if x["minimum_unbound_fraction"] < 0.0:
        failures.append("negative unbound receptor fraction")
    for result_name in ("control", "competition"):
        for ligand, pbpk in payload[result_name]["ligands"].items():
            if pbpk["max_abs_mass_balance_error"] > 1e-8:
                failures.append(f"{result_name}.{ligand}: PBPK mass imbalance")

    ddi = payload["transporter_ddi"]
    if ddi["inhibited_victim_final_central"] <= ddi["control_victim_final_central"]:
        failures.append("transporter inhibitor failed to retain victim in central")
    if ddi["inhibited_victim_final_liver"] >= ddi["control_victim_final_liver"]:
        failures.append("transporter inhibitor failed to reduce victim liver uptake")
    if max(ddi["control_mass_error"], ddi["inhibited_mass_error"]) > 1e-8:
        failures.append("transporter DDI PBPK mass imbalance")
    return (not failures, "; ".join(failures))


def main() -> int:
    args = _parser().parse_args()
    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="human_sim.multiligand",
        relations=[_relations],
        replay=lambda: build_payload(args),
        independent=lambda value: _independent_transport_check(args, value),
    )
    control = payload["control"]["targets"]["MOR_SYNTH"]["mean_signal_magnitude"]
    competed = payload["competition"]["targets"]["MOR_SYNTH"]["mean_signal_magnitude"]
    print(f"Wrote multi-ligand result to {out}")
    print(f"control_signal={control:.5f} competed_signal={competed:.5f}")
    ddi = payload["transporter_ddi"]
    print(
        f"transporter_victim_central="
        f"{ddi['control_victim_final_central']:.5f}->"
        f"{ddi['inhibited_victim_final_central']:.5f} "
        f"liver={ddi['control_victim_final_liver']:.5f}->"
        f"{ddi['inhibited_victim_final_liver']:.5f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
