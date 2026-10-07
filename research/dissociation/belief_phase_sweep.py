"""Phase sweep for cooperation -> fragmentation -> adversarial information dynamics.

Sweeps initial pairwise trust across several perturbation profiles and repeated seeds.
The purpose is to locate conditions under which withholding and false reporting emerge,
rather than assuming methamphetamine directly causes them.

All perturbations are dimensionless model inputs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from research.dissociation.belief_network import (
    BeliefNetworkConfig,
    BeliefNetworkParameters,
    simulate_belief_network,
)
from research.dissociation.model import MechanismInput
from research.dissociation.run_belief_network import make_facts, make_timeline


PROFILES = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.75),
    "meth_nmda": MechanismInput(meth=0.75, nmda_antagonism=0.60),
    "wake": MechanismInput(wake_anchor_disruption=0.90),
    "meth_wake": MechanismInput(meth=0.75, wake_anchor_disruption=0.90),
    "meth_nmda_wake": MechanismInput(
        meth=0.75,
        nmda_antagonism=0.60,
        wake_anchor_disruption=0.90,
    ),
}


def run_phase_sweep(
    trust_levels: list[float],
    *,
    steps: int = 240,
    n_states: int = 4,
    seeds: int = 5,
    sync_interval: int = 48,
    base_seed: int = 100,
    base_params: BeliefNetworkParameters = BeliefNetworkParameters(),
) -> dict:
    rows = []
    for trust_level in trust_levels:
        if not 0.0 <= trust_level <= 1.0:
            raise ValueError("trust levels must be in [0, 1]")

        for profile_name, inputs in PROFILES.items():
            samples = []
            for offset in range(seeds):
                config = BeliefNetworkConfig(
                    n_states=n_states,
                    steps=steps,
                    seed=base_seed + offset,
                    sync_interval=sync_interval,
                    max_coconscious=min(2, n_states),
                )
                params = replace(
                    base_params,
                    initial_trust_mean=trust_level,
                    initial_trust_sd=0.03,
                )
                result = simulate_belief_network(
                    inputs,
                    make_facts(steps),
                    config=config,
                    params=params,
                    timeline=make_timeline(config),
                )
                samples.append(result)

            rows.append(
                {
                    "initial_trust_mean": trust_level,
                    "profile": profile_name,
                    "n": len(samples),
                    "mean_final_trust": float(
                        np.mean([s.mean_pairwise_trust for s in samples])
                    ),
                    "mean_truth_accuracy": float(
                        np.mean([s.truth_accuracy for s in samples])
                    ),
                    "mean_withholding_rate": float(
                        np.mean([s.withholding_rate for s in samples])
                    ),
                    "mean_false_report_rate": float(
                        np.mean([s.false_report_rate for s in samples])
                    ),
                    "mean_adversarial_fraction": float(
                        np.mean([s.adversarial_steps / steps for s in samples])
                    ),
                    "p_any_false_report": float(
                        np.mean([s.false_report_events > 0 for s in samples])
                    ),
                    "p_final_adversarial": float(
                        np.mean([s.final_regime == "adversarial" for s in samples])
                    ),
                }
            )

    boundaries = {}
    for profile_name in PROFILES:
        profile_rows = sorted(
            [row for row in rows if row["profile"] == profile_name],
            key=lambda row: row["initial_trust_mean"],
        )
        false_rows = [
            row
            for row in profile_rows
            if row["mean_false_report_rate"] > 0.01
            or row["p_any_false_report"] >= 0.50
        ]
        adversarial_rows = [
            row
            for row in profile_rows
            if row["mean_adversarial_fraction"] >= 0.10
            or row["p_final_adversarial"] >= 0.50
        ]
        boundaries[profile_name] = {
            "highest_initial_trust_with_false_reporting": (
                max(row["initial_trust_mean"] for row in false_rows)
                if false_rows
                else None
            ),
            "highest_initial_trust_with_adversarial_regime": (
                max(row["initial_trust_mean"] for row in adversarial_rows)
                if adversarial_rows
                else None
            ),
        }

    return {
        "schema_version": 1,
        "model": "belief_network_phase_sweep",
        "warning": (
            "Synthetic research phase sweep. Trust and perturbation levels are "
            "dimensionless model variables, not clinical measurements or doses."
        ),
        "direct_meth_misreport_weight": base_params.direct_meth_misreport_weight,
        "trust_levels": trust_levels,
        "profiles": {name: asdict(inputs) for name, inputs in PROFILES.items()},
        "rows": rows,
        "phase_boundaries": boundaries,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--trust-levels",
        nargs="+",
        type=float,
        default=[0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80],
    )
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--sync-interval", type=int, default=48)
    p.add_argument("--base-seed", type=int, default=100)
    p.add_argument(
        "--direct-meth-misreport-weight",
        type=float,
        default=0.0,
        help=(
            "Sensitivity coefficient only. Default zero deliberately forbids a direct "
            "meth->false-report pathway."
        ),
    )
    p.add_argument(
        "--output",
        default="runs/dissociation_belief_phase_sweep.json",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    params = BeliefNetworkParameters(
        direct_meth_misreport_weight=args.direct_meth_misreport_weight
    )
    result = run_phase_sweep(
        args.trust_levels,
        steps=args.steps,
        n_states=args.states,
        seeds=args.seeds,
        sync_interval=args.sync_interval,
        base_seed=args.base_seed,
        base_params=params,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(result['rows'])} phase-sweep cells to {out}")
    print(
        "direct_meth_misreport_weight="
        f"{result['direct_meth_misreport_weight']:.3f}"
    )
    for profile, boundary in result["phase_boundaries"].items():
        print(
            f"{profile:18s} "
            f"false<=trust:{boundary['highest_initial_trust_with_false_reporting']} "
            f"adversarial<=trust:{boundary['highest_initial_trust_with_adversarial_regime']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
