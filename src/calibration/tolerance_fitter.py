"""
Tolerance model calibration
============================
Fits `SigmoidTolerance` parameters (``half_life_days``, ``max_factor``) to
observed dose-ratio-vs-time data from opioid dose-escalation studies.

The mapping from the clinical observation (dose_ratio) to the simulator's
tolerance *level* is:

    tolerance_level  =  dose_ratio - 1.0

i.e. a dose ratio of 1.0 means zero tolerance, 3.0 means the simulator's
``max_factor=3`` ceiling has been reached.  The SigmoidTolerance model targets
this value assuming constant daily exposure of ``exposure_per_day``.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "calibration"


@dataclass
class ToleranceObservation:
    day: float
    dose_ratio: float          # equianalgesic dose ratio (1.0 = no tolerance)
    compound_class: str
    notes: str

    @property
    def tolerance_level(self) -> float:
        """Convert dose_ratio to simulator tolerance_level."""
        return max(0.0, self.dose_ratio - 1.0)


def load_tolerance_observations(
    path: Optional[Path] = None,
    compound_class: str = "full_agonist",
) -> List[ToleranceObservation]:
    """Load digitised dose-ratio observations, optionally filtering by class."""
    path = path or DATA_DIR / "tolerance_observations.csv"
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            obs = ToleranceObservation(
                day=float(row["day"]),
                dose_ratio=float(row["dose_ratio"]),
                compound_class=row["compound_class"].strip(),
                notes=row.get("notes", "").strip(),
            )
            if compound_class == "all" or obs.compound_class == compound_class:
                rows.append(obs)
    return sorted(rows, key=lambda o: o.day)


# ---------------------------------------------------------------------------
# Model prediction
# ---------------------------------------------------------------------------

def sigmoid_tolerance_trajectory(
    days: np.ndarray,
    max_factor: float,
    half_life_days: float,
) -> np.ndarray:
    """
    Predict tolerance level at each *day* assuming constant daily dosing.

    Under constant exposure the SigmoidTolerance ODE has the analytic solution::

        tol(t) = max_factor * (1 - exp(-t * ln2 / half_life_days))

    This is an exponential approach to the ceiling, which is exactly what the
    clinical dose-ratio data shows over weeks-to-months timescales.

    Parameters
    ----------
    days:
        Array of day values.
    max_factor:
        Asymptotic ceiling (tolerance_level = dose_ratio - 1 at plateau).
    half_life_days:
        Time (days) to reach 50 % of max_factor under constant exposure.
    """
    k = math.log(2) / max(half_life_days, 1e-3)
    return max_factor * (1.0 - np.exp(-k * np.asarray(days, dtype=float)))


# ---------------------------------------------------------------------------
# Loss & fitting
# ---------------------------------------------------------------------------

def _tolerance_loss(
    params: np.ndarray,
    obs_days: np.ndarray,
    obs_levels: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> float:
    """Weighted mean-squared error between predicted and observed tolerance levels."""
    max_factor = abs(params[0])
    half_life_days = max(abs(params[1]), 0.5)  # physical minimum 0.5 days
    pred = sigmoid_tolerance_trajectory(obs_days, max_factor, half_life_days)
    residuals = pred - obs_levels
    if weights is not None:
        return float(np.mean(weights * residuals ** 2))
    return float(np.mean(residuals ** 2))


def fit_tolerance_model(
    observations: Optional[List[ToleranceObservation]] = None,
    compound_class: str = "full_agonist",
    data_path: Optional[Path] = None,
) -> Dict:
    """
    Fit SigmoidTolerance parameters to observed dose-ratio data.

    Returns a dict with the fitted parameters and diagnostics, ready to
    be written into ``calibrated_params.json``.
    """
    if observations is None:
        observations = load_tolerance_observations(data_path, compound_class)

    obs_days = np.array([o.day for o in observations])
    obs_levels = np.array([o.tolerance_level for o in observations])

    # cap max_factor search at 10% above the observed ceiling
    obs_ceiling = float(obs_levels.max()) + 0.1

    # Weight later timepoints less (plateau region is noisier in the literature)
    weights = 1.0 / (1.0 + obs_days / 30.0)

    # Grid search across biologically plausible range
    best_loss = float("inf")
    best_params = np.array([obs_ceiling, 14.0])

    for max_f in np.arange(obs_ceiling * 0.7, obs_ceiling * 1.3, 0.1):
        for hl in np.arange(3.0, 45.0, 1.0):   # 3–45 days covers clinical range
            p = np.array([max_f, hl])
            loss = _tolerance_loss(p, obs_days, obs_levels, weights)
            if loss < best_loss:
                best_loss = loss
                best_params = p.copy()

    # Fine-grained coordinate refinement
    step = np.array([0.05, 0.5])
    for _ in range(400):
        improved = False
        for i in range(2):
            for sign in (-1, 1):
                candidate = best_params.copy()
                candidate[i] = max(candidate[i] + sign * step[i], 0.01)
                loss = _tolerance_loss(candidate, obs_days, obs_levels, weights)
                if loss < best_loss:
                    best_loss = loss
                    best_params = candidate
                    improved = True
        step *= 0.5
        if step.max() < 1e-6:
            break

    max_factor_fit = float(abs(best_params[0]))
    half_life_fit = float(max(abs(best_params[1]), 0.5))

    # Compute R²
    pred = sigmoid_tolerance_trajectory(obs_days, max_factor_fit, half_life_fit)
    ss_res = float(np.sum((obs_levels - pred) ** 2))
    ss_tot = float(np.sum((obs_levels - obs_levels.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "model": "sigmoid",
        "compound_class": compound_class,
        "max_factor": round(max_factor_fit, 4),
        "half_life_days": round(half_life_fit, 4),
        "diagnostics": {
            "mse": round(best_loss, 6),
            "r_squared": round(r_squared, 4),
            "n_observations": len(observations),
            "data_source": "data/calibration/tolerance_observations.csv",
        },
    }
