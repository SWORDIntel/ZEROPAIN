import numpy as np

from research.human_sim.disposition import synthetic_reference_disposition
from research.human_sim.pbpk import simulate_pbpk
from research.human_sim.pbpk_reference import (
    compare_to_reference,
    simulate_pbpk_reference,
)
from research.human_sim.physiology import synthetic_reference_physiology


def test_reference_solver_conserves_mass():
    reference = simulate_pbpk_reference(
        synthetic_reference_physiology(),
        synthetic_reference_disposition(),
        duration_h=2.0,
        output_dt_h=0.02,
        substeps=30,
        initial_central_amount=1.0,
    )
    assert np.max(np.abs(reference.mass_balance_error)) < 1e-8
    assert np.all(reference.central_amount >= -1e-10)
    assert all(
        np.all(values >= -1e-10)
        for values in reference.tissue_amounts.values()
    )


def test_primary_solver_agrees_with_independent_rk4_reference_at_fine_step():
    physiology = synthetic_reference_physiology()
    disposition = synthetic_reference_disposition()

    primary = simulate_pbpk(
        physiology,
        disposition,
        duration_h=2.0,
        dt_h=0.01,
        initial_central_amount=1.0,
    )
    reference = simulate_pbpk_reference(
        physiology,
        disposition,
        duration_h=2.0,
        output_dt_h=0.01,
        substeps=20,
        initial_central_amount=1.0,
    )

    comparison = compare_to_reference(primary, reference)

    # This is an implementation-agreement gate, not a biological validation gate.
    # At a fine timestep, the sequential exact-exchange production solver should
    # remain within a few percent of the independently integrated coupled ODEs.
    assert comparison.max_metric < 0.05, comparison.to_dict()


def test_reference_comparison_detects_deliberately_wrong_trace():
    physiology = synthetic_reference_physiology()
    disposition = synthetic_reference_disposition()
    reference = simulate_pbpk_reference(
        physiology,
        disposition,
        duration_h=1.0,
        output_dt_h=0.02,
        substeps=20,
        initial_central_amount=1.0,
    )
    primary = simulate_pbpk(
        physiology,
        disposition,
        duration_h=1.0,
        dt_h=0.02,
        initial_central_amount=1.0,
    )

    baseline = compare_to_reference(primary, reference)
    tampered = type(primary)(
        times_h=primary.times_h,
        central_amount=primary.central_amount,
        tissue_amounts=primary.tissue_amounts,
        eliminated_amount=primary.eliminated_amount,
        cumulative_input=primary.cumulative_input,
        mass_balance_error=primary.mass_balance_error,
        central_concentration=primary.central_concentration * 1.5,
        brain_total_concentration=primary.brain_total_concentration * 0.5,
        brain_free_concentration=primary.brain_free_concentration * 0.5,
    )
    bad = compare_to_reference(tampered, reference)
    assert bad.max_metric > baseline.max_metric



def test_primary_and_reference_agree_with_intrinsic_liver_and_gfr_elimination():
    from research.human_sim.disposition import CompoundDisposition

    physiology = synthetic_reference_physiology()
    base = synthetic_reference_disposition()
    disposition = CompoundDisposition(
        label="mechanistic_clearance_reference_test",
        tissue_partition_coefficients=dict(base.tissue_partition_coefficients),
        plasma_unbound_fraction=0.25,
        brain_unbound_fraction=base.brain_unbound_fraction,
        blood_to_plasma_ratio=1.2,
        hepatic_intrinsic_unbound_clearance_l_per_h=12.0,
        liver_unbound_fraction=0.08,
        renal_gfr_l_per_h=7.0,
    )

    primary = simulate_pbpk(
        physiology,
        disposition,
        duration_h=2.0,
        dt_h=0.01,
        initial_central_amount=1.0,
    )
    reference = simulate_pbpk_reference(
        physiology,
        disposition,
        duration_h=2.0,
        output_dt_h=0.01,
        substeps=25,
        initial_central_amount=1.0,
    )
    comparison = compare_to_reference(primary, reference)
    assert comparison.max_metric < 0.05, comparison.to_dict()
    assert primary.eliminated_amount[-1] > 0
    assert reference.eliminated_amount[-1] > 0
