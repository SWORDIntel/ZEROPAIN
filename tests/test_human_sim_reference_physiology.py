import numpy as np

from research.human_sim.reference_physiology import (
    adult_male_reference_composite,
    audit_physiology_against_reference,
)
from research.human_sim.physiology import Physiology, TissueSpec


def test_reference_profile_reconciles_regional_flows_to_cardiac_output():
    reference = adult_male_reference_composite()
    physiology = reference.physiology
    assert np.isclose(
        physiology.total_tissue_flow_l_per_h,
        reference.cardiac_output_l_per_h,
        rtol=0,
        atol=1e-10,
    )
    assert physiology.tissue_map["brain"].volume_l > 1.0
    assert physiology.tissue_map["brain"].blood_flow_l_per_h > 40.0
    assert "icrp89" in physiology.source_ids
    assert "atsdr_mann_pbpk" in physiology.source_ids


def test_reference_quantities_preserve_derivation_and_evidence_status():
    reference = adult_male_reference_composite()
    brain = reference.quantities["brain_volume_l"]
    peripheral = reference.quantities["peripheral_volume_l"]
    assert "1.450" in brain.derivation
    assert peripheral.evidence_status == "model_reduction_assumption"
    payload = reference.to_dict()
    assert "sources" in payload
    assert "lassen1985_cbf" in payload["sources"]


def test_reference_audit_passes_reference_itself():
    reference = adult_male_reference_composite()
    report = audit_physiology_against_reference(reference.physiology)
    assert report.passed_broad_screen
    assert np.isclose(report.total_flow_ratio, 1.0)
    assert all(np.isclose(value, 1.0) for value in report.ratios_to_reference.values())


def test_reference_audit_flags_gross_outlier_without_mutating_it():
    reference = adult_male_reference_composite()
    base = reference.physiology
    extreme = Physiology(
        central_volume_l=base.central_volume_l * 3.0,
        tissues=tuple(
            TissueSpec(
                tissue.name,
                tissue.volume_l * (3.0 if tissue.name == "brain" else 1.0),
                tissue.blood_flow_l_per_h,
            )
            for tissue in base.tissues
        ),
        label="extreme",
    )
    report = audit_physiology_against_reference(extreme)
    assert not report.passed_broad_screen
    assert any("central_volume" in flag for flag in report.broad_screen_flags)
    assert any("brain_volume" in flag for flag in report.broad_screen_flags)
    assert extreme.central_volume_l == base.central_volume_l * 3.0
