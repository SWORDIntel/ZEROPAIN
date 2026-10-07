"""Tests for observational CSV bridge."""

import csv

import numpy as np
import pytest

from research.dissociation.observational_csv import (
    load_observational_csv,
    score_observational_rows,
)


def _write_csv(path, *, include_mechanisms=False, sessions=8):
    fields = [
        "subject_id", "session_index",
        "observer_switch_count", "switch_observation_checks",
        "recall_successes", "recall_trials",
        "plan_agreement_successes", "plan_trials",
        "stress_load", "sleep_wake_irregularity", "social_conflict_load",
    ]
    if include_mechanisms:
        fields += [
            "meth", "nmda_antagonism", "mor_partial_agonism",
            "kor_antagonism", "wake_anchor_disruption",
        ]

    rows = []
    for subject in ("A", "B"):
        for session in range(sessions):
            row = {
                "subject_id": subject,
                "session_index": session,
                "observer_switch_count": 2 + (session % 3),
                "switch_observation_checks": 20,
                "recall_successes": 8 - (session % 2),
                "recall_trials": 10,
                "plan_agreement_successes": 7 - (session % 3),
                "plan_trials": 10,
                "stress_load": 0.15 + 0.07 * session,
                "sleep_wake_irregularity": 0.10 + 0.05 * (session % 4),
                "social_conflict_load": 0.08 + 0.04 * (session % 3),
            }
            if include_mechanisms:
                row.update({
                    "meth": 0.5 if session % 4 == 0 else 0.0,
                    "nmda_antagonism": 0.5 if session % 4 == 1 else 0.0,
                    "mor_partial_agonism": 0.5 if session % 4 == 2 else 0.0,
                    "kor_antagonism": 0.5 if session % 4 == 3 else 0.0,
                    "wake_anchor_disruption": 0.3 if session % 2 else 0.0,
                })
            rows.append(row)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_csv_loader_derives_rates_lags_and_time_trend_without_mechanism_fields(tmp_path):
    path = tmp_path / "observations.csv"
    _write_csv(path, include_mechanisms=False)

    rows, report = load_observational_csv(path)
    assert report.rows == 16
    assert report.subjects == 2
    assert report.available_mechanism_features == ()
    assert "observer_switch_rate" in report.available_outcomes
    assert np.isclose(rows[0]["observer_switch_rate"], 0.10)
    assert np.isnan(rows[0]["lag_observer_switch_rate"])
    assert np.isfinite(rows[1]["lag_observer_switch_rate"])
    assert 0.0 <= rows[-1]["time_trend"] <= 1.0
    assert any("mechanism" in warning.lower() for warning in report.warnings)


def test_models_skip_mechanism_family_when_annotations_absent(tmp_path):
    path = tmp_path / "context.csv"
    _write_csv(path, include_mechanisms=False)
    rows, _ = load_observational_csv(path)
    scores = score_observational_rows(rows, test_fraction=0.25)
    names = {score.model for score in scores}
    assert "mean_only" in names
    assert "context_available" in names
    assert not any("mechanism" in name for name in names)


def test_mechanism_models_become_available_only_when_columns_exist(tmp_path):
    path = tmp_path / "annotated.csv"
    _write_csv(path, include_mechanisms=True, sessions=16)
    rows, report = load_observational_csv(path)
    assert len(report.available_mechanism_features) == 5
    scores = score_observational_rows(rows, test_fraction=0.25)
    names = {score.model for score in scores}
    assert "mechanism_available" in names
    assert "full_available" in names


def test_duplicate_subject_session_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    _write_csv(path, include_mechanisms=False)
    text = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(text + [text[1]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_observational_csv(path)


def test_missing_required_identifiers_are_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("session_index,observer_switch_rate\n0,0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="subject_id"):
        load_observational_csv(path)
