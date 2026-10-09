"""Factorial interaction analysis for the dissociative-state toy model.

Runs a binary high/low design over selected mechanistic perturbations and estimates
main effects plus pairwise interaction contrasts on synthetic outputs.

All factor levels are dimensionless model perturbations, not doses.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable

from research.dissociation.model import (
    MechanismInput,
    ModelParameters,
    PopulationConfig,
    simulate,
)


DEFAULT_FACTORS = (
    "meth",
    "nmda_antagonism",
    "mor_partial_agonism",
    "kor_agonism",
    "kor_antagonism",
    "nop_agonism",
    "wake_anchor_disruption",
)

METRICS = (
    "mean_switch_probability",
    "mean_persistence_steps",
    "executive_stability",
    "cortical_integration",
    "internal_coordination",
    "information_consistency",
    "salience_load",
)


def generate_design(
    factors: Iterable[str] = DEFAULT_FACTORS,
    *,
    high: float = 0.65,
) -> list[tuple[dict[str, int], MechanismInput]]:
    factors = tuple(factors)
    if not 0.0 <= high <= 1.0:
        raise ValueError("high must be in [0, 1]")

    rows = []
    for bits in itertools.product((0, 1), repeat=len(factors)):
        indicators = dict(zip(factors, bits, strict=True))
        kwargs = {name: high * bit for name, bit in indicators.items()}
        rows.append((indicators, MechanismInput(**kwargs)))
    return rows


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def estimate_effects(
    records: list[dict],
    factors: Iterable[str] = DEFAULT_FACTORS,
) -> dict:
    """Estimate marginal main effects and pairwise difference-in-differences."""

    factors = tuple(factors)
    main: Dict[str, Dict[str, float]] = {}
    pairwise: Dict[str, Dict[str, float]] = {}

    for factor in factors:
        on = [r for r in records if r["indicators"][factor] == 1]
        off = [r for r in records if r["indicators"][factor] == 0]
        main[factor] = {
            metric: _mean([r["metrics"][metric] for r in on])
            - _mean([r["metrics"][metric] for r in off])
            for metric in METRICS
        }

    for a, b in itertools.combinations(factors, 2):
        key = f"{a} x {b}"
        pairwise[key] = {}
        for metric in METRICS:
            # Average over all other factors by taking the four marginal cells.
            cells: dict[tuple[int, int], list[float]] = {
                (0, 0): [],
                (1, 0): [],
                (0, 1): [],
                (1, 1): [],
            }
            for record in records:
                cell = (
                    record["indicators"][a],
                    record["indicators"][b],
                )
                cells[cell].append(record["metrics"][metric])

            m00 = _mean(cells[(0, 0)])
            m10 = _mean(cells[(1, 0)])
            m01 = _mean(cells[(0, 1)])
            m11 = _mean(cells[(1, 1)])
            pairwise[key][metric] = m11 - m10 - m01 + m00

    return {"main_effects": main, "pairwise_interactions": pairwise}


def run_factorial(
    *,
    factors: Iterable[str] = DEFAULT_FACTORS,
    high: float = 0.65,
    config: PopulationConfig = PopulationConfig(n_subjects=1500, steps=120, seed=11),
    params: ModelParameters = ModelParameters(),
) -> dict:
    factors = tuple(factors)
    records = []
    for indicators, inputs in generate_design(factors, high=high):
        summary = simulate(inputs, config=config, params=params)
        records.append(
            {
                "indicators": indicators,
                "inputs": asdict(inputs),
                "metrics": summary.to_dict(),
            }
        )

    return {
        "schema_version": 1,
        "model": "dimensionless_dissociative_state_gating_factorial",
        "warning": "Synthetic research model; factor levels are not drug doses.",
        "factors": list(factors),
        "high_level": high,
        "population": asdict(config),
        "parameters": asdict(params),
        "records": records,
        **estimate_effects(records, factors),
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=1500)
    p.add_argument("--steps", type=int, default=120)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--high", type=float, default=0.65)
    p.add_argument(
        "--factors",
        nargs="+",
        default=list(DEFAULT_FACTORS),
        choices=list(DEFAULT_FACTORS),
    )
    p.add_argument("--output", default="runs/dissociation_factorial.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    config = PopulationConfig(args.subjects, args.steps, args.seed)
    result = run_factorial(
        factors=args.factors,
        high=args.high,
        config=config,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(result['records'])} factorial conditions to {output}")
    print("\nMain effects on switching probability:")
    for factor, metrics in result["main_effects"].items():
        print(f"  {factor:26s} {metrics['mean_switch_probability']:+.5f}")

    print("\nPairwise interactions on switching probability:")
    ranked = sorted(
        result["pairwise_interactions"].items(),
        key=lambda item: abs(item[1]["mean_switch_probability"]),
        reverse=True,
    )
    for name, metrics in ranked:
        print(f"  {name:52s} {metrics['mean_switch_probability']:+.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
