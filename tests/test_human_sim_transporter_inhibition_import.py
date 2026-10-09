import pytest

from research.human_sim.transporter_inhibition_import import (
    load_transporter_inhibition_csv,
)


def test_inhibition_import_groups_entries_by_ligand(tmp_path):
    path = tmp_path / "inhibition.csv"
    path.write_text(
        "inhibitor_name,interaction_group,ki_concentration,source_compartment,"
        "source_unbound_fraction,source_id,mode\n"
        "x,hepatic_OATP1B1,0.05,central,,synthetic_fixture,competitive\n"
        "x,renal_OCT2,0.10,kidney,0.2,synthetic_fixture,competitive\n",
        encoding="utf-8",
    )
    result = load_transporter_inhibition_csv(path)
    assert set(result) == {"x"}
    assert len(result["x"]) == 2
    assert result["x"][0].interaction_group == "hepatic_OATP1B1"
    assert result["x"][1].source_unbound_fraction == 0.2


def test_inhibition_import_rejects_duplicate_ligand_group(tmp_path):
    path = tmp_path / "inhibition.csv"
    path.write_text(
        "inhibitor_name,interaction_group,ki_concentration,source_compartment,"
        "source_unbound_fraction,source_id,mode\n"
        "x,g,0.05,central,,synthetic_fixture,competitive\n"
        "x,g,0.10,central,,synthetic_fixture,competitive\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_transporter_inhibition_csv(path)


def test_inhibition_import_rejects_tissue_source_without_unbound_fraction(tmp_path):
    path = tmp_path / "inhibition.csv"
    path.write_text(
        "inhibitor_name,interaction_group,ki_concentration,source_compartment,"
        "source_unbound_fraction,source_id,mode\n"
        "x,g,0.05,liver,,synthetic_fixture,competitive\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source_unbound_fraction"):
        load_transporter_inhibition_csv(path)
