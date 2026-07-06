"""Tests for the calibration data pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calibration.tolerance_fitter import (
    load_tolerance_observations,
    sigmoid_tolerance_trajectory,
    fit_tolerance_model,
)
from calibration.addiction_fitter import (
    load_addiction_observations,
    predict_oud_incidence,
    fit_addiction_model,
)
from calibration.calibration_pipeline import (
    build_tolerance_config,
    run_calibration,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def test_tolerance_observations_load():
    obs = load_tolerance_observations()
    assert len(obs) >= 10
    # All should be full_agonist by default
    assert all(o.compound_class == "full_agonist" for o in obs)
    # dose_ratio always >= 1 (can't need less drug to achieve same effect)
    assert all(o.dose_ratio >= 1.0 for o in obs)


def test_tolerance_observations_partial_agonist():
    obs = load_tolerance_observations(compound_class="partial_agonist")
    assert len(obs) >= 3
    assert all(o.compound_class == "partial_agonist" for o in obs)


def test_addiction_observations_load():
    obs = load_addiction_observations()
    assert len(obs) >= 10
    # Incidence always in [0, 1]
    assert all(0.0 <= o.oud_incidence <= 1.0 for o in obs)
    # MME always positive
    assert all(o.cumulative_mme > 0 for o in obs)


# ---------------------------------------------------------------------------
# Model prediction
# ---------------------------------------------------------------------------

def test_sigmoid_trajectory_starts_at_zero():
    days = np.array([0.0, 7.0, 14.0, 90.0])
    traj = sigmoid_tolerance_trajectory(days, max_factor=3.0, half_life_days=14.0)
    assert traj[0] == pytest.approx(0.0, abs=0.05)


def test_sigmoid_trajectory_monotone():
    days = np.linspace(0, 90, 50)
    traj = sigmoid_tolerance_trajectory(days, max_factor=3.0, half_life_days=14.0)
    # Should be non-decreasing
    assert np.all(np.diff(traj) >= -1e-6)


def test_sigmoid_trajectory_bounded_by_max_factor():
    days = np.linspace(0, 365, 100)
    traj = sigmoid_tolerance_trajectory(days, max_factor=2.5, half_life_days=14.0)
    assert float(traj.max()) <= 2.5 + 1e-6


def test_oud_incidence_monotone():
    mme = np.linspace(0, 50000, 100)
    inc = predict_oud_incidence(mme, max_incidence=0.25, ec50_mme=5000.0, hill_n=1.0)
    assert np.all(np.diff(inc) >= -1e-9)


def test_oud_incidence_bounded():
    mme = np.array([0.0, 100000.0])
    inc = predict_oud_incidence(mme, max_incidence=0.25, ec50_mme=5000.0, hill_n=1.0)
    assert inc.max() <= 0.5 + 1e-6
    assert inc.min() >= 0.0


# ---------------------------------------------------------------------------
# Fitters
# ---------------------------------------------------------------------------

def test_fit_tolerance_returns_plausible_params():
    result = fit_tolerance_model(compound_class="full_agonist")
    assert 1.0 <= result["max_factor"] <= 6.0
    assert 3.0 <= result["half_life_days"] <= 60.0
    assert result["diagnostics"]["r_squared"] > 0.8, (
        f"R² too low: {result['diagnostics']['r_squared']:.4f} — "
        "sigmoid fit is not capturing the dose-ratio data well"
    )


def test_fit_tolerance_partial_agonist_lower_than_full():
    full = fit_tolerance_model(compound_class="full_agonist")
    partial = fit_tolerance_model(compound_class="partial_agonist")
    # Partial agonists should have lower max_factor
    assert partial["max_factor"] < full["max_factor"], (
        f"Partial agonist max_factor ({partial['max_factor']}) should be "
        f"less than full agonist ({full['max_factor']})"
    )


def test_fit_addiction_returns_plausible_params():
    result = fit_addiction_model()
    assert result["addiction_slope"] > 0
    assert result["addiction_threshold"] > 0
    assert result["diagnostics"]["r_squared"] > 0.7, (
        f"Addiction fit R² too low: {result['diagnostics']['r_squared']:.4f}"
    )


def test_fit_addiction_clinical_params_reasonable():
    result = fit_addiction_model()
    clinical = result["clinical"]
    # ec50_mme should be in the plausible clinical range (500, 40000)
    assert 500 < clinical["ec50_mme"] < 40000, (
        f"ec50_mme={clinical['ec50_mme']} outside plausible clinical range"
    )


# ---------------------------------------------------------------------------
# Pipeline & config building
# ---------------------------------------------------------------------------

def test_build_tolerance_config_structure():
    fake_params = {
        "tolerance": {
            "model": "sigmoid",
            "max_factor": 2.9,
            "half_life_days": 12.5,
        },
        "addiction": {
            "model": "linear",
            "addiction_slope": 0.003,
            "addiction_threshold": 50.0,
        },
    }
    config = build_tolerance_config(fake_params)
    assert "tolerance" in config
    tol = config["tolerance"]
    assert tol["model"] == "sigmoid"
    assert tol["max_factor"] == 2.9
    assert tol["addiction_slope"] == 0.003


def test_run_calibration_writes_json(tmp_path):
    out = tmp_path / "params.json"
    result = run_calibration(out, verbose=False)
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert "tolerance" in loaded
    assert "addiction" in loaded
    assert "meta" in loaded
    assert loaded["meta"]["calibrated_at"]


def test_calibrated_config_feeds_into_tolerance_model(tmp_path):
    """End-to-end: calibrate -> build config -> instantiate model."""
    out = tmp_path / "params.json"
    params = run_calibration(out, verbose=False)
    config = build_tolerance_config(params)

    # Import and instantiate the tolerance model
    from tolerance_models import make_tolerance_model, ToleranceState
    model = make_tolerance_model(config["tolerance"])
    state = ToleranceState()
    for _ in range(30):
        state = model.update(state, exposure=0.3, dt_days=1.0)
    assert state.level > 0, "Tolerance should accumulate under constant exposure"
    assert state.level <= config["tolerance"]["max_factor"] + 1e-6
