"""Local identifiability analysis for scalar gating parameters.

Computes a finite-difference Jacobian from selected dimensionless mechanism parameters
to observable synthetic summary metrics across perturbation conditions, then examines:
- singular values / numerical rank;
- condition number;
- per-parameter sensitivity norm;
- pairwise cosine similarity between parameter-effect vectors.

Highly parallel Jacobian columns indicate parameter confounding: multiple mechanisms can
produce nearly indistinguishable observable changes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from research.dissociation.model import (
    MechanismInput,
    ModelParameters,
    PopulationConfig,
)
from research.dissociation.parameter_recovery import (
    DEFAULT_BOUNDS,
    FIT_CONDITIONS,
    FIT_METRICS,
    _mean_condition_matrix,
    _metric_scales,
    _replicate_configs,
)


@dataclass
class IdentifiabilitySummary:
    parameter_count: int
    observable_count: int
    numerical_rank: int
    condition_number: float
    smallest_singular_value: float
    largest_singular_value: float
    highly_confounded_pairs: list[dict[str, float | str]]

    def to_dict(self) -> dict:
        return asdict(self)


def finite_difference_jacobian(
    params: ModelParameters,
    parameter_bounds: Dict[str, tuple[float, float]],
    *,
    population: PopulationConfig,
    conditions: Dict[str, MechanismInput] = FIT_CONDITIONS,
    replicates: int = 3,
    epsilon_fraction: float = 0.03,
    seed_offset: int = 2000,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if not 0.0 < epsilon_fraction < 0.5:
        raise ValueError("epsilon_fraction must be in (0, 0.5)")

    configs = _replicate_configs(
        population,
        replicates,
        seed_offset=seed_offset,
    )
    baseline = _mean_condition_matrix(params, conditions, configs)
    scales = _metric_scales(baseline, 0.04)

    columns = []
    names = list(parameter_bounds)
    for name in names:
        low, high = parameter_bounds[name]
        center = float(getattr(params, name))
        epsilon = epsilon_fraction * (high - low)
        plus_value = min(high, center + epsilon)
        minus_value = max(low, center - epsilon)
        denominator = plus_value - minus_value
        if denominator <= 1e-12:
            raise ValueError(f"zero finite-difference span for {name}")

        plus = replace(params, **{name: plus_value})
        minus = replace(params, **{name: minus_value})
        plus_matrix = _mean_condition_matrix(plus, conditions, configs)
        minus_matrix = _mean_condition_matrix(minus, conditions, configs)

        derivative = (plus_matrix - minus_matrix) / denominator
        normalized = derivative / scales[None, :]
        columns.append(normalized.reshape(-1))

    jacobian = np.column_stack(columns)
    return jacobian, scales, names


def analyze_identifiability(
    jacobian: np.ndarray,
    names: Sequence[str],
    *,
    confounding_threshold: float = 0.90,
    rank_tolerance: float = 1e-6,
) -> tuple[IdentifiabilitySummary, dict[str, float], np.ndarray]:
    if jacobian.ndim != 2:
        raise ValueError("jacobian must be 2D")
    if jacobian.shape[1] != len(names):
        raise ValueError("name count must match jacobian columns")

    singular = np.linalg.svd(jacobian, compute_uv=False)
    largest = float(singular[0]) if len(singular) else 0.0
    smallest = float(singular[-1]) if len(singular) else 0.0
    tolerance = rank_tolerance * max(largest, 1e-12)
    rank = int(np.sum(singular > tolerance))
    condition = (
        float(largest / smallest)
        if smallest > 1e-12
        else float("inf")
    )

    norms = np.linalg.norm(jacobian, axis=0)
    sensitivities = {
        name: float(norm)
        for name, norm in zip(names, norms)
    }

    cosine = np.eye(len(names), dtype=float)
    confounded: list[dict[str, float | str]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            denom = norms[i] * norms[j]
            value = float(np.dot(jacobian[:, i], jacobian[:, j]) / denom) if denom > 0 else 0.0
            cosine[i, j] = cosine[j, i] = value
            if abs(value) >= confounding_threshold:
                confounded.append(
                    {
                        "parameter_a": names[i],
                        "parameter_b": names[j],
                        "cosine_similarity": value,
                    }
                )

    confounded.sort(
        key=lambda row: abs(float(row["cosine_similarity"])),
        reverse=True,
    )

    summary = IdentifiabilitySummary(
        parameter_count=len(names),
        observable_count=jacobian.shape[0],
        numerical_rank=rank,
        condition_number=condition,
        smallest_singular_value=smallest,
        largest_singular_value=largest,
        highly_confounded_pairs=confounded,
    )
    return summary, sensitivities, cosine


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=500)
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--seed", type=int, default=91)
    p.add_argument("--replicates", type=int, default=3)
    p.add_argument("--epsilon-fraction", type=float, default=0.03)
    p.add_argument("--confounding-threshold", type=float, default=0.90)
    p.add_argument(
        "--parameters",
        nargs="+",
        default=list(DEFAULT_BOUNDS),
        choices=list(DEFAULT_BOUNDS),
    )
    p.add_argument(
        "--output",
        default="runs/dissociation_identifiability.json",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    population = PopulationConfig(
        n_subjects=args.subjects,
        steps=args.steps,
        seed=args.seed,
    )
    bounds = {name: DEFAULT_BOUNDS[name] for name in args.parameters}
    params = ModelParameters()

    jacobian, scales, names = finite_difference_jacobian(
        params,
        bounds,
        population=population,
        replicates=args.replicates,
        epsilon_fraction=args.epsilon_fraction,
    )
    summary, sensitivities, cosine = analyze_identifiability(
        jacobian,
        names,
        confounding_threshold=args.confounding_threshold,
    )

    payload = {
        "schema_version": 1,
        "model": "scalar_gating_local_identifiability",
        "warning": (
            "Local synthetic identifiability analysis only. Results depend on the "
            "chosen conditions, observables and current model equations."
        ),
        "population": asdict(population),
        "parameters": names,
        "metric_names": list(FIT_METRICS),
        "condition_names": list(FIT_CONDITIONS),
        "metric_scales": scales.tolist(),
        "jacobian": jacobian.tolist(),
        "singular_values": np.linalg.svd(jacobian, compute_uv=False).tolist(),
        "sensitivity_norms": sensitivities,
        "cosine_similarity": cosine.tolist(),
        "summary": summary.to_dict(),
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote identifiability analysis to {out}")
    print(
        f"rank={summary.numerical_rank}/{summary.parameter_count} "
        f"condition={summary.condition_number:.3f}"
    )
    for name in names:
        print(f"sensitivity {name:32s} {sensitivities[name]:.5f}")
    for row in summary.highly_confounded_pairs:
        print(
            "confounded "
            f"{row['parameter_a']} ~ {row['parameter_b']} "
            f"cos={float(row['cosine_similarity']):+.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
