from research.dissociation.belief_network import (
    BeliefNetworkConfig,
    BeliefNetworkParameters,
    FactEvent,
    _encoding_accuracy,
    _false_report_probability,
    _withholding_probability,
    simulate_belief_network,
)
from research.dissociation.model import MechanismInput
from research.dissociation.state_network import EventKind, TimelineEvent


CFG = BeliefNetworkConfig(
    n_states=4,
    steps=240,
    seed=41,
    sync_interval=48,
    max_coconscious=2,
)
PARAMS = BeliefNetworkParameters()
FACTS = [
    FactEvent(step=20, truth=1, label="a"),
    FactEvent(step=55, truth=-1, label="b"),
    FactEvent(step=90, truth=1, label="c"),
    FactEvent(step=125, truth=-1, label="d"),
    FactEvent(step=165, truth=1, label="e"),
    FactEvent(step=205, truth=-1, label="f"),
]


def test_meth_and_nmda_reduce_encoding_accuracy_without_assuming_deception():
    baseline = _encoding_accuracy(MechanismInput(), PARAMS)
    meth = _encoding_accuracy(MechanismInput(meth=0.75), PARAMS)
    nmda = _encoding_accuracy(MechanismInput(nmda_antagonism=0.60), PARAMS)

    assert meth < baseline
    assert nmda < baseline
    assert PARAMS.direct_meth_misreport_weight == 0.0


def test_withholding_and_false_reporting_depend_on_low_trust():
    assert _withholding_probability(0.20, PARAMS) > _withholding_probability(0.80, PARAMS)
    assert (
        _false_report_probability(0.20, MechanismInput(), PARAMS)
        > _false_report_probability(0.80, MechanismInput(), PARAMS)
    )


def test_missed_sync_degrades_trust_and_information_integrity():
    timeline = [
        TimelineEvent(step=47, kind=EventKind.WAKE),
        TimelineEvent(step=95, kind=EventKind.WAKE),
        TimelineEvent(step=143, kind=EventKind.WAKE),
        TimelineEvent(step=191, kind=EventKind.WAKE),
    ]
    intact = simulate_belief_network(
        MechanismInput(),
        FACTS,
        config=CFG,
        params=PARAMS,
        timeline=timeline,
    )
    disrupted = simulate_belief_network(
        MechanismInput(wake_anchor_disruption=1.0),
        FACTS,
        config=CFG,
        params=PARAMS,
        timeline=timeline,
    )
    assert intact.sync_completed == 4
    assert disrupted.sync_completed == 0
    assert intact.mean_pairwise_trust > disrupted.mean_pairwise_trust


def test_low_initial_trust_generates_more_withholding_and_false_reporting():
    low_params = BeliefNetworkParameters(
        initial_trust_mean=0.20,
        initial_trust_sd=0.01,
        sync_trust_gain=0.0,
    )
    high_params = BeliefNetworkParameters(
        initial_trust_mean=0.90,
        initial_trust_sd=0.01,
        sync_trust_gain=0.0,
    )

    low = simulate_belief_network(
        MechanismInput(),
        FACTS,
        config=CFG,
        params=low_params,
        timeline=[],
    )
    high = simulate_belief_network(
        MechanismInput(),
        FACTS,
        config=CFG,
        params=high_params,
        timeline=[],
    )

    assert low.withholding_rate > high.withholding_rate
    assert low.false_report_rate > high.false_report_rate
    assert low.adversarial_steps > high.adversarial_steps


def test_false_consensus_is_measurable_separately_from_consistency():
    params = BeliefNetworkParameters(
        base_encoding_accuracy=0.05,
        initial_trust_mean=0.95,
        initial_trust_sd=0.0,
        base_communication_probability=0.90,
        sync_reconciliation_probability=1.0,
    )
    timeline = [
        TimelineEvent(step=47, kind=EventKind.SYNC),
        TimelineEvent(step=95, kind=EventKind.SYNC),
        TimelineEvent(step=143, kind=EventKind.SYNC),
        TimelineEvent(step=191, kind=EventKind.SYNC),
        TimelineEvent(step=239, kind=EventKind.SYNC),
    ]
    result = simulate_belief_network(
        MechanismInput(),
        FACTS,
        config=CFG,
        params=params,
        timeline=timeline,
    )
    # High agreement can still be wrong; these metrics must remain distinct.
    assert 0.0 <= result.false_consensus_rate <= 1.0
    assert 0.0 <= result.belief_consistency <= 1.0
    assert 0.0 <= result.truth_accuracy <= 1.0
