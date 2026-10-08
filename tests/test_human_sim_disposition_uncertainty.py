import numpy as np
import pytest

from research.human_sim.disposition_uncertainty import (
    DispositionUncertainty,
    sample_external_dispositions,
    summarize_disposition_samples,
)
from research.human_sim.external_disposition import ExternalDispositionInputs
from research.human_sim.physiology import synthetic_reference_physiology


def _base_inputs():
    return ExternalDispositionInputs(
        label="uncertainty_fixture",
        tissue_partition_coefficients={
            "brain": 4.0,
            "liver": 5.0,
            "kidney": 3.0,
            "peripheral": 2.0,
        },
        partition_basis="tissue_to_unbound_plasma",
        fu_plasma=0.2,
        fu_brain=0.1,
        blood_to_plasma_ratio=1.2,
        kp_uu_brain=0.5,
        intrinsic_hepatic_clearance_l_per_h=20.0,
        gfr_l_per_h=7.5,
        source_id="synthetic_fixture",
        method="synthetic",
    )


def test_zero_cv_reproduces_identical_dispositions():
    physiology = synthetic_reference_physiology()
    results = sample_external_dispositions(
        physiology,
        _base_inputs(),
        DispositionUncertainty(),
        samples=5,
        seed=3,
    )
    brain = [
        result.disposition.tissue_partition_coefficients["brain"]
        for result in results
    ]
    assert np.allclose(brain, brain[0])

    summary = summarize_disposition_samples(results)
    assert summary["partition_coefficients"]["brain"]["sd"] == 0.0


def test_nonzero_uncertainty_produces_variability_but_keeps_bounds():
    physiology = synthetic_reference_physiology()
    uncertainty = DispositionUncertainty(
        partition_cv_by_tissue={
            "brain": 0.20,
            "liver": 0.15,
            "kidney": 0.10,
            "peripheral": 0.20,
        },
        fu_plasma_cv=0.15,
        fu_brain_cv=0.10,
        blood_to_plasma_cv=0.10,
        kp_uu_brain_cv=0.20,
        intrinsic_hepatic_clearance_cv=0.25,
        gfr_cv=0.10,
    )
    results = sample_external_dispositions(
        physiology,
        _base_inputs(),
        uncertainty,
        samples=200,
        seed=11,
    )
    assert len(results) == 200

    fu_values = [result.diagnostics["fu_plasma"] for result in results]
    assert np.std(fu_values) > 0
    assert all(0.0 < value <= 1.0 for value in fu_values)

    for result in results:
        for value in result.disposition.tissue_partition_coefficients.values():
            assert value > 0

    summary = summarize_disposition_samples(results)
    assert summary["partition_coefficients"]["brain"]["sd"] > 0
    assert "well_stirred_hepatic_clearance_l_per_h" in summary
    assert "filtration_only_renal_clearance_l_per_h" in summary


def test_fraction_cv_that_implies_impossible_beta_variance_is_rejected():
    physiology = synthetic_reference_physiology()
    with pytest.raises(ValueError, match="beta variance"):
        sample_external_dispositions(
            physiology,
            _base_inputs(),
            DispositionUncertainty(fu_plasma_cv=3.0),
            samples=10,
            seed=1,
        )


def test_uncertainty_for_unknown_tissue_is_rejected():
    physiology = synthetic_reference_physiology()
    with pytest.raises(ValueError, match="unknown tissues"):
        sample_external_dispositions(
            physiology,
            _base_inputs(),
            DispositionUncertainty(
                partition_cv_by_tissue={"spleen": 0.1}
            ),
            samples=10,
        )
