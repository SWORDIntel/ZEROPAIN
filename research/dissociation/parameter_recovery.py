"""Synthetic parameter-recovery benchmark for the scalar gating model.

The benchmark hides selected ModelParameters, generates synthetic summaries, and then
tries to recover those parameters from a set of perturbation conditions.

This is an identifiability test, not biological parameter estimation. Inputs and
coefficients are dimensionless.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, Sequence

import numpy as np

from zeropain.verified_io import write_json

from research.dissociation.model import (
    MechanismInput,
    ModelParameters,
    PopulationConfig,
    SimulationSummary,
    compare_conditions,
)


FIT_METRICS = (
    "mean_switch_probability",
    "executive_stability",
    "cortical_integration",
    "internal_coordination",
    "salience_load",
)

DEFAULT_BOUNDS: dict[str, tuple[float, float]] = {
    "meth_salience_weight": (0.30, 1.80),
    "nmda_integration_weight": (0.40, 1.60),
    "mor_partial_control_weight": (-0.20, 0.75),
    "kor_antagonist_control_weight": (-0.20, 0.75),
    "wake_coordination_weight": (0.30, 1.40),
}


FIT_CONDITIONS: dict[str, MechanismInput] = {
    "baseline": MechanismInput(),
    "meth_low": MechanismInput(meth=0.35),
    "meth_high": MechanismInput(meth=0.75),
    "nmda_low": MechanismInput(nmda_antagonism=0.30),
    "nmda_high": MechanismInput(nmda_antagonism=0.70),
    "mor_partial": MechanismInput(mor_partial_agonism=0.65),
    "kor_antagonist": MechanismInput(kor_antagonism=0.65),
    "wake_disruption": MechanismInput(wake_anchor_disruption=0.80),
}

HOLDOUT_CONDITIONS: dict[str, MechanismInput] = {
    "meth_nmda": MechanismInput(meth=0.65, nmda_antagonism=0.55),
    "meth_mor": MechanismInput(meth=0.65, mor_partial_agonism=0.55),
    "meth_kor_ant": MechanismInput(meth=0.65, kor_antagonism=0.55),
    "meth_wake": MechanismInput(meth=0.65, wake_anchor_disruption=0.70),
}


@dataclass(frozen=True)
class RecoveryConfig:
    grid_points: int = 7
    passes: int = 4
    shrink: float = 0.45
    metric_floor: float = 0.04
    target_replicates: int = 3
    fit_replicates: int = 3
    fit_seed_offset: int = 1000


@dataclass
class ParameterRecovery:
    name: str
    true_value: float
    estimated_value: float
    absolute_error: float
    relative_error: float
    final_search_low: float
    final_search_high: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


def _summary_matrix(
    summaries: Dict[str, SimulationSummary],
    condition_order: Sequence[str],
    metrics: Sequence[str] = FIT_METRICS,
) -> np.ndarray:
    return np.array(
        [
            [float(getattr(summaries[name], metric)) for metric in metrics]
            for name in condition_order
        ],
        dtype=float,
    )


def _metric_scales(target: np.ndarray, floor: float) -> np.ndarray:
    spread = np.std(target, axis=0)
    magnitude = np.mean(np.abs(target), axis=0)
    return np.maximum.reduce(
        [
            spread,
            0.20 * magnitude,
            np.full_like(spread, floor),
        ]
    )


def _replicate_configs(
    population: PopulationConfig,
    count: int,
    *,
    seed_offset: int = 0,
) -> list[PopulationConfig]:
    if count < 1:
        raise ValueError("replicate count must be >= 1")
    return [
        PopulationConfig(
            n_subjects=population.n_subjects,
            steps=population.steps,
            seed=population.seed + seed_offset + idx,
        )
        for idx in range(count)
    ]


def _mean_condition_matrix(
    params: ModelParameters,
    conditions: Dict[str, MechanismInput],
    configs: Sequence[PopulationConfig],
    *,
    metrics: Sequence[str] = FIT_METRICS,
) -> np.ndarray:
    matrices = []
    order = list(conditions)
    for config in configs:
        summaries = compare_conditions(conditions, config=config, params=params)
        matrices.append(_summary_matrix(summaries, order, metrics))
    return np.mean(np.stack(matrices, axis=0), axis=0)


def objective(
    params: ModelParameters,
    target: np.ndarray,
    conditions: Dict[str, MechanismInput],
    configs: Sequence[PopulationConfig],
    *,
    metric_scales: np.ndarray,
    metrics: Sequence[str] = FIT_METRICS,
) -> float:
    matrix = _mean_condition_matrix(
        params,
        conditions,
        configs,
        metrics=metrics,
    )
    residual = (matrix - target) / metric_scales[None, :]
    return float(np.mean(residual * residual))


def recover_parameters(
    true_params: ModelParameters,
    parameter_bounds: Dict[str, tuple[float, float]],
    *,
    population: PopulationConfig,
    recovery: RecoveryConfig = RecoveryConfig(),
    fit_conditions: Dict[str, MechanismInput] = FIT_CONDITIONS,
) -> tuple[ModelParameters, list[ParameterRecovery], dict[str, float]]:
    """Recover selected parameters by deterministic coordinate-grid refinement."""

    if recovery.grid_points < 3:
        raise ValueError("grid_points must be >= 3")
    if recovery.passes < 1:
        raise ValueError("passes must be >= 1")
    if not 0.0 < recovery.shrink < 1.0:
        raise ValueError("shrink must be in (0, 1)")
    if recovery.target_replicates < 1 or recovery.fit_replicates < 1:
        raise ValueError("replicate counts must be >= 1")

    names = list(parameter_bounds)
    for name, (low, high) in parameter_bounds.items():
        if not hasattr(true_params, name):
            raise ValueError(f"unknown ModelParameters field: {name}")
        if low >= high:
            raise ValueError(f"invalid bounds for {name}: {(low, high)}")

    # Generate target data and fit simulations from different random seeds by default.
    # This prevents the recovery benchmark from becoming artificially easy because
    # stochastic process noise cancels between truth and candidate evaluations.
    target_configs = _replicate_configs(
        population,
        recovery.target_replicates,
        seed_offset=0,
    )
    fit_configs = _replicate_configs(
        population,
        recovery.fit_replicates,
        seed_offset=recovery.fit_seed_offset,
    )

    target = _mean_condition_matrix(
        true_params,
        fit_conditions,
        target_configs,
    )
    scales = _metric_scales(target, recovery.metric_floor)

    # Start from the center of each bound while retaining defaults for parameters
    # not under recovery.
    estimate = ModelParameters()
    for name, (low, high) in parameter_bounds.items():
        estimate = replace(estimate, **{name: (low + high) / 2.0})

    windows = dict(parameter_bounds)
    score_history: list[float] = []

    for _ in range(recovery.passes):
        for name in names:
            low, high = windows[name]
            candidates = np.linspace(low, high, recovery.grid_points)
            scored: list[tuple[float, float]] = []
            for value in candidates:
                candidate = replace(estimate, **{name: float(value)})
                score = objective(
                    candidate,
                    target,
                    fit_conditions,
                    fit_configs,
                    metric_scales=scales,
                )
                scored.append((score, float(value)))

            scored.sort(key=lambda item: item[0])
            best_score, best_value = scored[0]
            estimate = replace(estimate, **{name: best_value})
            score_history.append(best_score)

            width = (high - low) * recovery.shrink
            global_low, global_high = parameter_bounds[name]
            new_low = max(global_low, best_value - width / 2.0)
            new_high = min(global_high, best_value + width / 2.0)
            if new_high - new_low < 1e-9:
                new_low, new_high = global_low, global_high
            windows[name] = (new_low, new_high)

    recovered: list[ParameterRecovery] = []
    for name in names:
        truth = float(getattr(true_params, name))
        estimated = float(getattr(estimate, name))
        abs_error = abs(estimated - truth)
        denom = max(abs(truth), 1e-9)
        low, high = windows[name]
        recovered.append(
            ParameterRecovery(
                name=name,
                true_value=truth,
                estimated_value=estimated,
                absolute_error=abs_error,
                relative_error=abs_error / denom,
                final_search_low=low,
                final_search_high=high,
            )
        )

    fit_score = objective(
        estimate,
        target,
        fit_conditions,
        fit_configs,
        metric_scales=scales,
    )

    holdout_target = _mean_condition_matrix(
        true_params,
        HOLDOUT_CONDITIONS,
        target_configs,
    )
    holdout_matrix = _mean_condition_matrix(
        estimate,
        HOLDOUT_CONDITIONS,
        fit_configs,
    )
    holdout_scales = _metric_scales(holdout_target, recovery.metric_floor)
    holdout_residual = (holdout_matrix - holdout_target) / holdout_scales[None, :]
    holdout_score = float(np.mean(holdout_residual * holdout_residual))

    diagnostics = {
        "fit_objective": fit_score,
        "holdout_objective": holdout_score,
        "max_relative_error": max(item.relative_error for item in recovered),
        "mean_relative_error": float(np.mean([item.relative_error for item in recovered])),
        "evaluations_approx": recovery.passes
        * recovery.grid_points
        * len(parameter_bounds),
        "last_coordinate_score": score_history[-1] if score_history else fit_score,
        "target_replicates": recovery.target_replicates,
        "fit_replicates": recovery.fit_replicates,
        "fit_seed_offset": recovery.fit_seed_offset,
    }
    return estimate, recovered, diagnostics


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=500)
    p.add_argument("--steps", type=int, default=60)
    p.add_argument("--seed", type=int, default=71)
    p.add_argument("--grid-points", type=int, default=7)
    p.add_argument("--passes", type=int, default=4)
    p.add_argument("--shrink", type=float, default=0.45)
    p.add_argument("--target-replicates", type=int, default=3)
    p.add_argument("--fit-replicates", type=int, default=3)
    p.add_argument("--fit-seed-offset", type=int, default=1000)
    p.add_argument(
        "--parameters",
        nargs="+",
        default=list(DEFAULT_BOUNDS),
        choices=list(DEFAULT_BOUNDS),
    )
    p.add_argument(
        "--output",
        default="runs/dissociation_parameter_recovery.json",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    population = PopulationConfig(
        n_subjects=args.subjects,
        steps=args.steps,
        seed=args.seed,
    )
    recovery_cfg = RecoveryConfig(
        grid_points=args.grid_points,
        passes=args.passes,
        shrink=args.shrink,
        target_replicates=args.target_replicates,
        fit_replicates=args.fit_replicates,
        fit_seed_offset=args.fit_seed_offset,
    )
    bounds = {name: DEFAULT_BOUNDS[name] for name in args.parameters}
    true_params = ModelParameters()

    estimate, recovered, diagnostics = recover_parameters(
        true_params,
        bounds,
        population=population,
        recovery=recovery_cfg,
    )

    payload = {
        "schema_version": 1,
        "model": "scalar_gating_parameter_recovery",
        "warning": (
            "Synthetic identifiability benchmark only. Recovered values are "
            "dimensionless model coefficients, not biological estimates."
        ),
        "population": asdict(population),
        "recovery_config": asdict(recovery_cfg),
        "bounds": {name: list(value) for name, value in bounds.items()},
        "fit_conditions": {name: asdict(value) for name, value in FIT_CONDITIONS.items()},
        "holdout_conditions": {
            name: asdict(value) for name, value in HOLDOUT_CONDITIONS.items()
        },
        "true_parameters": {
            name: getattr(true_params, name)
            for name in bounds
        },
        "estimated_parameters": {
            name: getattr(estimate, name)
            for name in bounds
        },
        "recovery": [item.to_dict() for item in recovered],
        "diagnostics": diagnostics,
    }

    def recovery_relation(value):
        failures = []
        for name, estimate in value["estimated_parameters"].items():
            low, high = value["bounds"][name]
            if not low <= estimate <= high:
                failures.append(f"{name}={estimate} outside [{low}, {high}]")
        if len(value["recovery"]) != len(value["estimated_parameters"]):
            failures.append("recovery row count does not match fitted parameter count")
        return (not failures, "; ".join(failures))

    out = write_json(
        args.output,
        payload,
        label="dissociation.parameter_recovery",
        relations=[recovery_relation],
        metadata={"seed": args.seed, "subjects": args.subjects, "steps": args.steps},
    )

    print(f"Wrote recovery benchmark to {out}")
    for item in recovered:
        print(
            f"{item.name:32s} "
            f"true={item.true_value:+.4f} "
            f"est={item.estimated_value:+.4f} "
            f"rel_err={item.relative_error:.3f}"
        )
    print(
        f"fit={diagnostics['fit_objective']:.6f} "
        f"holdout={diagnostics['holdout_objective']:.6f} "
        f"mean_rel_err={diagnostics['mean_relative_error']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
