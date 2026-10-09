import numpy as np
import pytest

from research.human_sim.disposition import (
    CompoundDisposition,
    synthetic_reference_disposition,
)
from research.human_sim.pbpk import _exchange_pair, simulate_pbpk
from research.human_sim.physiology import (
    Physiology,
    TissueSpec,
    synthetic_reference_physiology,
)


def test_pair_exchange_is_positive_and_exactly_conservative():
    central, tissue = _exchange_pair(1.0, 0.0, 2.0, 1.0, 0.5)
    assert central >= 0
    assert tissue >= 0
    assert np.isclose(central + tissue, 1.0, atol=1e-12)


def test_pbpk_conserves_input_plus_elimination():
    physiology = synthetic_reference_physiology()
    disposition = synthetic_reference_disposition()
    trace = simulate_pbpk(
        physiology,
        disposition,
        duration_h=8.0,
        dt_h=0.02,
        initial_central_amount=1.5,
        input_rate=lambda t: 0.04 if t < 2.0 else 0.0,
    )
    assert np.max(np.abs(trace.mass_balance_error)) < 1e-10
    assert np.all(trace.central_amount >= -1e-12)
    assert all(np.all(values >= -1e-12) for values in trace.tissue_amounts.values())
    assert trace.eliminated_amount[-1] > 0
    assert trace.brain_total_concentration.max() > 0
    assert trace.brain_free_concentration.max() > 0


def test_zero_initial_and_zero_input_stays_zero():
    trace = simulate_pbpk(
        synthetic_reference_physiology(),
        synthetic_reference_disposition(),
        duration_h=2.0,
        dt_h=0.1,
    )
    assert np.allclose(trace.central_amount, 0.0)
    assert all(np.allclose(values, 0.0) for values in trace.tissue_amounts.values())
    assert np.allclose(trace.eliminated_amount, 0.0)


def test_invalid_negative_input_is_rejected():
    with pytest.raises(ValueError, match="negative"):
        simulate_pbpk(
            synthetic_reference_physiology(),
            synthetic_reference_disposition(),
            duration_h=1.0,
            dt_h=0.1,
            input_rate=lambda t: -1.0,
        )


def test_brain_is_required():
    physiology = Physiology(
        central_volume_l=5.0,
        tissues=(TissueSpec("liver", 1.0, 10.0),),
    )
    with pytest.raises(ValueError, match="brain"):
        physiology.validate()


def test_same_physiology_can_be_reused_for_different_compound_partitioning():
    physiology = synthetic_reference_physiology()
    base = synthetic_reference_disposition()
    low_brain = CompoundDisposition(
        label="low_brain",
        tissue_partition_coefficients={
            **dict(base.tissue_partition_coefficients),
            "brain": 0.2,
        },
        brain_unbound_fraction=base.brain_unbound_fraction,
    )
    high_brain = CompoundDisposition(
        label="high_brain",
        tissue_partition_coefficients={
            **dict(base.tissue_partition_coefficients),
            "brain": 4.0,
        },
        brain_unbound_fraction=base.brain_unbound_fraction,
    )

    low = simulate_pbpk(
        physiology, low_brain, duration_h=2.0, dt_h=0.02, initial_central_amount=1.0
    )
    high = simulate_pbpk(
        physiology, high_brain, duration_h=2.0, dt_h=0.02, initial_central_amount=1.0
    )
    assert high.brain_total_concentration.max() > low.brain_total_concentration.max()
