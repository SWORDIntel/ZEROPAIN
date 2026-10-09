"""Sensitivity sweep for uncertain dissociation model coefficients.

The point of this script is to identify conclusions that only hold because of a chosen
coefficient sign/magnitude. It deliberately varies uncertain opioid/NOP effects.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import replace
from pathlib import Path

from research.dissociation.experiments import CONDITIONS
from research.dissociation.model import ModelParameters, PopulationConfig, compare_conditions


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=2500)
    p.add_argument("--steps", type=int, default=160)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--output", default="runs/dissociation_sensitivity.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    config = PopulationConfig(args.subjects, args.steps, args.seed)
    base = ModelParameters()

    mor_values = (-0.20, 0.0, 0.20, 0.35, 0.50)
    kor_ant_values = (-0.20, 0.0, 0.20, 0.30, 0.50)
    nop_ag_values = (-0.20, 0.0, 0.10, 0.25)

    rows = []
    for mor, kor_ant, nop_ag in itertools.product(mor_values, kor_ant_values, nop_ag_values):
        params = replace(
            base,
            mor_partial_control_weight=mor,
            kor_antagonist_control_weight=kor_ant,
            nop_agonist_control_weight=nop_ag,
        )
        results = compare_conditions(
            {
                "meth_direct": CONDITIONS["meth_direct"],
                "meth_plus_mor_partial": CONDITIONS["meth_plus_mor_partial"],
                "meth_plus_kor_antagonism": CONDITIONS["meth_plus_kor_antagonism"],
                "meth_plus_nop_agonism": CONDITIONS["meth_plus_nop_agonism"],
            },
            config=config,
            params=params,
        )
        baseline = results["meth_direct"].mean_switch_probability
        rows.append(
            {
                "mor_partial_control_weight": mor,
                "kor_antagonist_control_weight": kor_ant,
                "nop_agonist_control_weight": nop_ag,
                "meth_p_switch": baseline,
                "mor_delta": results["meth_plus_mor_partial"].mean_switch_probability - baseline,
                "kor_ant_delta": results["meth_plus_kor_antagonism"].mean_switch_probability - baseline,
                "nop_ag_delta": results["meth_plus_nop_agonism"].mean_switch_probability - baseline,
            }
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "warning": "Coefficient sensitivity analysis; not clinical pharmacology.",
                "population": {
                    "n_subjects": args.subjects,
                    "steps": args.steps,
                    "seed": args.seed,
                },
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} sensitivity combinations to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
