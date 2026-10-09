import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.observation_model import (
    ObservationConfig,
    _make_state_signatures,
    _mixture_weights,
    simulate_observations,
)
from research.dissociation.state_network import StateNetworkTrace


def _trace(executive, coconscious):
    n = len(executive)
    return StateNetworkTrace(
        executive=list(executive),
        coconscious=list(coconscious),
        mean_trust=[0.8] * n,
        memory_consistency=[0.9] * n,
        withholding_events=[0] * n,
    )


def test_blend_weights_are_convex_and_include_executive():
    weights = _mixture_weights((0, 1, 2), executive=0, n_states=4, executive_weight=0.70)
    assert np.isclose(np.sum(weights), 1.0)
    assert np.all(weights >= 0.0)
    assert weights[0] == 0.70
    assert weights[3] == 0.0


def test_zero_noise_blend_matches_linear_mixture_without_switch_transient():
    trace = _trace([0, 0, 0], [(0, 1), (0, 1), (0, 1)])
    config = ObservationConfig(
        n_states=4,
        seed=3,
        base_noise_sd=0.0,
        switch_transient_amplitude=0.0,
        perturbation_shift_scale=0.0,
    )
    result = simulate_observations(trace, MechanismInput(), config=config)
    assert np.allclose(result.features, result.expected_mixture)


def test_switch_generates_larger_residual_than_nonswitch_in_zero_noise_case():
    trace = _trace(
        [0, 0, 1, 1, 2, 2],
        [(0,), (0,), (1,), (1,), (2,), (2,)],
    )
    config = ObservationConfig(
        n_states=4,
        seed=5,
        base_noise_sd=0.0,
        perturbation_shift_scale=0.0,
        switch_transient_amplitude=1.0,
        switch_transient_decay=0.0,
    )
    result = simulate_observations(trace, MechanismInput(), config=config)
    assert result.summary.switch_transient_mean_norm > result.summary.nonswitch_mean_residual_norm


def test_distinct_state_signatures_are_classifiable_at_low_noise():
    executive = [0] * 30 + [1] * 30 + [2] * 30 + [3] * 30
    coconscious = [(state,) for state in executive]
    trace = _trace(executive, coconscious)
    config = ObservationConfig(
        n_states=4,
        seed=7,
        state_separation=2.0,
        base_noise_sd=0.03,
        switch_transient_amplitude=0.0,
        perturbation_shift_scale=0.0,
    )
    result = simulate_observations(trace, MechanismInput(), config=config)
    assert result.summary.nearest_signature_accuracy_pure > 0.95


def test_meth_nmda_increase_observation_noise_under_default_hypothesis():
    executive = [0] * 40 + [1] * 40
    coconscious = [(state,) for state in executive]
    trace = _trace(executive, coconscious)
    config = ObservationConfig(
        n_states=4,
        seed=11,
        base_noise_sd=0.15,
        switch_transient_amplitude=0.0,
    )

    baseline = simulate_observations(trace, MechanismInput(), config=config)
    perturbed = simulate_observations(
        trace,
        MechanismInput(meth=0.70, nmda_antagonism=0.60),
        config=config,
    )
    assert perturbed.summary.within_state_variance > baseline.summary.within_state_variance
