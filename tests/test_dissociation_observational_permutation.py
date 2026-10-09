"""Tests for observational mechanism-label permutation audit."""

import csv

import numpy as np

from research.dissociation.observational_csv import load_observational_csv
from research.dissociation.observational_permutation import (
    circular_shift_mechanisms,
    mechanism_gain,
    permutation_audit,
)


def _make(path):
    fields = [
        "subject_id", "session_index",
        "observer_switch_rate", "paired_recall_success", "morning_plan_agreement",
        "stress_load", "sleep_wake_irregularity", "social_conflict_load",
        "meth", "nmda_antagonism", "mor_partial_agonism",
        "kor_antagonism", "wake_anchor_disruption",
    ]
    rows = []
    for subject in ("A", "B", "C"):
        for session in range(14):
            meth = 0.7 if session % 5 == 0 else 0.0
            nmda = 0.6 if session % 5 == 1 else 0.0
            mor = 0.6 if session % 5 == 2 else 0.0
            kor = 0.6 if session % 5 == 3 else 0.0
            wake = 0.5 if session % 4 == 0 else 0.0
            rows.append({
                "subject_id": subject,
                "session_index": session,
                "observer_switch_rate": 0.06 + 0.22 * meth + 0.16 * nmda - 0.08 * mor - 0.06 * kor + 0.08 * wake,
                "paired_recall_success": 0.88 - 0.18 * nmda + 0.08 * mor + 0.05 * kor - 0.10 * wake,
                "morning_plan_agreement": 0.86 - 0.18 * wake - 0.05 * meth,
                "stress_load": 0.25 + 0.02 * (session % 3),
                "sleep_wake_irregularity": 0.20 + 0.02 * (session % 4),
                "social_conflict_load": 0.15,
                "meth": meth,
                "nmda_antagonism": nmda,
                "mor_partial_agonism": mor,
                "kor_antagonism": kor,
                "wake_anchor_disruption": wake,
            })
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_circular_shift_preserves_joint_mechanism_vectors_per_subject(tmp_path):
    path = tmp_path / "obs.csv"
    _make(path)
    rows, _ = load_observational_csv(path)
    shifted = circular_shift_mechanisms(rows, np.random.default_rng(7))

    for subject in {row["subject"] for row in rows}:
        original = sorted(
            tuple(row[name] for name in (
                "meth", "nmda_antagonism", "mor_partial_agonism",
                "kor_antagonism", "wake_anchor_disruption",
            ))
            for row in rows if row["subject"] == subject
        )
        permuted = sorted(
            tuple(row[name] for name in (
                "meth", "nmda_antagonism", "mor_partial_agonism",
                "kor_antagonism", "wake_anchor_disruption",
            ))
            for row in shifted if row["subject"] == subject
        )
        assert original == permuted


def test_permutation_audit_returns_empirical_null(tmp_path):
    path = tmp_path / "obs.csv"
    _make(path)
    rows, _ = load_observational_csv(path)
    result = permutation_audit(
        rows,
        permutations=12,
        seed=11,
        test_fraction=0.25,
    )
    assert result["status"] == "ok"
    assert result["valid_permutations"] > 0
    assert 0.0 < result["empirical_upper_tail_p"] <= 1.0
    assert result["permutation_method"] == "within_subject_joint_circular_shift"


def test_mechanism_gain_can_report_unavailable():
    assert mechanism_gain([])["status"] == "unavailable"
