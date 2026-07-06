"""
Addiction model calibration
============================
Fits ``LinearAddiction`` parameters (``slope``, ``threshold``) to observed
OUD incidence vs cumulative MME data from cohort studies.

Bridge between clinical data and simulator internals
-----------------------------------------------------
The simulator's dopamine signal is in internal units, not nanomolar.
The bridge is:

    cumulative_dopamine_signal  ≈  mme_to_dopamine_factor * cumulative_mme

where ``mme_to_dopamine_factor`` is also fitted, giving us 3 free parameters:
    - slope        : addiction accumulation rate per unit dopamine-above-threshold per day
    - threshold    : dopamine level below which no addiction accumulates
    - mme_factor   : linear scaling from clinical MME to simulator dopamine units

The final output is a ``(slope, threshold)`` pair in simulator units, and the
``mme_factor`` is stored for reference / future dimensionality work.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "calibration"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@dataclass
class AddictionObservation:
    cumulative_mme: float      # total morphine milligram equivalents
    oud_incidence: float       # proportion 0-1 meeting DSM-5 OUD
    study_weeks: float
    context: str


def load_addiction_observations(
    path: Optional[Path] = None,
) -> List[AddictionObservation]:
    path = path or DATA_DIR / "addiction_incidence.csv"
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            rows.append(AddictionObservation(
                cumulative_mme=float(row["cumulative_mme"]),
                oud_incidence=float(row["oud_incidence"]),
                study_weeks=float(row["study_weeks"]),
                context=row.get("context", "").strip(),
            ))
    return sorted(rows, key=lambda o: o.cumulative_mme)


# ---------------------------------------------------------------------------
# Model prediction
# ---------------------------------------------------------------------------

def predict_oud_incidence(
    cumulative_mme: np.ndarray,
    max_incidence: float,
    ec50_mme: float,
    hill_n: float = 1.0,
) -> np.ndarray:
    """
    Predict OUD incidence from cumulative MME using a Hill / Emax model.

    The Hill equation captures the concave-up, saturating shape of cumulative
    exposure → incidence data better than a logistic curve:

        p(OUD) = max_incidence * mme^n / (ec50^n + mme^n)

    Parameters
    ----------
    cumulative_mme:
        Total morphine milligram equivalents.
    max_incidence:
        Asymptotic OUD incidence (fitted; should be ~0.2–0.4 given observed data).
    ec50_mme:
        MME at which incidence reaches max_incidence/2.
    hill_n:
        Hill coefficient (steepness).  n=1 → simple saturation; n>1 → sigmoidal.
    """
    mme = np.asarray(cumulative_mme, dtype=float)
    mme_n = np.power(np.maximum(mme, 0.0), hill_n)
    ec50_n = max(ec50_mme, 1.0) ** hill_n
    return max_incidence * mme_n / (ec50_n + mme_n)


def _addiction_loss(
    params: np.ndarray,
    obs_mme: np.ndarray,
    obs_incidence: np.ndarray,
) -> float:
    """Mean-squared error for the Hill OUD incidence model."""
    max_inc = max(abs(params[0]), 1e-6)
    ec50 = max(abs(params[1]), 1.0)
    hill_n = max(abs(params[2]), 0.1)
    pred = predict_oud_incidence(obs_mme, max_inc, ec50, hill_n)
    return float(np.mean((pred - obs_incidence) ** 2))


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------

def fit_addiction_model(
    observations: Optional[List[AddictionObservation]] = None,
    data_path: Optional[Path] = None,
    # Conversion: simulator dopamine unit per MME unit
    # Default 0.8 = rough scaling so 5000 MME ≈ 4000 simulator dopamine units
    # (above the default 60-unit threshold after ~70 days at moderate dose)
    mme_to_dopamine: float = 0.8,
) -> Dict:
    """
    Fit the addiction model and convert back to simulator internal units.

    Returns a dict with ``slope`` and ``threshold`` in simulator units,
    ready to write into ``calibrated_params.json``.
    """
    if observations is None:
        observations = load_addiction_observations(data_path)

    obs_mme = np.array([o.cumulative_mme for o in observations])
    obs_inc = np.array([o.oud_incidence for o in observations])

    # --- Fit Hill model in MME space ---
    # params: [max_incidence, ec50_mme, hill_n]
    best_loss = float("inf")
    obs_max_inc = float(obs_inc.max())
    best_params = np.array([obs_max_inc * 1.2, 5000.0, 1.0])

    for max_inc in np.arange(obs_max_inc * 0.8, obs_max_inc * 2.0, obs_max_inc * 0.1):
        for ec50 in [500, 1000, 2000, 5000, 10000, 20000, 40000]:
            for hn in [0.5, 0.75, 1.0, 1.25, 1.5]:
                p = np.array([max_inc, float(ec50), hn])
                loss = _addiction_loss(p, obs_mme, obs_inc)
                if loss < best_loss:
                    best_loss = loss
                    best_params = p.copy()

    # Fine refinement
    step = best_params * 0.15
    step[2] = 0.1  # hill_n step
    for _ in range(500):
        improved = False
        for i in range(3):
            for sign in (-1, 1):
                candidate = best_params.copy()
                candidate[i] = max(candidate[i] + sign * step[i], 1e-10)
                loss = _addiction_loss(candidate, obs_mme, obs_inc)
                if loss < best_loss:
                    best_loss = loss
                    best_params = candidate
                    improved = True
        step *= 0.5
        if step.max() < 1e-10:
            break

    max_inc_fit = float(abs(best_params[0]))
    ec50_fit = float(abs(best_params[1]))
    hill_n_fit = float(abs(best_params[2]))

    # --- Convert to simulator units ---
    # In the simulator, addiction_level += slope * (dopamine - threshold) * dt
    # We approximate: slope_sim ≈ max_inc / (ec50 * mme_to_dopamine)
    # threshold_sim ≈ ec50 * mme_to_dopamine * 0.1  (low baseline)
    slope_sim = max_inc_fit / max(ec50_fit * mme_to_dopamine, 1e-6)
    threshold_sim = ec50_fit * mme_to_dopamine * 0.05

    # R² in MME space
    pred = predict_oud_incidence(obs_mme, max_inc_fit, ec50_fit, hill_n_fit)
    ss_res = float(np.sum((obs_inc - pred) ** 2))
    ss_tot = float(np.sum((obs_inc - obs_inc.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "model": "linear",
        # Simulator-unit parameters (use these in tolerance_config)
        "addiction_slope": round(slope_sim, 8),
        "addiction_threshold": round(threshold_sim, 4),
        # Clinical-space parameters (for reference / validation)
        "clinical": {
            "max_incidence": round(max_inc_fit, 5),
            "ec50_mme": round(ec50_fit, 1),
            "hill_n": round(hill_n_fit, 4),
            "mme_to_dopamine_factor": mme_to_dopamine,
        },
        "diagnostics": {
            "mse": round(best_loss, 8),
            "r_squared": round(r_squared, 4),
            "n_observations": len(observations),
            "data_source": "data/calibration/addiction_incidence.csv",
        },
    }
