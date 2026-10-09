import numpy as np
import pytest

from research.human_sim.adaptation import (
    AdaptationParameters,
    AdaptationState,
    step_adaptation,
)
from research.human_sim.receptors import (
    ReceptorTarget,
    hill_occupancy,
    receptor_state,
)


def test_hill_occupancy_is_half_at_kd_for_hill_one():
    assert np.isclose(hill_occupancy(2.0, 2.0, 1.0), 0.5)


def test_higher_affinity_gives_higher_occupancy_at_same_concentration():
    concentration = 0.5
    high_affinity = hill_occupancy(concentration, 0.1)
    low_affinity = hill_occupancy(concentration, 1.0)
    assert high_affinity > low_affinity


def test_effect_gain_is_separate_from_occupancy():
    target_full = ReceptorTarget("full", 0.2, effect_gain=1.0)
    target_partial = ReceptorTarget("partial", 0.2, effect_gain=0.4)
    full = receptor_state(1.0, target_full)
    partial = receptor_state(1.0, target_partial)
    assert np.isclose(full.occupancy, partial.occupancy)
    assert partial.effective_signal_magnitude < full.effective_signal_magnitude


def test_signed_effect_can_represent_opposite_target_direction():
    inhibitory = ReceptorTarget("inhibitory", 0.2, effect_gain=0.8, effect_polarity=-1)
    state = receptor_state(1.0, inhibitory)
    assert state.signed_effect < 0
    assert state.effective_signal_magnitude > 0


def test_sustained_signal_reduces_surface_and_coupling_then_zero_signal_recovers():
    params = AdaptationParameters(
        internalization_rate_per_h=0.25,
        recycling_rate_per_h=0.12,
        desensitization_rate_per_h=0.20,
        resensitization_rate_per_h=0.10,
    )
    state = AdaptationState()
    for _ in range(20):
        state = step_adaptation(state, 0.8, dt_h=0.1, params=params)

    depressed = state
    assert depressed.surface_fraction < 1.0
    assert depressed.coupling_fraction < 1.0

    for _ in range(80):
        state = step_adaptation(state, 0.0, dt_h=0.1, params=params)

    assert state.surface_fraction > depressed.surface_fraction
    assert state.coupling_fraction > depressed.coupling_fraction


def test_invalid_receptor_parameters_fail():
    with pytest.raises(ValueError):
        ReceptorTarget("bad", 0.0).validate()
