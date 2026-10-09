import pytest

from research.human_sim.transporter_import import load_transporter_csv


def test_transporter_import_loads_routes_and_provenance(tmp_path):
    path = tmp_path / "transporters.csv"
    path.write_text(
        "name,route,vmax_amount_per_h,km_concentration,source_unbound_fraction,source_id,transporter_family,interaction_group\n"
        "hep,hepatic_uptake,0.1,0.05,,synthetic_fixture,OATP-like,hepatic_OATP1B1\n"
        "bil,biliary_efflux,0.03,0.02,0.2,synthetic_fixture,P-gp-like,hepatic_PGP\n",
        encoding="utf-8",
    )
    processes = load_transporter_csv(path)
    assert len(processes) == 2
    assert processes[0].name == "hep"
    assert processes[0].source_id == "synthetic_fixture"
    assert processes[1].source_unbound_fraction == 0.2
    assert processes[0].interaction_group == "hepatic_OATP1B1"


def test_transporter_import_rejects_missing_tissue_unbound_fraction(tmp_path):
    path = tmp_path / "transporters.csv"
    path.write_text(
        "name,route,vmax_amount_per_h,km_concentration,source_unbound_fraction,source_id,transporter_family\n"
        "bil,biliary_efflux,0.03,0.02,,synthetic_fixture,P-gp-like\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source_unbound_fraction"):
        load_transporter_csv(path)


def test_transporter_import_rejects_duplicate_names(tmp_path):
    path = tmp_path / "transporters.csv"
    path.write_text(
        "name,route,vmax_amount_per_h,km_concentration,source_unbound_fraction,source_id,transporter_family\n"
        "x,hepatic_uptake,0.1,0.05,,synthetic_fixture,OATP-like\n"
        "x,renal_uptake,0.1,0.05,,synthetic_fixture,OCT-like\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_transporter_csv(path)
