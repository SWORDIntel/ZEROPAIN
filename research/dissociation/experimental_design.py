"""Greedy experimental design and leave-one-condition-out ablation.

Find the smallest *heuristic* subset of synthetic perturbation conditions that preserves
the local rank and numerical conditioning of a reference Jacobian. This is model
experimental design, NOT a human study protocol or a dosing tool.

Key safeguards:
* One Jacobian is computed for the entire candidate pool; metric scales do not
  change when individual conditions are removed.
* The primary optimisation is greedy and not guaranteed globally minimal.
* Local rank is necessary but insufficient: constrain condition number AND smallest
  singular value relative to the full experiment.
* Candidate selection uses training seeds; validation uses independent seeds.
* Ablation of full-pool conditions quantifies uniqueness/redundancy.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from research.dissociation.identifiability import finite_difference_jacobian
from research.dissociation.model import MechanismInput, ModelParameters, PopulationConfig
from research.dissociation.parameter_recovery import (
    DEFAULT_BOUNDS, FIT_CONDITIONS, FIT_METRICS,
)


def build_candidate_library() -> dict[str, MechanismInput]:
    """Dimensionless model conditions; NOT concentrations or administration regimens."""
    return {
        **FIT_CONDITIONS,
        "meth_nmda": MechanismInput(meth=0.55, nmda_antagonism=0.45),
        "meth_mor": MechanismInput(meth=0.55, mor_partial_agonism=0.55),
        "meth_kor": MechanismInput(meth=0.55, kor_antagonism=0.55),
        "nmda_mor": MechanismInput(nmda_antagonism=0.50, mor_partial_agonism=0.55),
        "nmda_kor": MechanismInput(nmda_antagonism=0.50, kor_antagonism=0.55),
        "mor_kor": MechanismInput(mor_partial_agonism=0.55, kor_antagonism=0.55),
        "meth_wake": MechanismInput(meth=0.55, wake_anchor_disruption=0.65),
        "nmda_wake": MechanismInput(nmda_antagonism=0.50, wake_anchor_disruption=0.65),
        "meth_nmda_wake": MechanismInput(
            meth=0.50, nmda_antagonism=0.45, wake_anchor_disruption=0.55,
        ),
        "meth_mor_kor": MechanismInput(
            meth=0.50, mor_partial_agonism=0.50, kor_antagonism=0.50,
        ),
        "nmda_mor_kor": MechanismInput(
            nmda_antagonism=0.50, mor_partial_agonism=0.50, kor_antagonism=0.50,
        ),
    }


@dataclass(frozen=True)
class DesignConstraints:
    max_condition_number: float = 6.0
    min_singular_fraction: float = 0.35
    rank_tolerance: float = 1e-6
    ridge: float = 1e-8
    budget: int = 0   # zero -> unlimited
    require_baseline: bool = True

    def validate(self) -> None:
        if self.max_condition_number < 1:
            raise ValueError("max_condition_number must be >= 1")
        if not 0 < self.min_singular_fraction <= 1:
            raise ValueError("min_singular_fraction must be in (0,1]")
        if not 0 < self.rank_tolerance < 1:
            raise ValueError("rank_tolerance must be in (0,1)")
        if self.ridge <= 0:
            raise ValueError("ridge must be positive")
        if self.budget < 0:
            raise ValueError("budget must be >= 0")


@dataclass(frozen=True)
class MatrixScore:
    numerical_rank: int
    condition_number: float
    min_singular_value: float
    max_singular_value: float
    logdet_fisher_regularized: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def score_matrix(matrix: np.ndarray, constraints: DesignConstraints) -> MatrixScore:
    if matrix.ndim != 2:
        raise ValueError("matrix must be two-dimensional")
    p = matrix.shape[1]
    if p == 0:
        raise ValueError("matrix must have at least one parameter column")
    singular = np.linalg.svd(matrix, compute_uv=False)
    # pad to P singular values when observations < parameters
    singular = np.pad(singular, (0, max(0, p - singular.size)))[:p]
    largest = float(singular[0])
    smallest = float(singular[-1])
    rank = int(np.count_nonzero(singular > constraints.rank_tolerance * max(largest, 1e-12)))
    condition = largest / smallest if smallest > 1e-12 else float("inf")
    logdet = float(np.sum(np.log(singular * singular + constraints.ridge)))
    return MatrixScore(rank, condition, smallest, largest, logdet)


def _chosen_matrix(blocks: np.ndarray, indices: Sequence[int]) -> np.ndarray:
    if blocks.ndim != 3:
        raise ValueError("Jacobian blocks must have shape (conditions, metrics, parameters)")
    if not indices:
        return np.zeros((0, blocks.shape[2]), dtype=float)
    return blocks[np.asarray(indices, dtype=int)].reshape(-1, blocks.shape[2])


def feasible(
    candidate: MatrixScore,
    full: MatrixScore,
    constraints: DesignConstraints,
) -> bool:
    return (
        candidate.numerical_rank == full.numerical_rank == full_parameter_count(full, candidate)
        and candidate.condition_number <= constraints.max_condition_number
        and candidate.min_singular_value
        >= constraints.min_singular_fraction * full.min_singular_value
    )


def full_parameter_count(full: MatrixScore, candidate: MatrixScore) -> int:
    # Feasibility requires full-column rank, not merely parity with a rank-deficient
    # reference. The caller enforces reference full rank before optimisation.
    return full.numerical_rank


def _is_feasible(
    candidate: MatrixScore,
    full: MatrixScore,
    n_parameters: int,
    constraints: DesignConstraints,
) -> bool:
    return (
        full.numerical_rank == n_parameters
        and candidate.numerical_rank == n_parameters
        and candidate.condition_number <= constraints.max_condition_number
        and candidate.min_singular_value >= constraints.min_singular_fraction * full.min_singular_value
    )


def optimize_blocks(
    blocks: np.ndarray,
    names: Sequence[str],
    *,
    constraints: DesignConstraints = DesignConstraints(),
) -> dict:
    """Rank-first greedy forward selection and feasibility-preserving backward deletion.

    The heuristic is stable under candidate order changes given identical names.
    """
    constraints.validate()
    blocks = np.asarray(blocks, dtype=float)
    if blocks.ndim != 3 or blocks.shape[0] != len(names):
        raise ValueError("expected one Jacobian block per named condition")
    if len(set(names)) != len(names):
        raise ValueError("candidate condition names must be unique")
    if not np.all(np.isfinite(blocks)):
        raise ValueError("Jacobian contains non-finite values")
    if not names:
        raise ValueError("at least one condition is required")

    n_parameters = blocks.shape[2]
    full_score = score_matrix(_chosen_matrix(blocks, list(range(len(names)))), constraints)
    if full_score.numerical_rank != n_parameters:
        return {
            "status": "reference_rank_deficient",
            "selected": [], "history": [],
            "reference": full_score.to_dict(),
            "message": "Candidate library cannot distinguish all selected parameters.",
        }

    required = ["baseline"] if constraints.require_baseline and "baseline" in names else []
    selected = list(required)
    history = []
    limit = constraints.budget or len(names)

    def score_selected(chosen: Sequence[str]) -> MatrixScore:
        return score_matrix(
            _chosen_matrix(blocks, [names.index(x) for x in chosen]),
            constraints,
        )

    while not _is_feasible(score_selected(selected), full_score, n_parameters, constraints):
        if len(selected) >= limit:
            break
        candidates = []
        for name in names:
            if name in selected:
                continue
            s = score_selected([*selected, name])
            # First obtain rank; then maximize information while constraining
            # condition number and minimum singular value. The D-opt criterion
            # acts as a deterministic tie-breaker during greedy expansion.
            rank_gain = s.numerical_rank
            information_ratio = (
                s.min_singular_value / max(full_score.min_singular_value, 1e-12)
            )
            capped_condition = (
                min(s.condition_number, 1e12)
                if np.isfinite(s.condition_number)
                else 1e12
            )
            candidates.append((
                _is_feasible(s, full_score, n_parameters, constraints),
                rank_gain,
                min(information_ratio, 1.0),
                -capped_condition,
                s.logdet_fisher_regularized,
                name,
                s,
            ))
        if not candidates:
            break
        # Lexically stable tie-break: sorted names first and strict > comparison.
        best = None
        for cand in sorted(candidates, key=lambda item: item[5]):
            if best is None or cand[:5] > best[:5]:
                best = cand
        assert best is not None
        chosen = best[5]
        selected.append(chosen)
        history.append({
            "action": "add", "condition": chosen,
            "score": best[6].to_dict(),
        })

    if not _is_feasible(score_selected(selected), full_score, n_parameters, constraints):
        return {
            "status": "budget_or_constraints_infeasible",
            "selected": selected, "history": history,
            "reference": full_score.to_dict(),
            "selected_score": score_selected(selected).to_dict(),
            "message": "No feasible design found under supplied budget/constraints.",
        }

    # Prefer to remove the least useful member first; never remove the required
    # baseline even though it may have zero local parameter derivatives.
    while True:
        removable = []
        for name in selected:
            if name in required:
                continue
            reduced = [x for x in selected if x != name]
            score = score_selected(reduced)
            if _is_feasible(score, full_score, n_parameters, constraints):
                removable.append((score.logdet_fisher_regularized, name, reduced, score))
        if not removable:
            break
        # Remove condition that sacrifices least information (highest retained logdet)
        removable.sort(key=lambda row: (-row[0], row[1]))
        _, removed, remaining, score = removable[0]
        selected = remaining
        history.append({"action": "remove", "condition": removed, "score": score.to_dict()})

    # Full-pool leave-one-out ablation with a common normalization.
    ablation = []
    all_indices = list(range(len(names)))
    for idx, name in enumerate(names):
        left = [i for i in all_indices if i != idx]
        score = score_matrix(_chosen_matrix(blocks, left), constraints)
        ablation.append({
            "condition": name,
            "remaining_rank": score.numerical_rank,
            "remaining_condition": score.condition_number,
            "remaining_min_singular_fraction":
                score.min_singular_value / max(full_score.min_singular_value, 1e-12),
            "lost_information_logdet":
                full_score.logdet_fisher_regularized - score.logdet_fisher_regularized,
        })
    ablation.sort(key=lambda row: (-row["lost_information_logdet"], row["condition"]))

    return {
        "status": "feasible",
        "selected": selected,
        "selected_count": len(selected),
        "full_count": len(names),
        "selection_fraction": len(selected) / len(names),
        "reference": full_score.to_dict(),
        "selected_score": score_selected(selected).to_dict(),
        "history": history,
        "leave_one_out_ablation": ablation,
    }


def _blocks_from_jacobian(
    matrix: np.ndarray, condition_count: int, metric_count: int,
) -> np.ndarray:
    expected = condition_count * metric_count
    if matrix.ndim != 2 or matrix.shape[0] != expected:
        raise ValueError(f"Jacobian row count {matrix.shape[0]} != expected {expected}")
    return matrix.reshape(condition_count, metric_count, matrix.shape[1])


def validate_selection(
    *,
    selected: Sequence[str],
    candidates: Mapping[str, MechanismInput],
    bounds: dict[str, tuple[float, float]],
    params: ModelParameters,
    population: PopulationConfig,
    constraints: DesignConstraints,
    seeds: Sequence[int],
    replicates: int,
) -> list[dict]:
    """Validate chosen design against complete reference on independent seeds."""
    results = []
    for seed in seeds:
        validation_pop = replace(population, seed=seed)
        jac, _, parameter_names = finite_difference_jacobian(
            params, bounds, population=validation_pop,
            conditions=dict(candidates), replicates=replicates, seed_offset=2500,
        )
        blocks = _blocks_from_jacobian(jac, len(candidates), len(FIT_METRICS))
        ordered_names = list(candidates)
        full = score_matrix(_chosen_matrix(blocks, range(len(ordered_names))), constraints)
        reduced = score_matrix(_chosen_matrix(
            blocks, [ordered_names.index(name) for name in selected],
        ), constraints)
        results.append({
            "seed": seed,
            "parameters": parameter_names,
            "reference": full.to_dict(),
            "selected": reduced.to_dict(),
            "passed": _is_feasible(reduced, full, len(bounds), constraints),
        })
    return results


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=400)
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--seed", type=int, default=111)
    p.add_argument("--replicates", type=int, default=2)
    p.add_argument("--validation-seeds", type=int, nargs="*", default=[211, 311])
    p.add_argument("--max-condition", type=float, default=6.0)
    p.add_argument("--min-information-fraction", type=float, default=0.35)
    p.add_argument("--budget", type=int, default=0)
    p.add_argument("--parameters", nargs="+", default=list(DEFAULT_BOUNDS),
                   choices=list(DEFAULT_BOUNDS))
    p.add_argument("--output", default="runs/dissociation_experiment_design.json")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    candidates = build_candidate_library()
    params = ModelParameters()
    bounds = {name: DEFAULT_BOUNDS[name] for name in args.parameters}
    population = PopulationConfig(args.subjects, args.steps, args.seed)
    constraints = DesignConstraints(
        max_condition_number=args.max_condition,
        min_singular_fraction=args.min_information_fraction,
        budget=args.budget,
    )
    jac, scales, names = finite_difference_jacobian(
        params, bounds, population=population, conditions=candidates,
        replicates=args.replicates, seed_offset=2000,
    )
    blocks = _blocks_from_jacobian(jac, len(candidates), len(FIT_METRICS))
    plan = optimize_blocks(blocks, list(candidates), constraints=constraints)
    validations = (
        validate_selection(
            selected=plan["selected"], candidates=candidates, bounds=bounds,
            params=params, population=population, constraints=constraints,
            seeds=args.validation_seeds, replicates=args.replicates,
        )
        if plan["status"] == "feasible" else []
    )
    payload = {
        "schema_version": 1,
        "warning": "Synthetic dimensionless model conditions, NOT human exposures or doses.",
        "selection_algorithm": "rank-first greedy + backward ablation; not proven global optimum",
        "parameter_names": names,
        "metric_names": list(FIT_METRICS),
        "metric_scales": scales.tolist(),
        "population": asdict(population),
        "constraints": asdict(constraints),
        "candidates": {name: asdict(value) for name, value in candidates.items()},
        "plan": plan,
        "independent_seed_validation": validations,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote experimental-design audit to {out}")
    print(f"status={plan['status']}")
    print(f"reference rank={plan['reference']['numerical_rank']} "
          f"condition={plan['reference']['condition_number']:.3f}")
    if plan["status"] == "feasible":
        print(f"selected={','.join(plan['selected'])}")
        print(f"count={plan['selected_count']}/{plan['full_count']} "
              f"condition={plan['selected_score']['condition_number']:.3f} "
              f"minimum_singular={plan['selected_score']['min_singular_value']:.4f}")
        for val in validations:
            print(f"validation seed={val['seed']} passed={val['passed']} "
                  f"rank={val['selected']['numerical_rank']} "
                  f"condition={val['selected']['condition_number']:.3f}")
    return 0 if plan["status"] == "feasible" else 2


if __name__ == "__main__":
    raise SystemExit(main())
