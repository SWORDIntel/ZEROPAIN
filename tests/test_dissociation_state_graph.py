from research.dissociation.model import MechanismInput
from research.dissociation.state_graph import (
    StateGraphConfig,
    StateGraphParameters,
    _memory_permeability,
    _switch_probability,
    simulate_state_graph,
)


GRAPH_FAST = StateGraphConfig(n_states=4, steps=240, seed=17, sync_interval=48)
PARAMS = StateGraphParameters()


def test_state_graph_meth_increases_switch_pressure_and_fatigue():
    baseline_p = _switch_probability(0.70, MechanismInput(), PARAMS)
    meth_p = _switch_probability(0.70, MechanismInput(meth=0.75), PARAMS)
    assert meth_p > baseline_p

    baseline = simulate_state_graph(MechanismInput(), config=GRAPH_FAST)
    meth = simulate_state_graph(MechanismInput(meth=0.75), config=GRAPH_FAST)
    assert meth.mean_executive_energy < baseline.mean_executive_energy


def test_state_graph_wake_sync_reduces_memory_divergence():
    intact = simulate_state_graph(MechanismInput(), config=GRAPH_FAST)
    disrupted = simulate_state_graph(
        MechanismInput(wake_anchor_disruption=1.0),
        config=GRAPH_FAST,
    )
    assert intact.synchronization_events_completed > disrupted.synchronization_events_completed
    assert intact.memory_divergence < disrupted.memory_divergence


def test_state_graph_nmda_reduces_memory_permeability():
    meth_only = _memory_permeability(MechanismInput(meth=0.60), PARAMS)
    combined = _memory_permeability(
        MechanismInput(meth=0.60, nmda_antagonism=0.60),
        PARAMS,
    )
    assert combined < meth_only

    p_meth = _switch_probability(0.70, MechanismInput(meth=0.60), PARAMS)
    p_combined = _switch_probability(
        0.70,
        MechanismInput(meth=0.60, nmda_antagonism=0.60),
        PARAMS,
    )
    assert p_combined > p_meth


def test_state_graph_kor_hypothesis_directions_are_explicit():
    meth = MechanismInput(meth=0.70)
    kor_ag = MechanismInput(meth=0.70, kor_agonism=0.60)
    kor_ant = MechanismInput(meth=0.70, kor_antagonism=0.60)

    p_meth = _switch_probability(0.70, meth, PARAMS)
    p_ag = _switch_probability(0.70, kor_ag, PARAMS)
    p_ant = _switch_probability(0.70, kor_ant, PARAMS)

    assert p_ag > p_meth > p_ant
    assert _memory_permeability(kor_ag, PARAMS) < _memory_permeability(meth, PARAMS)
    assert _memory_permeability(kor_ant, PARAMS) > _memory_permeability(meth, PARAMS)
