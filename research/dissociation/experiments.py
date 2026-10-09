"""Predefined experiment matrix for the dissociative-state toy model."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from research.dissociation.model import (
    MechanismInput,
    ModelParameters,
    PopulationConfig,
    compare_conditions,
)


CONDITIONS = {
    "baseline": MechanismInput(),
    "meth_direct": MechanismInput(meth=0.75),
    "wake_anchor_only": MechanismInput(wake_anchor_disruption=0.75),
    "meth_plus_wake_anchor": MechanismInput(meth=0.75, wake_anchor_disruption=0.75),
    "nmda_antagonism": MechanismInput(nmda_antagonism=0.60),
    "meth_plus_nmda": MechanismInput(meth=0.75, nmda_antagonism=0.60),
    "meth_plus_mor_partial": MechanismInput(meth=0.75, mor_partial_agonism=0.60),
    "meth_plus_kor_agonism": MechanismInput(meth=0.75, kor_agonism=0.60),
    "meth_plus_kor_antagonism": MechanismInput(meth=0.75, kor_antagonism=0.60),
    "meth_plus_nop_agonism": MechanismInput(meth=0.75, nop_agonism=0.60),
    "meth_plus_nop_antagonism": MechanismInput(meth=0.75, nop_antagonism=0.60),
    "meth_nmda_mor_kor_antagonism": MechanismInput(
        meth=0.75,
        nmda_antagonism=0.45,
        mor_partial_agonism=0.60,
        kor_antagonism=0.60,
    ),
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=10_000)
    p.add_argument("--steps", type=int, default=240)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--output", default="runs/dissociation_state_matrix.json")
    p.add_argument("--csv", dest="csv_output", default=None)
    return p


def main() -> int:
    args = _parser().parse_args()
    config = PopulationConfig(
        n_subjects=args.subjects,
        steps=args.steps,
        seed=args.seed,
    )
    params = ModelParameters()
    results = compare_conditions(CONDITIONS, config=config, params=params)

    payload = {
        "schema_version": 1,
        "model": "dimensionless_dissociative_state_gating_toy_model",
        "warning": (
            "Research simulation only. Inputs are dimensionless perturbation strengths, "
            "not doses or treatment recommendations."
        ),
        "population": asdict(config),
        "parameters": asdict(params),
        "conditions": {name: asdict(cond) for name, cond in CONDITIONS.items()},
        "results": {name: result.to_dict() for name, result in results.items()},
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.csv_output:
        csv_path = Path(args.csv_output)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"condition": name, **result.to_dict()}
            for name, result in results.items()
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(results)} conditions to {out}")
    for name, result in results.items():
        print(
            f"{name:32s} "
            f"switches={result.mean_switches:7.2f} "
            f"p_switch={result.mean_switch_probability:0.4f} "
            f"persist={result.mean_persistence_steps:6.2f} "
            f"integration={result.cortical_integration:0.3f} "
            f"coord={result.internal_coordination:0.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
