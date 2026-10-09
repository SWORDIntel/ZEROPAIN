"""Repeated-seed null benchmark stability tests."""

from research.dissociation.longitudinal_null_stability import run_stability
from research.dissociation.longitudinal_nulls import LongitudinalConfig
from research.dissociation.observable_model import MeasurementConfig


def test_stability_reports_all_truth_families_and_health_fields():
    result = run_stability(
        seeds=2,
        config=LongitudinalConfig(
            subjects=3,
            sessions=10,
            micro_population=30,
            steps_per_session=10,
            seed=5,
            test_fraction=0.3,
        ),
        measurement=MeasurementConfig(missing_probability=0.0),
    )
    assert set(result["summary"]) == {"receptor", "context", "mixed"}
    for truth, summary in result["summary"].items():
        assert summary["runs"] == 2
        assert (
            sum(summary["winner_counts"].values()) == 2
        )
    assert "passed" in result["benchmark_health"]
