import numpy as np

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import simulate_pbpk
from research.human_sim.physiology import Physiology, TissueSpec


def _isolated_physiology():
    return Physiology(
        central_volume_l=1.0,
        tissues=(
            TissueSpec("brain", 1.0, 0.0),
            TissueSpec("liver", 1.0, 0.0),
            TissueSpec("kidney", 1.0, 0.0),
            TissueSpec("peripheral", 1.0, 0.0),
        ),
        label="isolated_test",
    )


def _base_disposition(**kwargs):
    values = dict(
        label="mechanism_test",
        tissue_partition_coefficients={
            "brain": 1.0,
            "liver": 1.0,
            "kidney": 1.0,
            "peripheral": 1.0,
        },
        plasma_unbound_fraction=0.5,
        brain_unbound_fraction=0.5,
        blood_to_plasma_ratio=1.0,
    )
    values.update(kwargs)
    return CompoundDisposition(**values)


def test_gfr_filtration_matches_exact_central_exponential():
    physiology = _isolated_physiology()
    disposition = _base_disposition(renal_gfr_l_per_h=1.0)

    trace = simulate_pbpk(
        physiology,
        disposition,
        duration_h=2.0,
        dt_h=0.1,
        initial_central_amount=1.0,
    )

    # CLfiltration = GFR * fu_plasma / B:P = 1 * 0.5 / 1 = 0.5 L/h.
    # Vcentral = 1 L -> k = 0.5 /h.
    expected = np.exp(-0.5 * trace.times_h)
    assert np.allclose(trace.central_amount, expected, atol=1e-12, rtol=1e-12)
    assert np.max(np.abs(trace.mass_balance_error)) < 1e-12
    assert np.isclose(trace.eliminated_amount[-1], 1.0 - expected[-1], atol=1e-12)


def test_blood_to_plasma_ratio_changes_filtration_on_correct_basis():
    physiology = _isolated_physiology()

    fast = simulate_pbpk(
        physiology,
        _base_disposition(
            renal_gfr_l_per_h=1.0,
            blood_to_plasma_ratio=1.0,
        ),
        duration_h=1.0,
        dt_h=0.1,
        initial_central_amount=1.0,
    )
    slow = simulate_pbpk(
        physiology,
        _base_disposition(
            renal_gfr_l_per_h=1.0,
            blood_to_plasma_ratio=2.0,
        ),
        duration_h=1.0,
        dt_h=0.1,
        initial_central_amount=1.0,
    )

    assert slow.central_amount[-1] > fast.central_amount[-1]


def test_intrinsic_liver_metabolism_matches_exact_tissue_exponential():
    physiology = _isolated_physiology()
    disposition = _base_disposition(
        hepatic_intrinsic_unbound_clearance_l_per_h=1.0,
        liver_unbound_fraction=0.5,
    )

    trace = simulate_pbpk(
        physiology,
        disposition,
        duration_h=2.0,
        dt_h=0.1,
        initial_tissue_amounts={"liver": 1.0},
    )

    # elimination = CLint,u * fu_liver * C_liver,total
    # = 1 L/h * 0.5 * A/1 L -> k=0.5/h.
    expected = np.exp(-0.5 * trace.times_h)
    assert np.allclose(
        trace.tissue_amounts["liver"],
        expected,
        atol=1e-12,
        rtol=1e-12,
    )
    assert np.max(np.abs(trace.mass_balance_error)) < 1e-12
    assert np.isclose(trace.eliminated_amount[-1], 1.0 - expected[-1], atol=1e-12)


def test_legacy_and_mechanistic_clearance_fields_are_distinct():
    physiology = _isolated_physiology()
    legacy = _base_disposition(hepatic_clearance_l_per_h=0.5)
    mechanistic = _base_disposition(
        hepatic_intrinsic_unbound_clearance_l_per_h=1.0,
        liver_unbound_fraction=0.5,
    )

    legacy_trace = simulate_pbpk(
        physiology,
        legacy,
        duration_h=1.0,
        dt_h=0.1,
        initial_tissue_amounts={"liver": 1.0},
    )
    mechanism_trace = simulate_pbpk(
        physiology,
        mechanistic,
        duration_h=1.0,
        dt_h=0.1,
        initial_tissue_amounts={"liver": 1.0},
    )

    # Same numerical effective coefficient in this constructed case, but represented
    # by different fields/concentration semantics.
    assert np.allclose(
        legacy_trace.tissue_amounts["liver"],
        mechanism_trace.tissue_amounts["liver"],
        atol=1e-12,
    )
