"""Synthetic linear-algebra invariants for experimental-design selection."""

import numpy as np
import pytest

from research.dissociation.experimental_design import (
    DesignConstraints,
    _blocks_from_jacobian,
    optimize_blocks,
    score_matrix,
)


def test_selects_two_independent_conditions_and_required_baseline():
    # Baseline is rank zero; each useful condition measures one independent
    # mechanism. The combined signal alone cannot identify two parameters.
    blocks = np.array([
        [[0.0, 0.0]],  # baseline
        [[1.0, 0.0]],  # meth
        [[0.0, 1.0]],  # nmda
        [[1.0, 1.0]],  # combined
    ])
    names = ["baseline", "meth", "nmda", "combined"]
    plan = optimize_blocks(blocks, names, constraints=DesignConstraints(
        max_condition_number=3.0,
        min_singular_fraction=0.30,
        require_baseline=True,
    ))
    assert plan["status"] == "feasible"
    assert "baseline" in plan["selected"]
    assert len(plan["selected"]) == 3  # mandatory baseline + two distinct rows
    assert plan["selected_score"]["numerical_rank"] == 2
    assert plan["selected_score"]["condition_number"] <= 3.0


def test_ablation_detects_uniquely_necessary_condition():
    blocks = np.array([
        [[0.0, 0.0]],
        [[1.0, 0.0]],
        [[0.0, 1.0]],
        [[2.0, 0.0]],
    ])
    names = ["baseline", "m1", "n", "m2"]
    plan = optimize_blocks(blocks, names, constraints=DesignConstraints(
        max_condition_number=10.0,
        min_singular_fraction=0.10,
    ))
    assert plan["status"] == "feasible"
    n_ablation = next(
        row for row in plan["leave_one_out_ablation"] if row["condition"] == "n"
    )
    assert n_ablation["remaining_rank"] == 1


def test_rank_deficient_pool_is_not_reported_as_success():
    blocks = np.array([
        [[1.0, 2.0]],
        [[2.0, 4.0]],
    ])
    plan = optimize_blocks(blocks, ["x", "y"], constraints=DesignConstraints(
        require_baseline=False,
    ))
    assert plan["status"] == "reference_rank_deficient"


def test_budget_failure_remains_explicit():
    blocks = np.array([
        [[0.0, 0.0]],
        [[1.0, 0.0]],
        [[0.0, 1.0]],
    ])
    plan = optimize_blocks(blocks, ["baseline", "x", "y"], constraints=DesignConstraints(
        budget=2, require_baseline=True,
    ))
    assert plan["status"] == "budget_or_constraints_infeasible"
    assert len(plan["selected"]) == 2


def test_common_scales_shape_validation_and_order_independence():
    jac = np.eye(4, dtype=float)
    blocks = _blocks_from_jacobian(jac, condition_count=2, metric_count=2)
    assert blocks.shape == (2, 2, 4)
    with pytest.raises(ValueError):
        _blocks_from_jacobian(jac, condition_count=3, metric_count=2)
    assert score_matrix(np.eye(3), DesignConstraints()).numerical_rank == 3

    blocks = np.array([
        [[0.0, 0.0]],
        [[1.0, 0.0]],
        [[0.0, 1.0]],
        [[1.0, 1.0]],
    ])
    names = ["baseline", "x", "y", "both"]
    a = optimize_blocks(blocks, names, constraints=DesignConstraints(
        max_condition_number=10.0, min_singular_fraction=0.1,
    ))
    permutation = [3, 1, 0, 2]
    b = optimize_blocks(blocks[permutation], [names[i] for i in permutation],
                        constraints=DesignConstraints(
                            max_condition_number=10.0,
                            min_singular_fraction=0.1,
                        ))
    assert sorted(a["selected"]) == sorted(b["selected"])
