from dataclasses import replace

import pytest

from research.dissociation.factorial import estimate_effects, generate_design
from research.dissociation.model import (
    MechanismInput,
    ModelParameters,
    PopulationConfig,
    compare_conditions,
    simulate,
)


FAST = PopulationConfig(n_subjects=600, steps=80, seed=42)


def test_inputs_are_dimensionless_and_bounded():
    with pytest.raises(ValueError):
        simulate(MechanismInput(meth=1.1), config=FAST)


def test_meth_default_model_increases_switching():
    results = compare_conditions(
        {
            "baseline": MechanismInput(),
            "meth": MechanismInput(meth=0.75),
        },
        config=FAST,
    )
    assert (
        results["meth"].mean_switch_probability
        > results["baseline"].mean_switch_probability
    )
    assert results["meth"].executive_stability < results["baseline"].executive_stability


def test_nmda_antagonism_reduces_integration():
    baseline = simulate(MechanismInput(), config=FAST)
    nmda = simulate(MechanismInput(nmda_antagonism=0.60), config=FAST)
    assert nmda.cortical_integration < baseline.cortical_integration
    assert nmda.mean_switch_probability > baseline.mean_switch_probability


def test_wake_anchor_is_separable_from_meth():
    baseline = simulate(MechanismInput(), config=FAST)
    wake = simulate(MechanismInput(wake_anchor_disruption=0.75), config=FAST)
    meth = simulate(MechanismInput(meth=0.75), config=FAST)

    assert wake.internal_coordination < baseline.internal_coordination
    assert meth.salience_load > wake.salience_load


def test_default_kor_directions_are_opposed():
    meth = simulate(MechanismInput(meth=0.75), config=FAST)
    agonist = simulate(MechanismInput(meth=0.75, kor_agonism=0.60), config=FAST)
    antagonist = simulate(
        MechanismInput(meth=0.75, kor_antagonism=0.60),
        config=FAST,
    )

    assert agonist.mean_switch_probability > meth.mean_switch_probability
    assert antagonist.mean_switch_probability < meth.mean_switch_probability


def test_default_mor_partial_hypothesis_is_stabilizing_but_not_hardcoded():
    meth_input = MechanismInput(meth=0.75)
    mor_input = MechanismInput(meth=0.75, mor_partial_agonism=0.60)

    default_meth = simulate(meth_input, config=FAST)
    default_mor = simulate(mor_input, config=FAST)
    assert default_mor.mean_switch_probability < default_meth.mean_switch_probability

    reversed_params = replace(
        ModelParameters(),
        mor_partial_control_weight=-0.50,
        mor_partial_integration_weight=-0.20,
    )
    reversed_meth = simulate(meth_input, config=FAST, params=reversed_params)
    reversed_mor = simulate(mor_input, config=FAST, params=reversed_params)
    assert reversed_mor.mean_switch_probability > reversed_meth.mean_switch_probability


def test_nop_direction_is_not_forced():
    nop = MechanismInput(meth=0.75, nop_agonism=0.60)
    meth = MechanismInput(meth=0.75)

    positive = ModelParameters(nop_agonist_control_weight=0.30)
    negative = ModelParameters(nop_agonist_control_weight=-0.30)

    assert (
        simulate(nop, config=FAST, params=positive).mean_switch_probability
        < simulate(meth, config=FAST, params=positive).mean_switch_probability
    )
    assert (
        simulate(nop, config=FAST, params=negative).mean_switch_probability
        > simulate(meth, config=FAST, params=negative).mean_switch_probability
    )


def test_factorial_design_size_and_interaction_math():
    design = generate_design(("meth", "nmda_antagonism"), high=0.5)
    assert len(design) == 4

    records = []
    for indicators, _ in design:
        m = indicators["meth"]
        n = indicators["nmda_antagonism"]
        y = 1.0 * m + 2.0 * n + 3.0 * m * n
        metrics = {
            "mean_switch_probability": y,
            "mean_persistence_steps": y,
            "executive_stability": y,
            "cortical_integration": y,
            "internal_coordination": y,
            "information_consistency": y,
            "salience_load": y,
        }
        records.append({"indicators": indicators, "metrics": metrics})

    effects = estimate_effects(records, ("meth", "nmda_antagonism"))
    assert effects["pairwise_interactions"]["meth x nmda_antagonism"][
        "mean_switch_probability"
    ] == 3.0
