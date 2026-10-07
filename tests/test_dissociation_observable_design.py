"""Observable-only measurement and design tests."""

from dataclasses import replace

import numpy as np
import pytest

from research.dissociation.model import (
    MechanismInput, ModelParameters, PopulationConfig, SimulationSummary,
)
from research.dissociation.observable_model import (
    ALL_CHANNELS, PANELS, MeasurementConfig, expected_observables,
    sample_observables, select_channels, uncertainty_for,
)
from research.dissociation.observable_design import (
    expected_matrix, observable_jacobian, recover_from_observations,
    run_observable_design,
)
from research.dissociation.experimental_design import DesignConstraints


SUMMARY = SimulationSummary(
    mean_switches=30.0,
    median_switches=28.0,
    mean_switch_probability=0.20,
    mean_persistence_steps=5.0,
    executive_stability=0.70,
    cortical_integration=0.80,
    internal_coordination=0.60,
    information_consistency=0.68,
    salience_load=0.30,
)


def test_measurement_adapter_is_noisy_and_not_direct_latents():
    config = MeasurementConfig(missing_probability=0.0)
    expected = expected_observables(SUMMARY, config)
    assert set(expected) == set(ALL_CHANNELS)
    assert expected["observer_switch_rate"] != SUMMARY.mean_switch_probability
    assert expected["paired_recall_success"] != SUMMARY.information_consistency
    assert 0.0 <= expected["morning_plan_agreement"] <= 1.0
    assert uncertainty_for("observer_only").shape == (3,)

    sampled = sample_observables(SUMMARY, np.random.default_rng(9), config=config)
    assert all(np.isfinite(list(sampled.values())))
    assert all(0 <= sampled[key] <= 1 for key in ALL_CHANNELS[:3])


def test_missingness_is_explicit_not_imputed_to_zero():
    config = MeasurementConfig(missing_probability=1.0)
    sampled = sample_observables(SUMMARY, np.random.default_rng(7), config=config)
    assert all(np.isnan(value) for value in sampled.values())
    with pytest.raises(ValueError):
        select_channels(sampled, "bad_panel")
    with pytest.raises(ValueError):
        MeasurementConfig(missing_probability=1.2).validate()


def test_observable_jacobian_does_not_include_hidden_metrics_and_is_reproducible():
    conditions = {
        "baseline": MechanismInput(),
        "meth": MechanismInput(meth=0.5),
        "nmda": MechanismInput(nmda_antagonism=0.5),
    }
    bounds = {
        "meth_salience_weight": (0.30, 1.80),
        "nmda_integration_weight": (0.40, 1.60),
    }
    pop = [PopulationConfig(n_subjects=80, steps=16, seed=33)]
    j1 = observable_jacobian(
        ModelParameters(), bounds, conditions, pop, panel="observer_only"
    )
    j2 = observable_jacobian(
        ModelParameters(), bounds, conditions, pop, panel="observer_only"
    )
    assert j1.shape == (3 * len(conditions), len(bounds))
    assert np.all(np.isfinite(j1))
    assert np.allclose(j1, j2)
    assert expected_matrix(
        ModelParameters(), conditions, pop, panel="multimodal"
    ).shape == (3, 5)


def test_recovery_reports_observed_entries_and_holdout_noise_floor():
    conditions = {
        "baseline": MechanismInput(),
        "meth": MechanismInput(meth=0.65),
        "nmda": MechanismInput(nmda_antagonism=0.65),
    }
    truth = replace(
        ModelParameters(), meth_salience_weight=1.18, nmda_integration_weight=1.08
    )
    bounds = {
        "meth_salience_weight": (0.45, 1.70),
        "nmda_integration_weight": (0.50, 1.55),
    }
    result = recover_from_observations(
        truth, bounds, conditions,
        PopulationConfig(n_subjects=100, steps=24, seed=15),
        panel="multimodal",
        measurement=MeasurementConfig(missing_probability=0.0),
        grid_points=5, passes=2, target_replicates=1, fit_replicates=1,
    )
    assert result["status"] == "fit"
    assert result["observed_entries"] == result["possible_entries"]
    assert np.isfinite(result["fit_loss"])
    assert np.isfinite(result["heldout_loss"])
    assert np.isfinite(result["heldout_oracle_noise_floor"])


def test_panel_ablation_reports_failures_without_making_up_rank():
    result = run_observable_design(
        population=PopulationConfig(n_subjects=65, steps=18, seed=51),
        measurement=MeasurementConfig(missing_probability=0.0),
        panels=("switch_only", "multimodal"),
        replicates=1,
        constraints=DesignConstraints(
            max_condition_number=100, min_singular_fraction=0.05,
        ),
        validation_seeds=(121,),
        recovery_check=False,
    )
    assert set(result["panels"]) == {"switch_only", "multimodal"}
    for name, record in result["panels"].items():
        assert record["channels"] == list(PANELS[name])
        assert 0 <= record["plan"]["reference"]["numerical_rank"] <= 5
        if record["plan"]["status"] == "feasible":
            assert record["plan"]["selected"]
            assert "validation_passed" in record
