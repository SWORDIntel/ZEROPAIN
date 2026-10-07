from research.dissociation.model import MechanismInput
from research.dissociation.state_graph import (
    StateGraphConfig,
    simulate_state_graph,
)


GRAPH_FAST = StateGraphConfig(n_states=4, steps=240, seed=17, sync_interval=48)


def test_state_graph_meth_increases_switching_under_default_model():
    baseline = simulate_state_graph(MechanismInput(), config=GRAPH_FAST)
    meth = simulate_state_graph(MechanismInput(meth=0.75), config=GRAPH_FAST)
    assert meth.switch_rate > baseline.switch_rate
    assert meth.mean_executive_energy < baseline.mean_executive_energy


def test_state_graph_wake_sync_reduces_memory_divergence():
    intact = simulate_state_graph(MechanismInput(), config=GRAPH_FAST)
    disrupted = simulate_state_graph(
        MechanismInput(wake_anchor_disruption=1.0),
        config=GRAPH_FAST,
    )
    assert intact.synchronization_events_completed > disrupted.synchronization_events_completed
    assert intact.memory_divergence < disrupted.memory_divergence


def test_state_graph_nmda_and_meth_worsen_memory_consistency():
    meth = simulate_state_graph(MechanismInput(meth=0.60), config=GRAPH_FAST)
    combined = simulate_state_graph(
        MechanismInput(meth=0.60, nmda_antagonism=0.60),
        config=GRAPH_FAST,
    )
    assert combined.memory_consistency < meth.memory_consistency
    assert combined.switch_rate > meth.switch_rate


def test_state_graph_opioid_hypothesis_directions_are_testable():
    meth = simulate_state_graph(MechanismInput(meth=0.70), config=GRAPH_FAST)
    kor_ag = simulate_state_graph(
        MechanismInput(meth=0.70, kor_agonism=0.60),
        config=GRAPH_FAST,
    )
    kor_ant = simulate_state_graph(
        MechanismInput(meth=0.70, kor_antagonism=0.60),
        config=GRAPH_FAST,
    )
    assert kor_ag.switch_rate > meth.switch_rate
    assert kor_ant.switch_rate < meth.switch_rate
