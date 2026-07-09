"""
Simulation result validator
============================
Compares observed tolerance / addiction rates from a completed simulation run
against what the calibrated model predicted for the same protocol.

Usage
-----
    python src/calibration/validate_sim_results.py \\
        --results   runs/sr-oxycodone-100k/results.json \\
        --params    calibrated_params.json \\
        --protocol  SR-17018,SR-14968,Oxycodone \\
        --doses     16.17,25.31,10.0 \\
        --frequencies 2,1,4 \\
        --duration  90

Output
------
Prints a validation report and writes ``validation_report.json`` alongside
the results file.  Any metric that deviates by > WARN_THRESHOLD is flagged.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_CALIBRATED_PARAMS_PATH = Path(__file__).resolve().parents[2] / "calibrated_params.json"

from calibration.tolerance_fitter import sigmoid_tolerance_trajectory
from calibration.addiction_fitter import predict_oud_incidence
from calibration.calibration_pipeline import load_calibrated_params

# Warn when observed deviates from prediction by more than this fraction
WARN_THRESHOLD = 0.30   # 30 %


# ---------------------------------------------------------------------------
# MME helpers
# ---------------------------------------------------------------------------

# Approximate oral MME conversion factors (conservative clinical references)
_MME_FACTORS: Dict[str, float] = {
    "Oxycodone":  1.5,
    "Morphine":   1.0,
    "Hydrocodone": 1.0,
    "Buprenorphine": 30.0,
    "Tramadol":   0.1,
    "Tapentadol": 0.4,
    "Oliceridine": 2.0,
    # SR compounds: g-protein biased, conservative equiv. to fentanyl range
    "SR-17018":   2.0,
    "SR-14968":   2.0,
    "PZM21":      1.5,
    "OPID":       1.0,
}


def compute_cumulative_mme(
    compounds: List[str],
    doses_mg: List[float],
    frequencies: List[int],
    duration_days: int,
) -> float:
    """Total MME across all compounds over the full protocol duration."""
    total = 0.0
    for name, dose, freq in zip(compounds, doses_mg, frequencies):
        factor = _MME_FACTORS.get(name, 1.0)
        total += dose * freq * factor * duration_days
    return total


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

def predict_tolerance_rate(
    params: Dict[str, Any],
    duration_days: int,
    compound_class: str = "full_agonist",
) -> float:
    """
    Predict the fraction of patients expected to have clinically meaningful
    tolerance (tolerance_level > 0.5 * max_factor) at ``duration_days``.

    The sigmoid model gives the *mean* tolerance level across a homogeneous
    population; we use a Normal approximation with CV=30% to compute the
    fraction above the threshold.
    """
    tol_key = "tolerance" if compound_class == "full_agonist" else "tolerance_partial_agonist"
    tol = params.get(tol_key, params.get("tolerance", {}))
    max_factor = tol.get("max_factor", 3.0)
    half_life = tol.get("half_life_days", 14.0)

    mean_level = float(sigmoid_tolerance_trajectory(
        np.array([float(duration_days)]), max_factor, half_life
    )[0])

    # Fraction above 50 % of ceiling = "significant tolerance"
    threshold = 0.5 * max_factor
    cv = 0.30
    sigma = mean_level * cv if mean_level > 0 else 1e-6
    # P(level > threshold) from Normal CDF
    z = (threshold - mean_level) / sigma
    p_above = 0.5 * (1.0 + math.erf(-z / math.sqrt(2)))
    return round(float(np.clip(p_above, 0.0, 1.0)), 4)


def predict_addiction_rate_from_params(
    params: Dict[str, Any],
    cumulative_mme: float,
) -> float:
    """
    Predict OUD incidence for the given cumulative MME using the fitted Hill model.
    """
    add = params.get("addiction", {})
    clinical = add.get("clinical", {})
    max_inc = clinical.get("max_incidence", 0.25)
    ec50 = clinical.get("ec50_mme", 5000.0)
    hill_n = clinical.get("hill_n", 1.0)
    pred = float(predict_oud_incidence(
        np.array([cumulative_mme]), max_inc, ec50, hill_n
    )[0])
    return round(pred, 4)


# ---------------------------------------------------------------------------
# Validation core
# ---------------------------------------------------------------------------

def validate(
    results: Dict[str, Any],
    params: Dict[str, Any],
    compounds: List[str],
    doses_mg: List[float],
    frequencies: List[int],
    duration_days: int,
) -> Dict[str, Any]:
    """
    Compare observed simulation metrics with model predictions.

    Parameters
    ----------
    results:
        JSON output from ``process_request`` or the simulation pipeline.
        Expected keys: ``tolerance_rate``, ``addiction_rate``, ``success_rate``.
    params:
        Loaded ``calibrated_params.json``.
    """
    # Unwrap result envelope if present
    if "result" in results and isinstance(results["result"], dict):
        obs = results["result"]
    elif "simulation" in results and isinstance(results["simulation"], dict):
        obs = results["simulation"]
    else:
        obs = results

    cumulative_mme = compute_cumulative_mme(compounds, doses_mg, frequencies, duration_days)

    # --- Predictions ---
    pred_tol = predict_tolerance_rate(params, duration_days)
    pred_add = predict_addiction_rate_from_params(params, cumulative_mme)

    # --- Observed ---
    obs_tol = float(obs.get("tolerance_rate", float("nan")))
    obs_add = float(obs.get("addiction_rate", float("nan")))
    obs_success = float(obs.get("success_rate", float("nan")))
    n_patients = int(obs.get("n_patients", obs.get("total_patients", 0)))

    # --- Divergence ---
    def _div(pred: float, observed: float) -> Optional[float]:
        if math.isnan(observed) or pred <= 0:
            return None
        return round(abs(observed - pred) / max(pred, 1e-9), 4)

    tol_div = _div(pred_tol, obs_tol)
    add_div = _div(pred_add, obs_add)

    def _flag(div: Optional[float]) -> str:
        if div is None:
            return "missing"
        if div > WARN_THRESHOLD:
            return f"WARN (dev={div:.1%})"
        return f"ok (dev={div:.1%})"

    checks = {
        "tolerance_rate": {
            "predicted": pred_tol,
            "observed": obs_tol,
            "divergence": tol_div,
            "status": _flag(tol_div),
        },
        "addiction_rate": {
            "predicted": pred_add,
            "observed": obs_add,
            "divergence": add_div,
            "status": _flag(add_div),
        },
    }

    warnings = [k for k, v in checks.items() if v["status"].startswith("WARN")]
    passed = len(warnings) == 0

    protocol_summary = {
        "compounds": compounds,
        "doses_mg": doses_mg,
        "frequencies": frequencies,
        "duration_days": duration_days,
        "cumulative_mme": round(cumulative_mme, 1),
        "n_patients": n_patients,
    }

    # Additional observed metrics (no prediction yet)
    extras = {
        k: obs.get(k)
        for k in ("success_rate", "mean_analgesia", "safety_score",
                  "mean_tolerance", "mean_addiction")
        if obs.get(k) is not None
    }

    return {
        "passed": passed,
        "warnings": warnings,
        "checks": checks,
        "protocol": protocol_summary,
        "extras": extras,
        "calibration_source": str(_CALIBRATED_PARAMS_PATH)
            if _CALIBRATED_PARAMS_PATH.exists() else "default_params",
    }


def print_report(report: Dict[str, Any]) -> None:
    status = "✅ PASS" if report["passed"] else "⚠️  WARN"
    print(f"\n{'='*60}")
    print(f"  Validation report  {status}")
    print(f"{'='*60}")
    proto = report["protocol"]
    print(f"  Protocol : {', '.join(proto['compounds'])}")
    print(f"  Doses    : {proto['doses_mg']} mg")
    print(f"  Duration : {proto['duration_days']} days")
    print(f"  MME total: {proto['cumulative_mme']:,.0f}")
    print(f"  Patients : {proto['n_patients']:,}")
    print()
    for metric, v in report["checks"].items():
        pred = v["predicted"]
        obs  = v["observed"]
        st   = v["status"]
        obs_str = f"{obs:.3f}" if not math.isnan(obs) else "missing"
        print(f"  {metric:<20}  pred={pred:.3f}  obs={obs_str}  [{st}]")
    if report["extras"]:
        print()
        print("  Extra observed metrics:")
        for k, val in report["extras"].items():
            print(f"    {k:<22} {val:.4f}" if isinstance(val, float) else f"    {k:<22} {val}")
    if report["warnings"]:
        print()
        print(f"  ⚠️  Warnings on: {', '.join(report['warnings'])}")
        print("  Consider re-calibrating or checking the mme_to_dopamine bridge factor.")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate simulation results against calibrated model predictions."
    )
    parser.add_argument("--results", type=Path, required=True,
                        help="Path to simulation results JSON")
    parser.add_argument("--params", type=Path, default=_CALIBRATED_PARAMS_PATH,
                        help="Path to calibrated_params.json")
    parser.add_argument("--compounds", type=str, required=True,
                        help="Comma-separated compound names, e.g. SR-17018,SR-14968,Oxycodone")
    parser.add_argument("--doses", type=str, required=True,
                        help="Comma-separated doses (mg), e.g. 16.17,25.31,10.0")
    parser.add_argument("--frequencies", type=str, required=True,
                        help="Comma-separated daily frequencies, e.g. 2,1,4")
    parser.add_argument("--duration", type=int, default=90,
                        help="Protocol duration in days (default: 90)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write JSON report alongside the results file")
    args = parser.parse_args()

    with args.results.open("r", encoding="utf-8") as f:
        results = json.load(f)

    params = load_calibrated_params(args.params)

    compounds = [c.strip() for c in args.compounds.split(",")]
    doses = [float(d) for d in args.doses.split(",")]
    frequencies = [int(fr) for fr in args.frequencies.split(",")]

    report = validate(results, params, compounds, doses, frequencies, args.duration)
    print_report(report)

    out_path = args.output or args.results.parent / "validation_report.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to: {out_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
