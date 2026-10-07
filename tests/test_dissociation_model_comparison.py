import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.model_comparison import compare_observation_models
from research.dissociation.observation_model import ObservationConfig, simulate_observations
from research.dissociation.state_network import StateNetworkTrace


def _structured_trace(repeats: int = 30) -> StateNetworkTrace:
    executive = []
    coconscious = []
    pattern = [
        (0, (0,)),
        (0, (0, 1)),
        (1, (1,)),
        (1, (1, 2)),
        (2, (2,)),
        (2, (2, 3)),
        (3, (3,)),
        (3, (3, 0)),
    ]
    for _ in range(repeats):
        for state, active in pattern:
            executive.append(state)
            coconscious.append(active)
    n = len(executive)
    return StateNetworkTrace(
        executive=executive,
        coconscious=coconscious,
        mean_trust=[0.8] * n,
        memory_consistency=[0.9] * n,
        withholding_events=[0] * n,
    )


def test_mixture_model_beats_executive_only_when_blends_exist():
    trace = _structured_trace(24)
    config = ObservationConfig(
        n_states=4,
        seed=9,
        state_separation=1.3,
        base_noise_sd=0.04,
        switch_transient_amplitude=0.0,
        perturbation_shift_scale=0.0,
    )
    observations = simulate_observations(trace, MechanismInput(), config=config)
    fits = compare_observation_models(
        trace,
        observations.features,
        n_states=4,
        executive_weight=config.executive_weight,
        transient_lags=2,
        test_every=5,
    )
    by_name = {fit.name: fit for fit in fits}

    assert by_name["mixture"].test_rmse < by_name["executive_state"].test_rmse
    assert by_name["executive_state"].test_rmse < by_name["null"].test_rmse


def test_transient_model_beats_plain_mixture_when_switch_transients_exist():
    trace = _structured_trace(30)
    config = ObservationConfig(
        n_states=4,
        seed=11,
        state_separation=1.1,
        base_noise_sd=0.03,
        switch_transient_amplitude=0.90,
        switch_transient_decay=0.0,
        perturbation_shift_scale=0.0,
    )
    observations = simulate_observations(trace, MechanismInput(), config=config)
    fits = compare_observation_models(
        trace,
        observations.features,
        n_states=4,
        executive_weight=config.executive_weight,
        transient_lags=1,
        test_every=5,
    )
    by_name = {fit.name: fit for fit in fits}

    assert (
        by_name["mixture_plus_state_derivative"].test_rmse
        < by_name["mixture"].test_rmse
    )
    assert (
        by_name["mixture_plus_state_derivative"].parameters
        < by_name["mixture_plus_pair_transient"].parameters
    )
