import csv

import numpy as np

from research.human_sim.population import (
    detect_population_format,
    load_httkpop_csv,
    load_pksim_csv,
    summarize_population,
)


FIELDS = [
    "seqn", "gender", "age_years", "weight", "weight_adj", "Blood_mass",
    "Brain_mass", "Brain_flow", "Liver_mass", "Liver_flow",
    "Kidneys_mass", "Kidneys_flow", "CO", "hematocrit",
]


def _write_population(path):
    rows = [
        {
            "seqn": "101", "gender": "Female", "age_years": 31, "weight": 62,
            "weight_adj": 61.5, "Blood_mass": 4.7,
            "Brain_mass": 1.35, "Brain_flow": 42,
            "Liver_mass": 1.45, "Liver_flow": 78,
            "Kidneys_mass": 0.30, "Kidneys_flow": 65,
            "CO": 290, "hematocrit": 41,
        },
        {
            "seqn": "102", "gender": "Male", "age_years": 48, "weight": 84,
            "weight_adj": 83.2, "Blood_mass": 5.8,
            "Brain_mass": 1.48, "Brain_flow": 47,
            "Liver_mass": 1.80, "Liver_flow": 92,
            "Kidneys_mass": 0.34, "Kidneys_flow": 72,
            "CO": 335, "hematocrit": 45,
        },
        {
            "seqn": "103", "gender": "Female", "age_years": 66, "weight": 72,
            "weight_adj": 71.1, "Blood_mass": 5.0,
            "Brain_mass": 1.29, "Brain_flow": 38,
            "Liver_mass": 1.55, "Liver_flow": 73,
            "Kidneys_mass": 0.28, "Kidneys_flow": 58,
            "CO": 270, "hematocrit": 39,
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_httkpop_import_preserves_individual_correlations(tmp_path):
    path = tmp_path / "httkpop.csv"
    _write_population(path)
    people = load_httkpop_csv(path)

    assert len(people) == 3
    assert people[0].individual_id == "101"
    assert people[0].metadata["gender"] == "Female"
    assert people[1].physiology.central_volume_l > people[0].physiology.central_volume_l
    assert people[1].physiology.tissue_map["brain"].blood_flow_l_per_h > people[0].physiology.tissue_map["brain"].blood_flow_l_per_h

    for person in people:
        flows = sum(t.blood_flow_l_per_h for t in person.physiology.tissues)
        # Reduced model explicitly assigns residual CO to peripheral.
        assert np.isclose(flows, float([
            row for row in csv.DictReader(path.open()) if row["seqn"] == person.individual_id
        ][0]["CO"]))


def test_population_summary_reports_empirical_variability(tmp_path):
    path = tmp_path / "httkpop.csv"
    _write_population(path)
    summary = summarize_population(load_httkpop_csv(path))

    assert summary.count == 3
    assert summary.central_volume_sd_l > 0
    assert summary.tissue_volume_sd_l["brain"] > 0
    assert summary.tissue_flow_sd_l_per_h["liver"] > 0


def test_import_rejects_missing_required_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("seqn,weight\n1,70\n", encoding="utf-8")
    try:
        load_httkpop_csv(path)
    except ValueError as exc:
        assert "Blood_mass" in str(exc)
    else:
        raise AssertionError("expected missing-column failure")



def test_pksim_population_import_uses_direct_organ_volumes(tmp_path):
    path = tmp_path / "pksim.csv"
    path.write_text(
        "#PK-Sim version: synthetic-test\n"
        '"IndividualId","Gender","Population",'
        '"Organism|VenousBlood|Volume [l]","Organism|ArterialBlood|Volume [l]",'
        '"Organism|Brain|Volume [l]","Organism|Brain|Specific blood flow rate [l/min/kg organ]",'
        '"Organism|Liver|Volume [l]","Organism|Liver|Specific blood flow rate [l/min/kg organ]",'
        '"Organism|Kidney|Volume [l]","Organism|Kidney|Specific blood flow rate [l/min/kg organ]",'
        '"Organism|Muscle|Volume [l]","Organism|Muscle|Specific blood flow rate [l/min/kg organ]",'
        '"Organism|Fat|Volume [l]","Organism|Fat|Specific blood flow rate [l/min/kg organ]"\n'
        '7,"FEMALE","European_ICRP_2002",3.2,1.4,1.35,0.45,1.55,0.75,0.31,2.6,24.0,0.02,18.0,0.018\n',
        encoding="utf-8",
    )
    assert detect_population_format(path) == "pksim"
    people = load_pksim_csv(path)
    assert len(people) == 1
    person = people[0]
    assert np.isclose(person.physiology.central_volume_l, 4.6)
    assert np.isclose(person.physiology.tissue_map["brain"].volume_l, 1.35)
    assert person.physiology.tissue_map["brain"].blood_flow_l_per_h > 0
    assert np.isclose(person.physiology.tissue_map["peripheral"].volume_l, 42.0)
    assert person.source_id == "pksim_population"


def test_format_detection_distinguishes_httk_and_pksim(tmp_path):
    httk = tmp_path / "httk.csv"
    _write_population(httk)
    assert detect_population_format(httk) == "httk"
