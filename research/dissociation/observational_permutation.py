"""Within-subject permutation audit for optional mechanism annotations.

Tests whether mechanism-labelled covariates improve held-out prediction more than
expected after destroying their temporal alignment with outcomes.

Default permutation is a circular shift of the *joint mechanism vector* within each
subject. This preserves:
- each subject's mechanism value distribution;
- correlations among mechanism columns;
- much of the annotation sequence structure;

while breaking the original session alignment.

This is an association/randomization diagnostic, not a causal test and not evidence
for treatment effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np

from research.dissociation.longitudinal_nulls import MECHANISM_FEATURES
from research.dissociation.observational_csv import (
    load_observational_csv,
    score_observational_rows,
)


NULL_MODEL_PREFIXES = (
    "mean_only",
    "history_available",
    "context_available",
    "context_history_available",
)
MECHANISM_MODEL_NAMES = (
    "mechanism_available",
    "context_plus_mechanism_available",
    "full_available",
)


def _best_mse(scores, names: Sequence[str]) -> tuple[str, float] | None:
    eligible = [score for score in scores if score.model in names]
    if not eligible:
        return None
    best = min(eligible, key=lambda score: score.test_mse)
    return best.model, best.test_mse


def mechanism_gain(scores) -> dict:
    null = _best_mse(scores, NULL_MODEL_PREFIXES)
    mechanism = _best_mse(scores, MECHANISM_MODEL_NAMES)
    if null is None or mechanism is None:
        return {
            "status": "unavailable",
            "reason": "both null and mechanism model families require enough usable data",
        }
    null_name, null_mse = null
    mechanism_name, mechanism_mse = mechanism
    return {
        "status": "ok",
        "best_null_model": null_name,
        "best_mechanism_model": mechanism_name,
        "best_null_mse": null_mse,
        "best_mechanism_mse": mechanism_mse,
        "absolute_gain": null_mse - mechanism_mse,
        "fractional_gain": (null_mse - mechanism_mse) / max(null_mse, 1e-12),
    }


def circular_shift_mechanisms(
    rows: Sequence[dict],
    rng: np.random.Generator,
) -> list[dict]:
    result = [dict(row) for row in rows]
    by_subject: dict[int, list[int]] = {}
    for idx, row in enumerate(result):
        by_subject.setdefault(int(row["subject"]), []).append(idx)

    for indices in by_subject.values():
        indices.sort(key=lambda idx: result[idx]["session"])
        n = len(indices)
        if n < 2:
            continue
        shift = int(rng.integers(1, n))
        matrix = np.asarray([
            [result[idx].get(name, float("nan")) for name in MECHANISM_FEATURES]
            for idx in indices
        ], dtype=float)
        shifted = np.roll(matrix, shift=shift, axis=0)
        for idx, vector in zip(indices, shifted):
            for name, value in zip(MECHANISM_FEATURES, vector):
                result[idx][name] = float(value)
    return result


def permutation_audit(
    rows: Sequence[dict],
    *,
    permutations: int = 200,
    seed: int = 404,
    test_fraction: float = 0.25,
    ridge: float = 1e-3,
) -> dict:
    if permutations < 10:
        raise ValueError("permutations must be >= 10")

    original_scores = score_observational_rows(
        rows, test_fraction=test_fraction, ridge=ridge,
    )
    observed = mechanism_gain(original_scores)
    if observed["status"] != "ok":
        return {
            "status": "unavailable",
            "observed": observed,
            "permutations": 0,
        }

    rng = np.random.default_rng(seed)
    null_gains = []
    unavailable = 0
    for _ in range(permutations):
        shifted = circular_shift_mechanisms(rows, rng)
        scores = score_observational_rows(
            shifted, test_fraction=test_fraction, ridge=ridge,
        )
        result = mechanism_gain(scores)
        if result["status"] != "ok":
            unavailable += 1
            continue
        null_gains.append(float(result["fractional_gain"]))

    if not null_gains:
        return {
            "status": "unavailable",
            "reason": "no valid permuted model comparisons",
            "observed": observed,
            "permutations": permutations,
        }

    null = np.asarray(null_gains)
    observed_gain = float(observed["fractional_gain"])
    p_upper = (1.0 + float(np.sum(null >= observed_gain))) / (1.0 + len(null))
    return {
        "status": "ok",
        "observed": observed,
        "requested_permutations": permutations,
        "valid_permutations": len(null),
        "unavailable_permutations": unavailable,
        "permutation_method": "within_subject_joint_circular_shift",
        "null_gain_median": float(np.median(null)),
        "null_gain_q025": float(np.quantile(null, 0.025)),
        "null_gain_q975": float(np.quantile(null, 0.975)),
        "empirical_upper_tail_p": p_upper,
        "warning": (
            "Empirical randomization diagnostic only. Time-varying confounding, "
            "measurement error and non-random exposure remain possible."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_path")
    p.add_argument("--permutations", type=int, default=200)
    p.add_argument("--seed", type=int, default=404)
    p.add_argument("--test-fraction", type=float, default=0.25)
    p.add_argument("--ridge", type=float, default=1e-3)
    p.add_argument("--output", default="runs/dissociation_observational_permutation.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    rows, schema = load_observational_csv(args.csv_path)
    result = permutation_audit(
        rows,
        permutations=args.permutations,
        seed=args.seed,
        test_fraction=args.test_fraction,
        ridge=args.ridge,
    )
    payload = {
        "schema_version": 1,
        "schema": schema.to_dict(),
        "audit": result,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote observational permutation audit to {out}")
    print(f"status={result['status']}")
    if result["status"] == "ok":
        observed = result["observed"]
        print(
            f"observed_mechanism_gain={observed['fractional_gain']:+.3f} "
            f"null_median={result['null_gain_median']:+.3f} "
            f"p_upper={result['empirical_upper_tail_p']:.4f}"
        )
    else:
        print(result.get("reason") or result["observed"].get("reason"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
