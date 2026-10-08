import pytest

from research.human_sim.partition_import import load_partition_csv


def test_partition_import_loads_single_basis_and_provenance(tmp_path):
    path = tmp_path / "partition.csv"
    path.write_text(
        "tissue,value,basis,source_id,method\n"
        "brain,4.0,tissue_to_unbound_plasma,synthetic_fixture,test\n"
        "liver,5.0,tissue_to_unbound_plasma,synthetic_fixture,test\n",
        encoding="utf-8",
    )
    table = load_partition_csv(path)
    assert table.basis.value == "tissue_to_unbound_plasma"
    assert table.source_id == "synthetic_fixture"
    assert table.tissue_partition_coefficients["brain"] == 4.0


def test_partition_import_rejects_mixed_basis(tmp_path):
    path = tmp_path / "partition.csv"
    path.write_text(
        "tissue,value,basis,source_id,method\n"
        "brain,4.0,tissue_to_unbound_plasma,x,test\n"
        "liver,5.0,tissue_to_plasma,x,test\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="one partition basis"):
        load_partition_csv(path)


def test_partition_import_rejects_duplicate_tissue(tmp_path):
    path = tmp_path / "partition.csv"
    path.write_text(
        "tissue,value,basis,source_id,method\n"
        "brain,4.0,tissue_to_plasma,x,test\n"
        "brain,5.0,tissue_to_plasma,x,test\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_partition_csv(path)
