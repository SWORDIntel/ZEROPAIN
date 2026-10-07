"""Load consented longitudinal observational CSVs and compare simple null models.

This is a data-analysis bridge, not a collection protocol and not a drug-challenge
planner. Exposure/mechanism columns are OPTIONAL. If they are absent, models requiring
them are not fabricated by substituting zeros.

Accepted outcome representations:
- direct rate columns, or
- success/count + opportunity/trial columns.

Required identifiers:
- subject_id
- session_index

Optional context columns:
- stress_load
- sleep_wake_irregularity
- social_conflict_load
- time_trend (derived from session order when absent)

Optional mechanism annotation columns (dimensionless/research-coded, NOT doses):
- meth
- nmda_antagonism
- mor_partial_agonism
- kor_antagonism
- wake_anchor_disruption

Synthetic wearable/EEG column names are accepted as generic analysis channels only.
Their presence in a CSV does NOT make them validated DID biomarkers.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from research.dissociation.longitudinal_nulls import (
    CONTEXT_FEATURES,
    HISTORY_FEATURES,
    MECHANISM_FEATURES,
    LongitudinalConfig,
    ModelScore,
)
from research.dissociation.observable_model import ALL_CHANNELS


MISSING_TOKENS = {"", "na", "nan", "n/a", "null", "none", "."}


@dataclass(frozen=True)
class CsvSchemaReport:
    rows: int
    subjects: int
    available_outcomes: tuple[str, ...]
    available_context_features: tuple[str, ...]
    available_mechanism_features: tuple[str, ...]
    missing_fraction_by_outcome: dict[str, float]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _float(value: str | None) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip().lower()
    if text in MISSING_TOKENS:
        return float("nan")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"not numeric: {value!r}") from exc


def _rate(
    raw: Mapping[str, str],
    direct: str,
    numerator: str,
    denominator: str,
) -> float:
    direct_value = _float(raw.get(direct))
    if np.isfinite(direct_value):
        return direct_value
    num = _float(raw.get(numerator))
    den = _float(raw.get(denominator))
    if np.isfinite(num) and np.isfinite(den) and den > 0:
        return float(num / den)
    return float("nan")


def _subject_mapping(raw_rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    subjects = sorted({str(row.get("subject_id", "")).strip() for row in raw_rows})
    if "" in subjects:
        raise ValueError("subject_id cannot be blank")
    return {subject: idx for idx, subject in enumerate(subjects)}


def load_observational_csv(path: str | Path) -> tuple[list[dict], CsvSchemaReport]:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = tuple(reader.fieldnames or ())
        raw_rows = list(reader)

    for required in ("subject_id", "session_index"):
        if required not in fieldnames:
            raise ValueError(f"missing required column: {required}")
    if not raw_rows:
        raise ValueError("CSV contains no data rows")

    subject_map = _subject_mapping(raw_rows)
    context_available = tuple(name for name in CONTEXT_FEATURES if name in fieldnames)
    mechanism_available = tuple(name for name in MECHANISM_FEATURES if name in fieldnames)

    rows: list[dict] = []
    for raw in raw_rows:
        session_value = _float(raw.get("session_index"))
        if not np.isfinite(session_value):
            raise ValueError("session_index cannot be missing")

        row = {
            "subject": subject_map[str(raw["subject_id"]).strip()],
            "subject_id": str(raw["subject_id"]).strip(),
            "session": int(session_value),
            "observer_switch_rate": _rate(
                raw, "observer_switch_rate",
                "observer_switch_count", "switch_observation_checks",
            ),
            "paired_recall_success": _rate(
                raw, "paired_recall_success",
                "recall_successes", "recall_trials",
            ),
            "morning_plan_agreement": _rate(
                raw, "morning_plan_agreement",
                "plan_agreement_successes", "plan_trials",
            ),
            "wearable_arousal_index": _float(raw.get("wearable_arousal_index")),
            "eeg_connectivity_index": _float(raw.get("eeg_connectivity_index")),
        }

        for name in CONTEXT_FEATURES:
            row[name] = _float(raw.get(name)) if name in fieldnames else float("nan")
        for name in MECHANISM_FEATURES:
            row[name] = _float(raw.get(name)) if name in fieldnames else float("nan")
        rows.append(row)

    rows.sort(key=lambda row: (row["subject"], row["session"]))

    # Reject duplicate subject/session keys rather than averaging silently.
    seen = set()
    for row in rows:
        key = (row["subject"], row["session"])
        if key in seen:
            raise ValueError(f"duplicate subject/session: {row['subject_id']} / {row['session']}")
        seen.add(key)

    # Derive normalized time trend if absent and derive lagged reports.
    by_subject: dict[int, list[dict]] = {}
    for row in rows:
        by_subject.setdefault(row["subject"], []).append(row)

    for subject_rows in by_subject.values():
        min_session = min(row["session"] for row in subject_rows)
        max_session = max(row["session"] for row in subject_rows)
        lag_switch = float("nan")
        lag_recall = float("nan")
        for row in subject_rows:
            if "time_trend" not in fieldnames or not np.isfinite(row["time_trend"]):
                denom = max(1, max_session - min_session)
                row["time_trend"] = (row["session"] - min_session) / denom

            row["lag_observer_switch_rate"] = lag_switch
            row["lag_paired_recall_success"] = lag_recall
            if np.isfinite(row["observer_switch_rate"]):
                lag_switch = float(row["observer_switch_rate"])
            if np.isfinite(row["paired_recall_success"]):
                lag_recall = float(row["paired_recall_success"])

    outcome_available = tuple(
        channel
        for channel in ALL_CHANNELS
        if any(np.isfinite(row[channel]) for row in rows)
    )
    if not outcome_available:
        raise ValueError("CSV has no usable outcome observations")

    warnings = []
    if not mechanism_available:
        warnings.append(
            "No mechanism annotation columns present; receptor-labelled models will be skipped."
        )
    if "eeg_connectivity_index" in outcome_available:
        warnings.append(
            "eeg_connectivity_index is treated as a generic supplied numeric feature; "
            "this tool does not validate it as a DID biomarker."
        )

    report = CsvSchemaReport(
        rows=len(rows),
        subjects=len(subject_map),
        available_outcomes=outcome_available,
        available_context_features=context_available,
        available_mechanism_features=mechanism_available,
        missing_fraction_by_outcome={
            channel: float(np.mean([not np.isfinite(row[channel]) for row in rows]))
            for channel in outcome_available
        },
        warnings=tuple(warnings),
    )
    return rows, report


def _blocked_masks(rows: Sequence[dict], test_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    if not 0.1 <= test_fraction <= 0.5:
        raise ValueError("test_fraction must be in [0.1,0.5]")
    train = np.zeros(len(rows), dtype=bool)
    test = np.zeros(len(rows), dtype=bool)
    by_subject: dict[int, list[int]] = {}
    for idx, row in enumerate(rows):
        by_subject.setdefault(row["subject"], []).append(idx)

    for indices in by_subject.values():
        indices.sort(key=lambda idx: rows[idx]["session"])
        if len(indices) < 4:
            continue
        n_test = max(1, int(round(len(indices) * test_fraction)))
        train[indices[:-n_test]] = True
        test[indices[-n_test:]] = True
    return train, test


def _available_feature_set(rows: Sequence[dict], candidates: Sequence[str]) -> tuple[str, ...]:
    # A feature is considered available if at least half of training-agnostic rows
    # contain a finite value. Per-model fitting still drops rows missing that feature.
    return tuple(
        name for name in candidates
        if np.mean([np.isfinite(row.get(name, float("nan"))) for row in rows]) >= 0.5
    )


def _model_library(rows: Sequence[dict]) -> dict[str, tuple[str, ...]]:
    context = _available_feature_set(rows, CONTEXT_FEATURES)
    mechanism = _available_feature_set(rows, MECHANISM_FEATURES)
    history = _available_feature_set(rows, HISTORY_FEATURES)

    models: dict[str, tuple[str, ...]] = {"mean_only": ()}
    if history:
        models["history_available"] = history
    if context:
        models["context_available"] = context
    if context or history:
        models["context_history_available"] = context + history
    if mechanism:
        models["mechanism_available"] = mechanism
        models["context_plus_mechanism_available"] = context + mechanism
        models["full_available"] = context + history + mechanism
    return models


def _design(
    rows: Sequence[dict],
    features: Sequence[str],
    train_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    subjects = sorted({row["subject"] for row in rows})
    subject_columns = subjects[1:]

    feature_values = np.array([
        [row.get(name, float("nan")) for name in features]
        for row in rows
    ], dtype=float) if features else np.zeros((len(rows), 0))

    predictor_valid = (
        np.all(np.isfinite(feature_values), axis=1)
        if features else np.ones(len(rows), dtype=bool)
    )

    if features:
        valid_train = train_mask & predictor_valid
        if not np.any(valid_train):
            return np.empty((len(rows), 0)), predictor_valid
        mu = np.mean(feature_values[valid_train], axis=0)
        sd = np.std(feature_values[valid_train], axis=0)
        sd = np.where(sd < 1e-9, 1.0, sd)
        # Missing entries remain zero after standardization but are excluded by
        # predictor_valid; this avoids NaNs contaminating matrix multiplication.
        standardized = np.zeros_like(feature_values)
        finite = np.isfinite(feature_values)
        centered = (feature_values - mu) / sd
        standardized[finite] = centered[finite]
        feature_values = standardized

    subject_matrix = np.array([
        [1.0 if row["subject"] == subject else 0.0 for subject in subject_columns]
        for row in rows
    ])
    x = np.concatenate([
        np.ones((len(rows), 1)),
        subject_matrix,
        feature_values,
    ], axis=1)
    return x, predictor_valid


def score_observational_rows(
    rows: Sequence[dict],
    *,
    test_fraction: float = 0.25,
    ridge: float = 1e-3,
) -> list[ModelScore]:
    train_mask, test_mask = _blocked_masks(rows, test_fraction)
    if not np.any(train_mask) or not np.any(test_mask):
        raise ValueError("insufficient per-subject sessions for blocked time split")

    available_outcomes = [
        channel for channel in ALL_CHANNELS
        if any(np.isfinite(row[channel]) for row in rows)
    ]
    scores = []

    for model_name, features in _model_library(rows).items():
        x, predictor_valid = _design(rows, features, train_mask)
        if x.shape[1] == 0:
            continue

        train_sse = test_sse = 0.0
        train_n = test_n = 0
        test_y_all = []
        test_pred_all = []
        parameters = 0

        for channel in available_outcomes:
            y = np.array([row[channel] for row in rows], dtype=float)
            valid_train = train_mask & predictor_valid & np.isfinite(y)
            valid_test = test_mask & predictor_valid & np.isfinite(y)
            if np.sum(valid_train) <= x.shape[1] or not np.any(valid_test):
                continue

            xtx = x[valid_train].T @ x[valid_train]
            penalty = ridge * np.eye(x.shape[1])
            penalty[0, 0] = 0.0
            beta = np.linalg.solve(
                xtx + penalty,
                x[valid_train].T @ y[valid_train],
            )
            train_pred = x[valid_train] @ beta
            test_pred = x[valid_test] @ beta
            train_sse += float(np.sum((y[valid_train] - train_pred) ** 2))
            test_sse += float(np.sum((y[valid_test] - test_pred) ** 2))
            train_n += int(np.sum(valid_train))
            test_n += int(np.sum(valid_test))
            test_y_all.extend(y[valid_test].tolist())
            test_pred_all.extend(test_pred.tolist())
            parameters += len(beta)

        if train_n == 0 or test_n == 0:
            continue
        mse = test_sse / test_n
        y_test = np.asarray(test_y_all)
        pred = np.asarray(test_pred_all)
        sst = float(np.sum((y_test - np.mean(y_test)) ** 2))
        r2 = 1.0 - test_sse / sst if sst > 1e-12 else 0.0
        bic = float(
            train_n * np.log(max(train_sse, 1e-12) / train_n)
            + parameters * np.log(train_n)
        )
        scores.append(ModelScore(
            model=model_name,
            parameters=parameters,
            observed_test_values=test_n,
            test_mse=mse,
            test_rmse=float(np.sqrt(mse)),
            test_r2=r2,
            train_bic=bic,
        ))
    return sorted(scores, key=lambda score: score.test_mse)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_path")
    p.add_argument("--test-fraction", type=float, default=0.25)
    p.add_argument("--ridge", type=float, default=1e-3)
    p.add_argument("--output", default="runs/dissociation_observational_csv.json")
    return p


def main() -> int:
    args = _parser().parse_args()
    rows, schema = load_observational_csv(args.csv_path)
    scores = score_observational_rows(
        rows, test_fraction=args.test_fraction, ridge=args.ridge
    )
    report = {
        "schema_version": 1,
        "warning": (
            "Observational association analysis only. Model ranking does not establish "
            "causality or a treatment effect."
        ),
        "schema": schema.to_dict(),
        "models": [score.to_dict() for score in scores],
        "best_test_model": scores[0].model if scores else None,
        "best_bic_model": min(scores, key=lambda score: score.train_bic).model if scores else None,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote observational comparison to {out}")
    print(f"rows={schema.rows} subjects={schema.subjects}")
    print(f"outcomes={','.join(schema.available_outcomes)}")
    print(f"context={','.join(schema.available_context_features) or 'none'}")
    print(f"mechanism_annotations={','.join(schema.available_mechanism_features) or 'none'}")
    for warning in schema.warnings:
        print(f"warning: {warning}")
    for score in scores:
        print(
            f"{score.model:36s} rmse={score.test_rmse:.4f} "
            f"r2={score.test_r2:+.3f} bic={score.train_bic:+.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
