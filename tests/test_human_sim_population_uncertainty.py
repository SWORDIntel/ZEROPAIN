import numpy as np

from research.human_sim.population import load_httkpop_csv
from research.human_sim.population_uncertainty import (
    bootstrap_outcome_report,
    correlation_report,
    percentile_bootstrap_interval,
)


def test_bootstrap_interval_is_reproducible_and_contains_estimate():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    a = percentile_bootstrap_interval(values, resamples=200, seed=7)
    b = percentile_bootstrap_interval(values, resamples=200, seed=7)
    assert a == b
    assert a.lower <= a.estimate <= a.upper
    assert a.resamples == 200


def test_correlation_report_preserves_imported_population_structure():
    people = load_httkpop_csv("research/human_sim/examples/httkpop_synthetic_fixture.csv")
    report = correlation_report(people)
    assert report["status"] == "ok"
    assert report["n"] == len(people)
    matrix = np.asarray(report["matrix"], dtype=float)
    assert matrix.shape[0] == len(report["variables"])
    assert matrix.shape[0] == matrix.shape[1]


def test_bootstrap_outcome_report_keeps_sampling_uncertainty_separate():
    report = bootstrap_outcome_report(
        {
            "brain_peak": [0.1, 0.15, 0.2, 0.25, 0.3],
            "signal": [0.4, 0.45, 0.5, 0.55, 0.6],
        },
        resamples=100,
        seed=11,
    )
    assert report["brain_peak"]["status"] == "ok"
    assert report["brain_peak"]["median"]["confidence"] == 0.95
    assert report["signal"]["mean"]["resamples"] == 100
