from research.dissociation.model_selection_stability import run_selection_stability


def test_selection_stability_runs_repeated_synthetic_datasets():
    result = run_selection_stability(
        seeds=2,
        steps=100,
        n_states=4,
        base_seed=3,
        transient_lags=2,
        test_every=5,
    )

    assert len(result["rows"]) == 2 * 4
    for scenario, record in result["summary"].items():
        assert record["runs"] == 2
        total_rmse_wins = sum(
            metrics["test_rmse_wins"]
            for metrics in record["models"].values()
        )
        total_bic_wins = sum(
            metrics["bic_wins"]
            for metrics in record["models"].values()
        )
        assert total_rmse_wins == 2
        assert total_bic_wins == 2
