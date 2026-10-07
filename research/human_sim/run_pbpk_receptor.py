"""Run the first HumanSim PBPK -> receptor -> adaptation milestone.

All exposure/affinity values are arbitrary research units. This CLI intentionally has
no mg/kg conversion, clinical dosing presets, or administration recommendations.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict

from research.human_sim.disposition import synthetic_reference_disposition
from research.human_sim.compound_pk import synthetic_compound_pk
from research.human_sim.engine import simulate_human_chain, synthetic_target_panel
from research.human_sim.pbpk import simulate_pbpk
from research.human_sim.pbpk_reference import compare_to_reference, simulate_pbpk_reference
from research.human_sim.physiology import synthetic_reference_physiology
from zeropain.verified_io import write_json


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-h", type=float, default=12.0)
    p.add_argument("--dt-h", type=float, default=0.05)
    p.add_argument(
        "--initial-central-units",
        type=float,
        default=1.0,
        help="Arbitrary amount units; not mg and not a human dose.",
    )
    p.add_argument("--trace", action="store_true")
    p.add_argument("--output", default="runs/human_sim_pbpk_receptor.json")
    return p


def build_payload(args: argparse.Namespace) -> dict:
    physiology = synthetic_reference_physiology()
    disposition = synthetic_reference_disposition()
    targets = synthetic_target_panel()
    result = simulate_human_chain(
        physiology,
        disposition,
        targets,
        duration_h=args.duration_h,
        dt_h=args.dt_h,
        initial_central_amount=args.initial_central_units,
    )
    return {
        "schema_version": 1,
        "model": "human_sim_pbpk_receptor_adaptation_milestone_1",
        "warning": (
            "Synthetic research fixture only. Physiology/affinity values are not "
            "validated human calibration data and amount units are not clinical doses."
        ),
        "physiology": physiology.to_dict(),
        "disposition": disposition.to_dict(),
        "compound_pk": compound_pk.to_dict(),
        "targets": {name: target.to_dict() for name, target in targets.items()},
        "input": {
            "duration_h": args.duration_h,
            "dt_h": args.dt_h,
            "initial_central_units": args.initial_central_units,
        },
        "result": result.to_dict(include_trace=args.trace),
    }


def _relations(payload: dict):
    failures = []
    summary = payload["result"]["summary"]
    mass_error = summary["pbpk"]["max_abs_mass_balance_error"]
    if mass_error > 1e-8:
        failures.append(f"mass balance residual {mass_error} exceeds 1e-8")

    for name, target in summary["targets"].items():
        for field in (
            "peak_occupancy",
            "mean_occupancy",
            "peak_signal_magnitude",
            "mean_signal_magnitude",
            "final_surface_fraction",
            "final_coupling_fraction",
        ):
            value = target[field]
            if not 0.0 <= value <= 1.0:
                failures.append(f"{name}.{field}={value} outside [0,1]")
    return (not failures, "; ".join(failures[:8]))


def _reference_checker(args: argparse.Namespace):
    enabled = os.getenv("ZEROPAIN_VERIFY_REFERENCE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not enabled:
        return None

    tolerance = float(os.getenv("ZEROPAIN_VERIFY_REFERENCE_NRMSE", "0.08"))
    if tolerance <= 0:
        raise ValueError("ZEROPAIN_VERIFY_REFERENCE_NRMSE must be positive")

    def check(_payload):
        physiology = synthetic_reference_physiology()
        disposition = synthetic_reference_disposition()
        primary = simulate_pbpk(
            physiology,
            disposition,
            duration_h=args.duration_h,
            dt_h=args.dt_h,
            initial_central_amount=args.initial_central_units,
        )
        reference = simulate_pbpk_reference(
            physiology,
            disposition,
            duration_h=args.duration_h,
            output_dt_h=args.dt_h,
            substeps=20,
            initial_central_amount=args.initial_central_units,
        )
        comparison = compare_to_reference(primary, reference)
        passed = comparison.max_metric <= tolerance
        return (
            passed,
            (
                f"PBPK independent RK4 max_nrmse={comparison.max_metric:.6f}; "
                f"threshold={tolerance:.6f}; metrics={comparison.to_dict()}"
            ),
        )

    return check


def main() -> int:
    args = _parser().parse_args()
    if args.initial_central_units < 0:
        raise ValueError("--initial-central-units cannot be negative")

    payload = build_payload(args)
    out = write_json(
        args.output,
        payload,
        label="human_sim.pbpk_receptor",
        relations=[_relations],
        replay=lambda: build_payload(args),
        independent=_reference_checker(args),
        metadata={
            "duration_h": args.duration_h,
            "dt_h": args.dt_h,
            "synthetic_fixture": True,
        },
    )

    pbpk = payload["result"]["summary"]["pbpk"]
    print(f"Wrote HumanSim milestone-1 result to {out}")
    print(
        f"mass_error={pbpk['max_abs_mass_balance_error']:.3e} "
        f"peak_brain_free={pbpk['peak_brain_free_concentration']:.6f}"
    )
    for name, target in payload["result"]["summary"]["targets"].items():
        print(
            f"{name:12s} occupancy={target['peak_occupancy']:.3f} "
            f"signal={target['peak_signal_magnitude']:.3f} "
            f"surface_final={target['final_surface_fraction']:.3f} "
            f"coupling_final={target['final_coupling_fraction']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
