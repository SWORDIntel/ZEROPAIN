"""Tests for longitudinal competing-null model benchmark."""

from research.dissociation.longitudinal_nulls import (
    LongitudinalConfig,
    benchmark_truth,
    discrimination_diagnostics,
    generate_panel,
    permute_mechanisms_within_subject,
    run_benchmark,
    score_models,
)
from research.dissociation.observable_model import MeasurementConfig


SMALL = LongitudinalConfig(
    subjects=3,
    sessions=10,
    micro_population=35,
    steps_per_session=12,
    seed=22,
    test_fraction=0.3,
)


def test_generate_panel_has_expected_longitudinal_shape_and_covariates():
    rows = generate_panel(
        "receptor",
        config=SMALL,
        measurement=MeasurementConfig(missing_probability=0.0),
    )
    assert len(rows) == SMALL.subjects * SMALL.sessions
    assert {"subject", "session", "stress_load", "meth", "observer_switch_rate"} <= set(rows[0])


def test_context_truth_is_not_forced_to_require_mechanism_features():
    result = benchmark_truth(
        "context",
        config=SMALL,
        measurement=MeasurementConfig(missing_probability=0.0),
    )
    by_name = {row["model"]: row for row in result["scores"]}
    # The benchmark is allowed to be noisy, but the context model should not be
    # dramatically worse than mechanism-only under context-generated truth.
    assert by_name["context_history"]["test_mse"] <= 1.5 * by_name["mechanism_only"]["test_mse"]


def test_mechanism_permutation_preserves_row_count_and_context():
    rows = generate_panel(
        "mixed",
        config=SMALL,
        measurement=MeasurementConfig(missing_probability=0.0),
    )
    shuffled = permute_mechanisms_within_subject(rows, seed=99)
    assert len(shuffled) == len(rows)
    for a, b in zip(rows, shuffled):
        assert a["subject"] == b["subject"]
        assert a["session"] == b["session"]
        assert a["stress_load"] == b["stress_load"]
        assert a["sleep_wake_irregularity"] == b["sleep_wake_irregularity"]


def test_score_models_returns_all_candidate_families():
    rows = generate_panel(
        "receptor",
        config=SMALL,
        measurement=MeasurementConfig(missing_probability=0.05),
    )
    scores = score_models(rows, config=SMALL)
    names = {score.model for score in scores}
    assert {
        "mean_only",
        "history_only",
        "context_only",
        "context_history",
        "mechanism_only",
        "context_plus_mechanism",
        "full",
    } == names
    assert all(score.observed_test_values > 0 for score in scores)


def test_full_benchmark_runs_all_truth_families():
    report = run_benchmark(
        config=SMALL,
        measurement=MeasurementConfig(missing_probability=0.05),
    )
    assert set(report["results"]) == {"receptor", "context", "mixed"}
    for result in report["results"].values():
        assert result["best_test_model"]
        assert result["permuted_best_test_model"]



def test_discrimination_diagnostic_uses_effect_sizes_not_only_rank():
    from research.dissociation.longitudinal_nulls import ModelScore

    def score(name, mse):
        return ModelScore(
            model=name,
            parameters=1,
            observed_test_values=20,
            test_mse=mse,
            test_rmse=mse ** 0.5,
            test_r2=0.0,
            train_bic=0.0,
        )

    original = [
        score("context_history", 1.0),
        score("mechanism_only", 0.8),
        score("full", 0.75),
    ]
    permuted = [
        score("context_history", 1.0),
        score("mechanism_only", 1.1),
        score("full", 1.0),
    ]
    result = discrimination_diagnostics(original, permuted)
    assert result["status"] == "ok"
    assert result["mechanism_gain_over_null_fraction"] > 0
    assert result["mechanism_permutation_penalty_fraction"] > 0
