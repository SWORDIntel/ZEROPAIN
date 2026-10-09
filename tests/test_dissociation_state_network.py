import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.state_network import (
    EventKind,
    StateNetworkConfig,
    StateNetworkParameters,
    TimelineEvent,
    _memory_modifier,
    _switch_probability,
    simulate_state_network,
)


CFG = StateNetworkConfig(
    n_states=4,
    steps=240,
    seed=31,
    max_coconscious=3,
    sync_interval=48,
)
PARAMS = StateNetworkParameters()


def test_meth_and_nmda_have_separable_default_pressures():
    base_switch = _switch_probability(0.70, 0.0, MechanismInput(), PARAMS)
    meth_switch = _switch_probability(
        0.70, 0.0, MechanismInput(meth=0.70), PARAMS
    )
    nmda_switch = _switch_probability(
        0.70, 0.0, MechanismInput(nmda_antagonism=0.60), PARAMS
    )
    assert meth_switch > base_switch
    assert nmda_switch > base_switch

    base_memory = _memory_modifier(MechanismInput(), PARAMS)
    nmda_memory = _memory_modifier(
        MechanismInput(nmda_antagonism=0.60), PARAMS
    )
    assert nmda_memory < base_memory


def test_coconscious_occupancy_is_representable():
    summary = simulate_state_network(MechanismInput(), config=CFG, params=PARAMS)
    assert summary.mean_coconscious_states >= 1.0
    assert summary.blended_steps > 0


def test_intact_sync_preserves_more_trust_than_failed_sync():
    timeline = [
        TimelineEvent(step=47, kind=EventKind.WAKE, label="wake_1"),
        TimelineEvent(step=95, kind=EventKind.WAKE, label="wake_2"),
        TimelineEvent(step=143, kind=EventKind.WAKE, label="wake_3"),
        TimelineEvent(step=191, kind=EventKind.WAKE, label="wake_4"),
    ]
    intact = simulate_state_network(
        MechanismInput(),
        config=CFG,
        params=PARAMS,
        timeline=timeline,
    )
    disrupted = simulate_state_network(
        MechanismInput(wake_anchor_disruption=1.0),
        config=CFG,
        params=PARAMS,
        timeline=timeline,
    )
    assert intact.sync_completed == 4
    assert disrupted.sync_completed == 0
    assert intact.mean_pairwise_trust > disrupted.mean_pairwise_trust
    assert intact.memory_consistency > disrupted.memory_consistency


def test_meth_nmda_can_drive_more_divergence_than_meth_alone():
    meth = simulate_state_network(
        MechanismInput(meth=0.65),
        config=CFG,
        params=PARAMS,
    )
    combined = simulate_state_network(
        MechanismInput(meth=0.65, nmda_antagonism=0.60),
        config=CFG,
        params=PARAMS,
    )
    assert combined.memory_consistency < meth.memory_consistency


def test_low_trust_can_generate_withholding_without_hardcoding_state_identity():
    low_trust_params = StateNetworkParameters(
        initial_trust_mean=0.25,
        initial_trust_sd=0.01,
        sync_trust_gain=0.0,
    )
    high_trust_params = StateNetworkParameters(
        initial_trust_mean=0.90,
        initial_trust_sd=0.01,
        sync_trust_gain=0.0,
    )
    low = simulate_state_network(
        MechanismInput(),
        config=CFG,
        params=low_trust_params,
        timeline=[],
    )
    high = simulate_state_network(
        MechanismInput(),
        config=CFG,
        params=high_trust_params,
        timeline=[],
    )
    assert low.withholding_rate > high.withholding_rate


def test_trace_captures_explicit_event_timeline():
    timeline = [
        TimelineEvent(step=20, kind=EventKind.STRESS, intensity=0.8, label="stress"),
        TimelineEvent(step=47, kind=EventKind.SYNC, label="meeting"),
    ]
    summary, trace = simulate_state_network(
        MechanismInput(meth=0.25),
        config=CFG,
        params=PARAMS,
        timeline=timeline,
        return_trace=True,
    )
    assert len(trace.executive) == CFG.steps
    assert len(trace.mean_trust) == CFG.steps
    assert len(trace.memory_consistency) == CFG.steps
    assert summary.sync_expected == 1
