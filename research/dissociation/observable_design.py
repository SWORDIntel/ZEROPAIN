"""Observer-only identifiability, sensor ablation and reduced-design recovery.

The *fitter* receives synthetic noisy reports only, never hidden integration,
executive-control, coordination or salience variables. The generative simulator
necessarily uses those latents, but they are behind a measurement boundary.

No synthetic channel has been calibrated against patients. Results cannot establish
clinical identifiability or justify drug challenges.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from research.dissociation.experimental_design import (
    DesignConstraints, _blocks_from_jacobian, _chosen_matrix, _is_feasible,
    build_candidate_library, optimize_blocks, score_matrix,
)
from research.dissociation.model import (
    MechanismInput, ModelParameters, PopulationConfig, compare_conditions,
)
from research.dissociation.observable_model import (
    ALL_CHANNELS, PANELS, MeasurementConfig, expected_observables,
    sample_observables, select_channels, uncertainty_for,
)
from research.dissociation.parameter_recovery import DEFAULT_BOUNDS, HOLDOUT_CONDITIONS


def _replicate_populations(base: PopulationConfig, count: int, offset: int = 0):
    if count < 1:
        raise ValueError("replicates must be positive")
    return [
        replace(base, seed=base.seed + offset + i * 17)
        for i in range(count)
    ]


def expected_matrix(
    params: ModelParameters,
    conditions: Mapping[str, MechanismInput],
    populations: Sequence[PopulationConfig],
    *,
    panel: str,
    measurement: MeasurementConfig = MeasurementConfig(),
) -> np.ndarray:
    """Only transformed observable outputs cross this boundary."""
    if panel not in PANELS:
        raise ValueError(f"unknown panel: {panel}")
    arrays = []
    for population in populations:
        summaries = compare_conditions(dict(conditions), config=population, params=params)
        arrays.append(np.array([
            select_channels(expected_observables(summaries[name], measurement), panel)
            for name in conditions
        ]))
    return np.mean(arrays, axis=0)


def sampled_matrix(
    params: ModelParameters,
    conditions: Mapping[str, MechanismInput],
    populations: Sequence[PopulationConfig],
    *,
    panel: str,
    measurement: MeasurementConfig = MeasurementConfig(),
    observation_seed: int = 10021,
) -> np.ndarray:
    """Observed counts/noisy sensors only; no latent columns are returned."""
    rng = np.random.default_rng(observation_seed)
    observations = []
    for population in populations:
        summaries = compare_conditions(dict(conditions), config=population, params=params)
        observations.append(np.array([
            select_channels(sample_observables(summaries[name], rng, config=measurement), panel)
            for name in conditions
        ]))
    stacked = np.stack(observations, axis=0)
    with np.errstate(invalid="ignore"):
        valid = np.isfinite(stacked)
        counts = valid.sum(axis=0)
        sums = np.nansum(stacked, axis=0)
        return np.divide(
            sums, counts,
            out=np.full_like(sums, np.nan),
            where=counts > 0,
        )


def observable_jacobian(
    params: ModelParameters,
    bounds: dict[str, tuple[float, float]],
    conditions: Mapping[str, MechanismInput],
    populations: Sequence[PopulationConfig],
    *,
    panel: str,
    measurement: MeasurementConfig = MeasurementConfig(),
    epsilon_fraction: float = 0.035,
) -> np.ndarray:
    if not 0.0 < epsilon_fraction < 0.5:
        raise ValueError("epsilon_fraction must be in (0,0.5)")
    columns = []
    sigma = uncertainty_for(panel)[None, :]
    for name, (low, high) in bounds.items():
        center = getattr(params, name)
        span = (high - low) * epsilon_fraction
        plus_val = min(high, center + span)
        minus_val = max(low, center - span)
        if plus_val <= minus_val:
            raise ValueError(f"invalid differential range for {name}")
        plus = expected_matrix(
            replace(params, **{name: plus_val}), conditions, populations,
            panel=panel, measurement=measurement,
        )
        minus = expected_matrix(
            replace(params, **{name: minus_val}), conditions, populations,
            panel=panel, measurement=measurement,
        )
        # Common population seeds and expected observations eliminate noise-induced
        # artificial Jacobian rank. Noise affects separate recovery/validation.
        gradient = (plus - minus) / (plus_val - minus_val)
        columns.append((gradient / sigma).reshape(-1))
    return np.column_stack(columns)


def _normalized_loss(pred: np.ndarray, target: np.ndarray, panel: str) -> float:
    mask = np.isfinite(target)
    if not np.any(mask):
        return float("inf")
    residual = (pred - target) / uncertainty_for(panel)[None, :]
    return float(np.mean(np.square(residual[mask])))


def recover_from_observations(
    true_params: ModelParameters,
    bounds: dict[str, tuple[float, float]],
    conditions: Mapping[str, MechanismInput],
    population: PopulationConfig,
    *,
    panel: str,
    measurement: MeasurementConfig,
    target_replicates: int = 2,
    fit_replicates: int = 2,
    grid_points: int = 5,
    passes: int = 2,
    target_seed_offset: int = 300,
    fit_seed_offset: int = 1300,
) -> dict:
    """Fit coefficients to reports, not simulation latents.

    Target observations include noise and dropout; predictions are expected
    observable values generated using independent population seeds.
    """
    if grid_points < 3 or passes < 1:
        raise ValueError("grid_points must be >= 3 and passes >= 1")
    truth_pop = _replicate_populations(population, target_replicates, target_seed_offset)
    fit_pop = _replicate_populations(population, fit_replicates, fit_seed_offset)
    target = sampled_matrix(
        true_params, conditions, truth_pop,
        panel=panel, measurement=measurement,
        observation_seed=population.seed + 701,
    )
    if not np.any(np.isfinite(target)):
        return {"status": "no_observations"}

    estimated = ModelParameters()
    for name, (low, high) in bounds.items():
        estimated = replace(estimated, **{name: (low + high) / 2.0})
    windows = dict(bounds)
    for _ in range(passes):
        for name in bounds:
            low, high = windows[name]
            candidates = np.linspace(low, high, grid_points)
            losses = []
            for value in candidates:
                candidate = replace(estimated, **{name: float(value)})
                expected = expected_matrix(
                    candidate, conditions, fit_pop,
                    panel=panel, measurement=measurement,
                )
                losses.append((_normalized_loss(expected, target, panel), float(value)))
            _, best = min(losses)
            estimated = replace(estimated, **{name: best})
            global_low, global_high = bounds[name]
            radius = (high - low) * 0.23
            windows[name] = (max(global_low, best - radius),
                             min(global_high, best + radius))

    predicted = expected_matrix(
        estimated, conditions, fit_pop, panel=panel, measurement=measurement,
    )
    error = {
        name: abs(getattr(estimated, name) - getattr(true_params, name))
        / max(abs(getattr(true_params, name)), 1e-9)
        for name in bounds
    }

    holdout_target = sampled_matrix(
        true_params, HOLDOUT_CONDITIONS,
        _replicate_populations(population, target_replicates, 3300),
        panel=panel, measurement=measurement, observation_seed=population.seed + 1701,
    )
    holdout_expected = expected_matrix(
        estimated, HOLDOUT_CONDITIONS,
        _replicate_populations(population, fit_replicates, 4300),
        panel=panel, measurement=measurement,
    )
    oracle_expected = expected_matrix(
        true_params, HOLDOUT_CONDITIONS,
        _replicate_populations(population, fit_replicates, 4300),
        panel=panel, measurement=measurement,
    )
    return {
        "status": "fit",
        "observed_entries": int(np.isfinite(target).sum()),
        "possible_entries": int(target.size),
        "mean_parameter_relative_error": float(np.mean(list(error.values()))),
        "parameter_relative_errors": error,
        "estimated_parameters": {name: float(getattr(estimated, name)) for name in bounds},
        "fit_loss": _normalized_loss(predicted, target, panel),
        "heldout_loss": _normalized_loss(holdout_expected, holdout_target, panel),
        "heldout_oracle_noise_floor": _normalized_loss(oracle_expected, holdout_target, panel),
    }


def run_observable_design(
    *,
    population: PopulationConfig,
    measurement: MeasurementConfig = MeasurementConfig(),
    panels: Sequence[str] = ("switch_only", "observer_only", "observer_wearable", "multimodal"),
    replicates: int = 2,
    constraints: DesignConstraints = DesignConstraints(
        max_condition_number=15.0, min_singular_fraction=0.20,
    ),
    validation_seeds: Sequence[int] = (711,),
    recovery_check: bool = True,
    grid_points: int = 5,
    passes: int = 2,
) -> dict:
    measurement.validate()
    candidates = build_candidate_library()
    bounds = dict(DEFAULT_BOUNDS)
    params = ModelParameters()
    selected_panels = {}
    for panel in panels:
        if panel not in PANELS:
            raise ValueError(f"unknown panel {panel}")
        populations = _replicate_populations(population, replicates, 2000)
        jac = observable_jacobian(
            params, bounds, candidates, populations, panel=panel, measurement=measurement,
        )
        blocks = _blocks_from_jacobian(jac, len(candidates), len(PANELS[panel]))
        plan = optimize_blocks(blocks, list(candidates), constraints=constraints)
        validations = []
        if plan["status"] == "feasible":
            for seed in validation_seeds:
                val_pops = _replicate_populations(
                    replace(population, seed=int(seed)), replicates, 3000,
                )
                val_jac = observable_jacobian(
                    params, bounds, candidates, val_pops,
                    panel=panel, measurement=measurement,
                )
                val_blocks = _blocks_from_jacobian(
                    val_jac, len(candidates), len(PANELS[panel]),
                )
                full = score_matrix(
                    _chosen_matrix(val_blocks, list(range(len(candidates)))), constraints,
                )
                chosen = score_matrix(
                    _chosen_matrix(
                        val_blocks,
                        [list(candidates).index(name) for name in plan["selected"]],
                    ),
                    constraints,
                )
                validations.append({
                    "seed": seed,
                    "passed": _is_feasible(chosen, full, len(bounds), constraints),
                    "full": full.to_dict(),
                    "selected": chosen.to_dict(),
                })

        fit = None
        full_fit = None
        if plan["status"] == "feasible" and recovery_check:
            chosen_conditions = {name: candidates[name] for name in plan["selected"]}
            fit = recover_from_observations(
                params, bounds, chosen_conditions, population,
                panel=panel, measurement=measurement, grid_points=grid_points,
                passes=passes, target_replicates=replicates, fit_replicates=replicates,
            )
            full_fit = recover_from_observations(
                params, bounds, candidates, population,
                panel=panel, measurement=measurement, grid_points=grid_points,
                passes=passes, target_replicates=replicates, fit_replicates=replicates,
            )
        selected_panels[panel] = {
            "channels": list(PANELS[panel]),
            "plan": plan,
            "validation": validations,
            "validation_passed": (
                plan["status"] == "feasible"
                and bool(validations)
                and all(v["passed"] for v in validations)
            ),
            "reduced_recovery": fit,
            "full_recovery": full_fit,
        }
    return {
        "schema_version": 1,
        "warning": (
            "Synthetic observable PROXIES, including invented wearable/EEG readouts. "
            "No real-patient identifiability or safe human drug challenge implied."
        ),
        "population": asdict(population),
        "measurement": asdict(measurement),
        "constraints": asdict(constraints),
        "parameter_names": list(bounds),
        "candidate_conditions": {name: asdict(value) for name, value in candidates.items()},
        "panels": selected_panels,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=180)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=103)
    p.add_argument("--replicates", type=int, default=2)
    p.add_argument("--missing", type=float, default=0.10)
    p.add_argument("--max-condition", type=float, default=15.0)
    p.add_argument("--min-singular-fraction", type=float, default=0.20)
    p.add_argument("--panels", nargs="+", choices=list(PANELS),
                   default=list(PANELS))
    p.add_argument("--validation-seeds", nargs="+", type=int, default=[711])
    p.add_argument("--skip-recovery", action="store_true")
    p.add_argument("--grid-points", type=int, default=5)
    p.add_argument("--passes", type=int, default=2)
    p.add_argument("--output", default="runs/dissociation_observable_design.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    report = run_observable_design(
        population=PopulationConfig(args.subjects, args.steps, args.seed),
        measurement=MeasurementConfig(missing_probability=args.missing),
        panels=args.panels,
        replicates=args.replicates,
        constraints=DesignConstraints(
            max_condition_number=args.max_condition,
            min_singular_fraction=args.min_singular_fraction,
        ),
        validation_seeds=args.validation_seeds,
        recovery_check=not args.skip_recovery,
        grid_points=args.grid_points,
        passes=args.passes,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote observable design audit to {output}")
    for panel, record in report["panels"].items():
        plan = record["plan"]
        print(f"panel={panel} status={plan['status']} "
              f"full_rank={plan['reference']['numerical_rank']}/5 "
              f"selected={','.join(plan['selected'])} "
              f"validation_passed={record['validation_passed']}")
        if record["reduced_recovery"]:
            d, f = record["reduced_recovery"], record["full_recovery"]
            print(f"  reduced_recovery={d['mean_parameter_relative_error']:.3f} "
                  f"full_recovery={f['mean_parameter_relative_error']:.3f} "
                  f"reduced_holdout={d['heldout_loss']:.3f} "
                  f"full_holdout={f['heldout_loss']:.3f} "
                  f"oracle_noise_floor={d['heldout_oracle_noise_floor']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
