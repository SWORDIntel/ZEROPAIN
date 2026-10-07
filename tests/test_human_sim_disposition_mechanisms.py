import numpy as np
import pytest

from research.human_sim.disposition_mechanisms import (
    PartitionBasis,
    blood_unbound_fraction,
    brain_total_kp_from_kpuu,
    filtration_only_renal_clearance,
    tissue_partition_to_plasma,
    well_stirred_hepatic_clearance,
)
from research.human_sim.external_disposition import (
    ExternalDispositionInputs,
    build_external_disposition,
)
from research.human_sim.physiology import synthetic_reference_physiology


def test_httk_tissue_to_unbound_plasma_converts_to_total_plasma_basis():
    # Ktissue2pu = Ctissue / Cu,plasma. If fu=0.2, Kp = Ktissue2pu * 0.2.
    assert np.isclose(
        tissue_partition_to_plasma(
            5.0,
            basis=PartitionBasis.TISSUE_TO_UNBOUND_PLASMA,
            fu_plasma=0.2,
        ),
        1.0,
    )


def test_total_plasma_partition_basis_is_unchanged():
    assert np.isclose(
        tissue_partition_to_plasma(
            1.7,
            basis=PartitionBasis.TISSUE_TO_PLASMA,
            fu_plasma=0.2,
        ),
        1.7,
    )


def test_kpuu_conversion_matches_definition():
    # Kpuu = Kp * fu_brain/fu_plasma -> Kp = Kpuu*fu_plasma/fu_brain.
    kp = brain_total_kp_from_kpuu(
        0.5,
        fu_plasma=0.2,
        fu_brain=0.1,
    )
    assert np.isclose(kp, 1.0)


def test_blood_free_fraction_accounts_for_blood_to_plasma_ratio():
    assert np.isclose(
        blood_unbound_fraction(
            fu_plasma=0.2,
            blood_to_plasma_ratio=2.0,
        ),
        0.1,
    )


def test_well_stirred_clearance_never_exceeds_hepatic_flow():
    result = well_stirred_hepatic_clearance(
        hepatic_blood_flow_l_per_h=80.0,
        intrinsic_clearance_l_per_h=1000.0,
        fu_blood=0.5,
    )
    assert 0.0 < result.clearance_l_per_h < 80.0
    assert 0.0 < result.extraction_ratio < 1.0


def test_filtration_only_clearance_is_gfr_times_fu():
    result = filtration_only_renal_clearance(
        gfr_l_per_h=7.5,
        fu_plasma=0.2,
    )
    assert np.isclose(result.clearance_l_per_h, 1.5)
    assert np.isclose(result.extraction_ratio, 0.2)


def test_external_builder_normalizes_partition_basis_and_overrides_brain_from_kpuu():
    physiology = synthetic_reference_physiology()
    inputs = ExternalDispositionInputs(
        label="synthetic_external",
        tissue_partition_coefficients={
            "brain": 4.0,
            "liver": 5.0,
            "kidney": 3.0,
            "peripheral": 2.0,
        },
        partition_basis="tissue_to_unbound_plasma",
        fu_plasma=0.2,
        fu_brain=0.1,
        kp_uu_brain=0.5,
        blood_to_plasma_ratio=1.25,
        intrinsic_hepatic_clearance_l_per_h=20.0,
        gfr_l_per_h=7.5,
        source_id="synthetic_fixture",
        method="synthetic_schmitt_like",
    )
    result = build_external_disposition(physiology, inputs)
    disposition = result.disposition

    # brain override from Kpuu: 0.5 * 0.2 / 0.1 = 1.0
    assert np.isclose(disposition.tissue_partition_coefficients["brain"], 1.0)
    # liver normalized from tissue:unbound plasma: 5 * 0.2 = 1.0
    assert np.isclose(disposition.tissue_partition_coefficients["liver"], 1.0)

    # Reference clearances must NOT leak into legacy tissue-concentration fields.
    assert disposition.hepatic_clearance_l_per_h == 0.0
    assert disposition.renal_clearance_l_per_h == 0.0
    assert result.diagnostics["well_stirred_hepatic_reference"] is not None
    assert result.diagnostics["filtration_only_renal_reference"] is not None


def test_builder_requires_exact_reduced_tissue_set():
    physiology = synthetic_reference_physiology()
    inputs = ExternalDispositionInputs(
        label="bad",
        tissue_partition_coefficients={"brain": 1.0},
        partition_basis="tissue_to_plasma",
        fu_plasma=0.5,
        fu_brain=0.5,
        source_id="synthetic_fixture",
        method="bad",
    )
    with pytest.raises(ValueError, match="partition tissue mismatch"):
        build_external_disposition(physiology, inputs)


def test_invalid_derived_blood_free_fraction_is_rejected():
    with pytest.raises(ValueError, match="exceeds 1"):
        blood_unbound_fraction(
            fu_plasma=0.9,
            blood_to_plasma_ratio=0.5,
        )
