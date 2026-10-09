"""Repeated-seed stability for the longitudinal competing-null benchmark."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

from research.dissociation.longitudinal_nulls import (
    LongitudinalConfig, benchmark_truth,
)
from research.dissociation.observable_model import MeasurementConfig


MECHANISM_MODELS = {"mechanism_only", "context_plus_mechanism", "full"}
CONTEXT_MODELS = {"context_only", "context_history"}


def run_stability(
    *,
    seeds: int = 5,
    config: LongitudinalConfig = LongitudinalConfig(),
    measurement: MeasurementConfig = MeasurementConfig(missing_probability=0.10),
) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be >= 1")

    rows = []
    for offset in range(seeds):
        run_config = replace(config, seed=config.seed + 97 * offset)
        for truth in ("receptor", "context", "mixed"):
            result = benchmark_truth(
                truth, config=run_config, measurement=measurement
            )
            diag = result["discrimination"]
            rows.append({
                "seed": run_config.seed,
                "truth": truth,
                "best_test_model": result["best_test_model"],
                "best_bic_model": result["best_bic_model"],
                "permuted_best_test_model": result["permuted_best_test_model"],
                "mechanism_gain_over_null_fraction": (
                    diag.get("mechanism_gain_over_null_fraction")
                ),
                "mechanism_permutation_penalty_fraction": (
                    diag.get("mechanism_permutation_penalty_fraction")
                ),
            })

    summary = {}
    for truth in ("receptor", "context", "mixed"):
        subset = [row for row in rows if row["truth"] == truth]
        gains = np.array(
            [row["mechanism_gain_over_null_fraction"] for row in subset],
            dtype=float,
        )
        penalties = np.array(
            [row["mechanism_permutation_penalty_fraction"] for row in subset],
            dtype=float,
        )
        winners = Counter(row["best_test_model"] for row in subset)
        permuted_winners = Counter(row["permuted_best_test_model"] for row in subset)

        summary[truth] = {
            "runs": len(subset),
            "winner_counts": dict(winners),
            "permuted_winner_counts": dict(permuted_winners),
            "mechanism_family_wins": sum(
                row["best_test_model"] in MECHANISM_MODELS for row in subset
            ),
            "context_family_wins": sum(
                row["best_test_model"] in CONTEXT_MODELS for row in subset
            ),
            "median_mechanism_gain_over_null": float(np.median(gains)),
            "min_mechanism_gain_over_null": float(np.min(gains)),
            "median_permutation_penalty": float(np.median(penalties)),
            "min_permutation_penalty": float(np.min(penalties)),
        }

    # Synthetic benchmark-health checks. These are not scientific significance
    # thresholds; they only test whether this simulator can distinguish the truths
    # it generated itself.
    benchmark_health = {
        "receptor_truth_mechanism_majority": (
            summary["receptor"]["mechanism_family_wins"] > seeds / 2
        ),
        "context_truth_context_majority": (
            summary["context"]["context_family_wins"] > seeds / 2
        ),
        "receptor_truth_positive_median_gain": (
            summary["receptor"]["median_mechanism_gain_over_null"] > 0.0
        ),
        "receptor_truth_positive_permutation_penalty": (
            summary["receptor"]["median_permutation_penalty"] > 0.0
        ),
        "context_truth_no_large_spurious_gain": (
            summary["context"]["median_mechanism_gain_over_null"] < 0.10
        ),
    }
    benchmark_health["passed"] = all(benchmark_health.values())

    return {
        "schema_version": 1,
        "warning": (
            "Synthetic benchmark health check only. It demonstrates whether the "
            "simulated analysis can recover the simulated truth family, not whether "
            "any receptor mechanism is true in humans."
        ),
        "seeds": seeds,
        "base_config": asdict(config),
        "measurement": asdict(measurement),
        "summary": summary,
        "benchmark_health": benchmark_health,
        "rows": rows,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--subjects", type=int, default=5)
    p.add_argument("--sessions", type=int, default=18)
    p.add_argument("--micro-population", type=int, default=60)
    p.add_argument("--steps", type=int, default=18)
    p.add_argument("--seed", type=int, default=240)
    p.add_argument("--missing", type=float, default=0.10)
    p.add_argument("--output", default="runs/dissociation_longitudinal_null_stability.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    result = run_stability(
        seeds=args.seeds,
        config=LongitudinalConfig(
            subjects=args.subjects,
            sessions=args.sessions,
            micro_population=args.micro_population,
            steps_per_session=args.steps,
            seed=args.seed,
        ),
        measurement=MeasurementConfig(missing_probability=args.missing),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote longitudinal null stability benchmark to {out}")
    for truth, row in result["summary"].items():
        print(
            f"truth={truth:8s} "
            f"mechanism_wins={row['mechanism_family_wins']}/{row['runs']} "
            f"context_wins={row['context_family_wins']}/{row['runs']} "
            f"median_gain={row['median_mechanism_gain_over_null']:+.3f} "
            f"median_perm_penalty={row['median_permutation_penalty']:+.3f}"
        )
    print(f"benchmark_health_passed={result['benchmark_health']['passed']}")
    return 0 if result["benchmark_health"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
