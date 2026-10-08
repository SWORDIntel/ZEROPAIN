"""Normalize an external compound-disposition prediction into HumanSim.

The partition CSV may come from httk/Schmitt, PK-Sim, measured data, or another
backend as long as its coefficient basis and provenance are explicit.

No dose input is accepted. Intrinsic clearance, if supplied, must already be a
whole-liver L/h quantity and is used only for a well-stirred reference diagnostic.
"""

from __future__ import annotations

import argparse

from research.human_sim.external_disposition import (
    ExternalDispositionInputs,
    build_external_disposition,
)
from research.human_sim.partition_import import load_partition_csv
from research.human_sim.reference_physiology import adult_male_reference_composite
from research.human_sim.provenance import sources_dict
from zeropain.verified_io import write_json


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("partition_csv")
    p.add_argument("--label", default="external_compound")
    p.add_argument("--fu-plasma", type=float, required=True)
    p.add_argument("--fu-brain", type=float, required=True)
    p.add_argument("--blood-to-plasma", type=float, default=1.0)
    p.add_argument("--kp-uu-brain", type=float)
    p.add_argument(
        "--fu-liver",
        type=float,
        help=(
            "Unbound fraction in liver tissue. Required before intrinsic hepatic "
            "clearance is allowed to drive the PBPK liver elimination operator."
        ),
    )
    p.add_argument(
        "--intrinsic-hepatic-clearance-lph",
        type=float,
        help="Whole-liver intrinsic clearance in L/h; diagnostic only.",
    )
    p.add_argument(
        "--gfr-lph",
        type=float,
        help="GFR in L/h for filtration-only renal reference; diagnostic only.",
    )
    p.add_argument("--output", default="runs/human_sim_external_disposition.json")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    table = load_partition_csv(args.partition_csv)
    physiology = adult_male_reference_composite().physiology

    inputs = ExternalDispositionInputs(
        label=args.label,
        tissue_partition_coefficients=table.tissue_partition_coefficients,
        partition_basis=table.basis,
        fu_plasma=args.fu_plasma,
        fu_brain=args.fu_brain,
        source_id=table.source_id,
        method=table.method,
        blood_to_plasma_ratio=args.blood_to_plasma,
        kp_uu_brain=args.kp_uu_brain,
        intrinsic_hepatic_clearance_l_per_h=args.intrinsic_hepatic_clearance_lph,
        gfr_l_per_h=args.gfr_lph,
        fu_liver=args.fu_liver,
    )
    result = build_external_disposition(physiology, inputs)

    evidence_ids = [
        "schmitt_partitioning",
        "loryan2022_kpuu",
        "pang2019_clearance",
    ]
    if table.source_id == "httk_schmitt":
        evidence_ids.append("httk_schmitt")
    elif table.source_id == "synthetic_fixture":
        evidence_ids.append("synthetic_fixture")

    return {
        "schema_version": 1,
        "model": "human_sim_external_disposition_normalization",
        "warning": (
            "Partition normalization and reference-clearance diagnostics only. "
            "No clinical dose conversion. Well-stirred/filtration clearances are not "
            "silently copied into tissue-concentration PBPK elimination fields."
        ),
        "physiology": physiology.to_dict(),
        "partition_input": table.to_dict(),
        "input": {
            "label": args.label,
            "fu_plasma": args.fu_plasma,
            "fu_brain": args.fu_brain,
            "blood_to_plasma": args.blood_to_plasma,
            "kp_uu_brain": args.kp_uu_brain,
            "intrinsic_hepatic_clearance_lph": args.intrinsic_hepatic_clearance_lph,
            "gfr_lph": args.gfr_lph,
            "fu_liver": args.fu_liver,
        },
        "result": result.to_dict(),
        "evidence": sources_dict(evidence_ids),
    }


def _relations(payload: dict):
    failures = []
    result = payload["result"]
    disposition = result["disposition"]

    for tissue, value in disposition["tissue_partition_coefficients"].items():
        if value <= 0:
            failures.append(f"{tissue}: normalized Kp not positive")

    if disposition["hepatic_clearance_l_per_h"] != 0.0:
        failures.append("reference hepatic clearance leaked into PBPK tissue field")
    if disposition["renal_clearance_l_per_h"] != 0.0:
        failures.append("reference renal clearance leaked into PBPK tissue field")
    if (
        payload["input"]["gfr_lph"] is not None
        and disposition["renal_gfr_l_per_h"] != payload["input"]["gfr_lph"]
    ):
        failures.append("GFR did not reach dedicated PBPK filtration field")
    if (
        payload["input"]["fu_liver"] is None
        and disposition["hepatic_intrinsic_unbound_clearance_l_per_h"] != 0.0
    ):
        failures.append("intrinsic hepatic clearance activated without fu_liver")

    hepatic = result["diagnostics"]["well_stirred_hepatic_reference"]
    if hepatic is not None and not 0.0 <= hepatic["extraction_ratio"] <= 1.0:
        failures.append("hepatic extraction ratio outside [0,1]")

    renal = result["diagnostics"]["filtration_only_renal_reference"]
    if renal is not None and not 0.0 <= renal["extraction_ratio"] <= 1.0:
        failures.append("filtration extraction fraction outside [0,1]")

    return (not failures, "; ".join(failures))


def main() -> int:
    args = _parser().parse_args()
    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="human_sim.external_disposition",
        relations=[_relations],
        replay=lambda: build_payload(args),
        metadata={"partition_csv": args.partition_csv},
    )

    disposition = payload["result"]["disposition"]
    diagnostics = payload["result"]["diagnostics"]
    print(f"Wrote normalized external disposition to {out}")
    print(
        "Kp "
        + " ".join(
            f"{name}={value:.6g}"
            for name, value in disposition["tissue_partition_coefficients"].items()
        )
    )
    if diagnostics["well_stirred_hepatic_reference"] is not None:
        hepatic = diagnostics["well_stirred_hepatic_reference"]
        print(
            f"well_stirred_reference={hepatic['clearance_l_per_h']:.6g} L/h "
            f"ER={hepatic['extraction_ratio']:.4f}"
        )
    if diagnostics["filtration_only_renal_reference"] is not None:
        renal = diagnostics["filtration_only_renal_reference"]
        print(
            f"filtration_reference={renal['clearance_l_per_h']:.6g} L/h "
            f"pbpk_gfr_active={diagnostics['renal_filtration_active_in_pbpk']}"
        )
    print(
        "hepatic_intrinsic_pbpk_active="
        f"{diagnostics['intrinsic_hepatic_active_in_pbpk']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
