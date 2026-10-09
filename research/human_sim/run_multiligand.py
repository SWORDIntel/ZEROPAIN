"""Synthetic multi-ligand HumanSim receptor and transporter competition demo.

All amounts, affinities, partition values and efficacies are synthetic research units.
There is no clinical dose mapping.
"""

from __future__ import annotations

import argparse

from research.human_sim.competition import LigandInteraction
from research.human_sim.coupled_pbpk_reference import simulate_coupled_pbpk_reference
from research.human_sim.disposition import (
    CompoundDisposition,
    synthetic_reference_disposition,
)
from research.human_sim.multiligand_engine import (
    LigandSpec,
    simulate_multiligand_chain,
)
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
    base = synthetic_reference_disposition()

    victim = LigandSpec(
        name="victim",
        disposition=CompoundDisposition(
            label="victim_transport_SYNTH",
            tissue_partition_coefficients=dict(base.tissue_partition_coefficients),
            plasma_unbound_fraction=0.5,
            brain_unbound_fraction=0.5,
            transporter_processes=(
                TransporterProcess(
                    name="victim_oatp_like",
                    route="hepatic_uptake",
                    vmax_amount_per_h=0.30,
                    km_concentration=0.05,
                    source_id="synthetic_fixture",
                    transporter_family="OATP1B1-like",
                    interaction_group="hepatic_OATP1B1",
                ),
            ),
            evidence_status="synthetic_fixture",
        ),
        target_interactions={
            "PK_DIAGNOSTIC_TARGET": LigandInteraction(
                ligand_name="victim",
                kd_concentration=1.0,
                efficacy=0.0,
            )
        },
    )

    inhibitor = LigandSpec(
        name="inhibitor",
        disposition=CompoundDisposition(
            label="inhibitor_transport_SYNTH",
            tissue_partition_coefficients=dict(base.tissue_partition_coefficients),
            plasma_unbound_fraction=0.5,
            brain_unbound_fraction=0.5,
            evidence_status="synthetic_fixture",
        ),
        target_interactions={
            "PK_DIAGNOSTIC_TARGET": LigandInteraction(
                ligand_name="inhibitor",
                kd_concentration=10.0,
                efficacy=0.0,
            )
        },
        transporter_inhibitions=(
            TransporterInhibition(
                inhibitor_name="inhibitor",
                interaction_group="hepatic_OATP1B1",
                ki_concentration=0.03,
                source_id="synthetic_fixture",
            ),
        ),
    )

    return victim, inhibitor


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-h", type=float, default=4.0)
    p.add_argument("--dt-h", type=float, default=0.05)
    p.add_argument("--output", default="runs/human_sim_multiligand.json")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    physiology = synthetic_reference_physiology()

    # Receptor-level competition control.
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

    # Transporter-mediated PK interaction control.
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
            abs(
                transport_control.pbpk_by_ligand["victim"].mass_balance_error
            ).max()
        ),
        "inhibited_mass_error": float(
            max(
                abs(trace.mass_balance_error).max()
                for trace in transport_inhibited.pbpk_by_ligand.values()
            )
        ),
        "victim_central_max_abs_difference": float(
            abs(
                transport_inhibited.pbpk_by_ligand["victim"].central_amount
                - transport_control.pbpk_by_ligand["victim"].central_amount
            ).max()
        ),
    }

    return {
        "schema_version": 2,
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

    control_target = payload["control"]["targets"]["MOR_SYNTH"]
    competed_target = payload["competition"]["targets"]["MOR_SYNTH"]
    if (
        competed_target["mean_signal_magnitude"]
        >= control_target["mean_signal_magnitude"]
    ):
        failures.append("synthetic antagonist failed to reduce target signal")
    if competed_target["minimum_unbound_fraction"] < 0.0:
        failures.append("negative unbound receptor fraction")

    for result_name in ("control", "competition"):
        for ligand, pbpk in payload[result_name]["ligands"].items():
            if pbpk["max_abs_mass_balance_error"] > 1e-8:
                failures.append(
                    f"{result_name}.{ligand}: PBPK mass imbalance"
                )

    ddi = payload["transporter_ddi"]
    if ddi["victim_central_max_abs_difference"] < 1e-8:
        failures.append(
            "transporter inhibitor failed to change victim central trajectory"
        )
    if (
        ddi["inhibited_victim_final_liver"]
        >= ddi["control_victim_final_liver"]
    ):
        failures.append(
            "transporter inhibitor failed to reduce victim liver uptake"
        )
    if max(ddi["control_mass_error"], ddi["inhibited_mass_error"]) > 1e-8:
        failures.append("transporter DDI PBPK mass imbalance")

    return (not failures, "; ".join(failures))


def _reference_close(observed: float, expected: float) -> bool:
    tolerance = max(1e-5, 0.05 * max(abs(expected), 1e-8))
    return abs(observed - expected) <= tolerance


def _independent_transport_check(
    args: argparse.Namespace,
    payload: dict,
):
    physiology = synthetic_reference_physiology()
    victim, inhibitor = _transport_ligands()

    control = simulate_coupled_pbpk_reference(
        physiology,
        {"victim": victim.disposition},
        initial_central_amounts={"victim": 1.0},
        duration_h=args.duration_h,
        output_dt_h=args.dt_h,
        substeps=30,
    )

    inhibited = simulate_coupled_pbpk_reference(
        physiology,
        {
            "victim": victim.disposition,
            "inhibitor": inhibitor.disposition,
        },
        initial_central_amounts={"victim": 1.0, "inhibitor": 1.0},
        duration_h=args.duration_h,
        output_dt_h=args.dt_h,
        substeps=30,
        inhibitions_by_ligand={
            "inhibitor": inhibitor.transporter_inhibitions,
        },
    )

    expected = {
        "control_victim_final_central": float(
            control["victim"].central_amount[-1]
        ),
        "inhibited_victim_final_central": float(
            inhibited["victim"].central_amount[-1]
        ),
        "control_victim_final_liver": float(
            control["victim"].tissue_amounts["liver"][-1]
        ),
        "inhibited_victim_final_liver": float(
            inhibited["victim"].tissue_amounts["liver"][-1]
        ),
    }

    observed = payload["transporter_ddi"]
    failures = [
        f"{name}: production={observed[name]:.8g} reference={reference:.8g}"
        for name, reference in expected.items()
        if not _reference_close(float(observed[name]), reference)
    ]
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

    control = payload["control"]["targets"]["MOR_SYNTH"][
        "mean_signal_magnitude"
    ]
    competed = payload["competition"]["targets"]["MOR_SYNTH"][
        "mean_signal_magnitude"
    ]
    ddi = payload["transporter_ddi"]

    print(f"Wrote multi-ligand result to {out}")
    print(
        f"control_signal={control:.5f} "
        f"competed_signal={competed:.5f}"
    )
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
