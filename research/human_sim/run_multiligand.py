"""Synthetic multi-ligand HumanSim receptor-competition demonstration.

All amounts, affinities, partition values and efficacies are synthetic research units.
There is no clinical dose mapping.
"""

from __future__ import annotations

import argparse

from research.human_sim.competition import LigandInteraction
from research.human_sim.disposition import CompoundDisposition, synthetic_reference_disposition
from research.human_sim.multiligand_engine import LigandSpec, simulate_multiligand_chain
from research.human_sim.physiology import synthetic_reference_physiology
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


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-h", type=float, default=4.0)
    p.add_argument("--dt-h", type=float, default=0.05)
    p.add_argument("--output", default="runs/human_sim_multiligand.json")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    physiology = synthetic_reference_physiology()
    agonist = _ligand("agonist", kd=0.15, efficacy=0.8)
    antagonist = _ligand("antagonist", kd=0.05, efficacy=0.0)

    control = simulate_multiligand_chain(
        physiology,
        {"agonist": agonist},
        initial_central_amounts={"agonist": 1.0},
        duration_h=args.duration_h,
        dt_h=args.dt_h,
    )
    competed = simulate_multiligand_chain(
        physiology,
        {"agonist": agonist, "antagonist": antagonist},
        initial_central_amounts={"agonist": 1.0, "antagonist": 1.0},
        duration_h=args.duration_h,
        dt_h=args.dt_h,
    )

    return {
        "schema_version": 1,
        "model": "human_sim_multiligand_competition",
        "warning": (
            "Synthetic arbitrary-unit demonstration only. "
            "No human dosing or validated pharmacology."
        ),
        "control": control.summary(),
        "competition": competed.summary(),
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
    )
    control = payload["control"]["targets"]["MOR_SYNTH"]["mean_signal_magnitude"]
    competed = payload["competition"]["targets"]["MOR_SYNTH"]["mean_signal_magnitude"]
    print(f"Wrote multi-ligand result to {out}")
    print(f"control_signal={control:.5f} competed_signal={competed:.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
