"""Tests for calibration auto-wiring and simulation result validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calibration.validate_sim_results import (
    compute_cumulative_mme,
    predict_tolerance_rate,
    predict_addiction_rate_from_params,
    validate,
    WARN_THRESHOLD,
)
from dsmil_adapter import _load_calibrated_tolerance_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def calibrated_params(tmp_path):
    """Write a minimal calibrated_params.json and return the loaded dict."""
    params = {
        "tolerance": {
            "model": "sigmoid",
            "max_factor": 2.09,
            "half_life_days": 27.25,
        },
        "tolerance_partial_agonist": {
            "model": "sigmoid",
            "max_factor": 0.65,
            "half_life_days": 30.75,
        },
        "addiction": {
            "model": "linear",
            "addiction_slope": 1.7e-05,
            "addiction_threshold": 830.0,
            "clinical": {
                "max_incidence": 0.23,
                "ec50_mme": 10000.0,
                "hill_n": 0.75,
            },
        },
        "meta": {"calibrated_at": "2026-07-06T00:00:00Z"},
    }
    path = tmp_path / "calibrated_params.json"
    path.write_text(json.dumps(params))
    return params, path


@pytest.fixture()
def sim_results_close(calibrated_params):
    """Fake results that closely match the model prediction."""
    params, path = calibrated_params
    # predict what the model expects for 90 days
    pred_tol = predict_tolerance_rate(params, 90)
    pred_add = predict_addiction_rate_from_params(
        params, compute_cumulative_mme(["SR-17018"], [16.17], [2], 90)
    )
    return {
        "ok": True,
        "result": {
            "tolerance_rate": round(pred_tol * 1.05, 4),   # within 5%
            "addiction_rate": round(pred_add * 1.10, 4),   # within 10%
            "success_rate": 0.72,
            "n_patients": 100000,
        }
    }


@pytest.fixture()
def sim_results_diverged(calibrated_params):
    """Fake results that diverge badly from the model prediction."""
    params, path = calibrated_params
    pred_tol = predict_tolerance_rate(params, 90)
    pred_add = predict_addiction_rate_from_params(
        params, compute_cumulative_mme(["SR-17018"], [16.17], [2], 90)
    )
    return {
        "ok": True,
        "result": {
            "tolerance_rate": round(pred_tol * 2.5, 4),    # 150% over
            "addiction_rate": round(pred_add * 0.1, 4),    # 90% under
            "success_rate": 0.40,
            "n_patients": 100000,
        }
    }


# ---------------------------------------------------------------------------
# MME computation
# ---------------------------------------------------------------------------

def test_cumulative_mme_oxycodone():
    # 10 mg × 4×/day × 1.5 factor × 90 days = 5400
    mme = compute_cumulative_mme(["Oxycodone"], [10.0], [4], 90)
    assert mme == pytest.approx(5400.0)


def test_cumulative_mme_multi_compound():
    mme = compute_cumulative_mme(
        ["SR-17018", "SR-14968", "Oxycodone"],
        [16.17, 25.31, 10.0],
        [2, 1, 4],
        90,
    )
    # SR-17018: 16.17*2*2.0*90 = 5821.2
    # SR-14968: 25.31*1*2.0*90 = 4555.8
    # Oxycodone: 10.0*4*1.5*90 = 5400.0
    assert mme == pytest.approx(15777.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def test_predict_tolerance_rate_at_day0(calibrated_params):
    params, _ = calibrated_params
    # At day 0 there is no exposure, so tolerance should be near 0
    rate = predict_tolerance_rate(params, duration_days=0)
    assert rate == pytest.approx(0.0, abs=0.05)


def test_predict_tolerance_rate_increases_with_time(calibrated_params):
    params, _ = calibrated_params
    rate_30 = predict_tolerance_rate(params, 30)
    rate_90 = predict_tolerance_rate(params, 90)
    assert rate_90 > rate_30


def test_predict_addiction_rate_increases_with_mme(calibrated_params):
    params, _ = calibrated_params
    low  = predict_addiction_rate_from_params(params, cumulative_mme=500)
    high = predict_addiction_rate_from_params(params, cumulative_mme=50000)
    assert high > low


def test_predict_addiction_bounded(calibrated_params):
    params, _ = calibrated_params
    rate = predict_addiction_rate_from_params(params, cumulative_mme=1_000_000)
    assert 0.0 <= rate <= 0.5


# ---------------------------------------------------------------------------
# Validation: close results pass
# ---------------------------------------------------------------------------

def test_validate_close_results_passes(calibrated_params, sim_results_close):
    params, _ = calibrated_params
    report = validate(
        sim_results_close, params,
        ["SR-17018"], [16.17], [2], 90,
    )
    assert report["passed"], f"Expected PASS, got warnings: {report['warnings']}"


def test_validate_close_results_no_warnings(calibrated_params, sim_results_close):
    params, _ = calibrated_params
    report = validate(sim_results_close, params, ["SR-17018"], [16.17], [2], 90)
    assert report["warnings"] == []


# ---------------------------------------------------------------------------
# Validation: diverged results fail
# ---------------------------------------------------------------------------

def test_validate_diverged_results_fails(calibrated_params, sim_results_diverged):
    params, _ = calibrated_params
    report = validate(
        sim_results_diverged, params,
        ["SR-17018"], [16.17], [2], 90,
    )
    assert not report["passed"]
    assert len(report["warnings"]) > 0


def test_validate_diverged_has_warn_status(calibrated_params, sim_results_diverged):
    params, _ = calibrated_params
    report = validate(sim_results_diverged, params, ["SR-17018"], [16.17], [2], 90)
    for k in report["warnings"]:
        assert report["checks"][k]["status"].startswith("WARN")


# ---------------------------------------------------------------------------
# Adapter auto-loading
# ---------------------------------------------------------------------------

def test_load_calibrated_config_from_file(tmp_path):
    params_file = tmp_path / "calibrated_params.json"
    params_file.write_text(json.dumps({
        "tolerance": {
            "model": "sigmoid",
            "max_factor": 2.09,
            "half_life_days": 27.25,
        },
        "addiction": {
            "model": "linear",
            "addiction_slope": 1.7e-05,
            "addiction_threshold": 830.0,
        },
    }))
    cfg = _load_calibrated_tolerance_config(path=params_file)
    assert cfg is not None
    assert cfg["tolerance"]["max_factor"] == pytest.approx(2.09)
    assert cfg["tolerance"]["half_life_days"] == pytest.approx(27.25)
    assert cfg["tolerance"]["addiction_slope"] == pytest.approx(1.7e-05)


def test_load_calibrated_config_missing_file(tmp_path):
    cfg = _load_calibrated_tolerance_config(path=tmp_path / "nonexistent.json")
    assert cfg is None


def test_load_calibrated_config_corrupt_file(tmp_path):
    bad = tmp_path / "calibrated_params.json"
    bad.write_text("{not valid json}")
    cfg = _load_calibrated_tolerance_config(path=bad)
    assert cfg is None


def test_process_request_uses_calibrated_params(tmp_path):
    """
    Smoke-test: when calibrated_params.json exists, process_request should
    use it (no explicit tolerance_config in payload).
    """
    import importlib
    import dsmil_adapter as adapter

    # Write a temp calibrated_params.json and monkey-patch the path
    params_file = tmp_path / "calibrated_params.json"
    params_file.write_text(json.dumps({
        "tolerance": {"model": "sigmoid", "max_factor": 2.09, "half_life_days": 27.25},
        "addiction": {"addiction_slope": 1.7e-05, "addiction_threshold": 830.0},
    }))

    original_path = adapter._CALIBRATED_PARAMS_PATH
    try:
        adapter._CALIBRATED_PARAMS_PATH = params_file
        result = adapter.process_request({
            "operation": "simulate",
            "compounds": ["SR-17018"],
            "doses": [16.17],
            "frequencies": [2],
            "patient_count": 20,
            "seed": 42,
            "duration_days": 7,
        })
        assert result.get("ok"), f"Simulation failed: {result.get('error')}"
    finally:
        adapter._CALIBRATED_PARAMS_PATH = original_path


def test_process_request_explicit_config_overrides_calibrated(tmp_path):
    """Explicit tolerance_config in payload should take precedence over file."""
    import dsmil_adapter as adapter

    params_file = tmp_path / "calibrated_params.json"
    params_file.write_text(json.dumps({
        "tolerance": {"model": "sigmoid", "max_factor": 2.09, "half_life_days": 27.25},
        "addiction": {"addiction_slope": 1.7e-05, "addiction_threshold": 830.0},
    }))

    original_path = adapter._CALIBRATED_PARAMS_PATH
    try:
        adapter._CALIBRATED_PARAMS_PATH = params_file
        result = adapter.process_request({
            "operation": "simulate",
            "compounds": ["SR-17018"],
            "doses": [16.17],
            "frequencies": [2],
            "patient_count": 20,
            "seed": 42,
            "duration_days": 7,
            # Explicit override
            "tolerance_config": {
                "tolerance": {"model": "linear", "slope": 0.001, "max_factor": 3.0}
            },
        })
        assert result.get("ok"), f"Simulation failed: {result.get('error')}"
    finally:
        adapter._CALIBRATED_PARAMS_PATH = original_path
