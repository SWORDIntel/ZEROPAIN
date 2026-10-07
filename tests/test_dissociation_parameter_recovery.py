from dataclasses import replace

from research.dissociation.model import ModelParameters, PopulationConfig
from research.dissociation.parameter_recovery import (
    RecoveryConfig,
    recover_parameters,
)


def test_parameter_recovery_recovers_two_separable_mechanisms():
    truth = replace(
        ModelParameters(),
        meth_salience_weight=1.30,
        nmda_integration_weight=0.95,
    )
    bounds = {
        "meth_salience_weight": (0.60, 1.60),
        "nmda_integration_weight": (0.55, 1.35),
    }
    estimate, recovered, diagnostics = recover_parameters(
        truth,
        bounds,
        population=PopulationConfig(n_subjects=220, steps=35, seed=5),
        recovery=RecoveryConfig(grid_points=7, passes=4, shrink=0.45),
    )
    by_name = {item.name: item for item in recovered}

    assert by_name["meth_salience_weight"].relative_error < 0.12
    assert by_name["nmda_integration_weight"].relative_error < 0.12
    assert diagnostics["holdout_objective"] < 0.20
