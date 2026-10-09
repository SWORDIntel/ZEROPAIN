import pytest

from research.human_sim.disposition import (
    CompoundDisposition,
    synthetic_reference_disposition,
)
from research.human_sim.physiology import synthetic_reference_physiology


def test_synthetic_disposition_matches_fixture_tissue_schema():
    physiology = synthetic_reference_physiology()
    disposition = synthetic_reference_disposition()
    disposition.validate(set(physiology.tissue_map))


def test_disposition_rejects_missing_tissue_partitioning():
    disposition = CompoundDisposition(
        label="incomplete",
        tissue_partition_coefficients={"brain": 1.0},
    )
    with pytest.raises(ValueError, match="missing"):
        disposition.validate({"brain", "liver"})


def test_clearance_and_unbound_fractions_are_compound_specific():
    physiology = synthetic_reference_physiology()
    assert not hasattr(physiology, "hepatic_clearance_l_per_h")
    assert not hasattr(physiology, "brain_unbound_fraction")
    disposition = synthetic_reference_disposition()
    assert disposition.hepatic_clearance_l_per_h > 0
    assert 0 < disposition.brain_unbound_fraction <= 1
