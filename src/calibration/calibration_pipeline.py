"""
Calibration pipeline — CLI entry point
========================================
Runs all fitters and writes a single ``calibrated_params.json`` that the
simulation engine loads automatically.

Usage
-----
    python src/calibration/calibration_pipeline.py [--output PATH] [--verbose]

The output JSON has this structure::

    {
      "tolerance": {
        "model": "sigmoid",
        "max_factor": 2.91,
        "half_life_days": 12.5,
        "diagnostics": { ... }
      },
      "tolerance_partial_agonist": {
        "model": "sigmoid",
        "max_factor": 1.6,
        "half_life_days": 18.0,
        "diagnostics": { ... }
      },
      "addiction": {
        "model": "linear",
        "addiction_slope": 0.00312,
        "addiction_threshold": 48.2,
        "clinical": { ... },
        "diagnostics": { ... }
      },
      "meta": {
        "calibrated_at": "...",
        "sources": [ ... ]
      }
    }
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make src importable
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from calibration.tolerance_fitter import fit_tolerance_model
from calibration.addiction_fitter import fit_addiction_model

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "calibrated_params.json"


def run_calibration(output: Path, verbose: bool = True) -> dict:
    results = {}

    # ---- Tolerance: full agonist ----
    if verbose:
        print("Fitting tolerance model (full agonist)...")
    tol_full = fit_tolerance_model(compound_class="full_agonist")
    results["tolerance"] = tol_full
    if verbose:
        print(f"  max_factor={tol_full['max_factor']:.3f}  "
              f"half_life_days={tol_full['half_life_days']:.2f}  "
              f"R²={tol_full['diagnostics']['r_squared']:.4f}")

    # ---- Tolerance: partial agonist ----
    if verbose:
        print("Fitting tolerance model (partial agonist)...")
    tol_partial = fit_tolerance_model(compound_class="partial_agonist")
    results["tolerance_partial_agonist"] = tol_partial
    if verbose:
        print(f"  max_factor={tol_partial['max_factor']:.3f}  "
              f"half_life_days={tol_partial['half_life_days']:.2f}  "
              f"R²={tol_partial['diagnostics']['r_squared']:.4f}")

    # ---- Addiction ----
    if verbose:
        print("Fitting addiction model...")
    add = fit_addiction_model()
    results["addiction"] = add
    if verbose:
        print(f"  addiction_slope={add['addiction_slope']:.6f}  "
              f"addiction_threshold={add['addiction_threshold']:.2f}  "
              f"R²={add['diagnostics']['r_squared']:.4f}")

    results["meta"] = {
        "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [
            "data/calibration/tolerance_observations.csv",
            "data/calibration/addiction_incidence.csv",
        ],
        "notes": (
            "Parameters fitted to digitised literature data. "
            "Tolerance: equianalgesic dose-ratio vs days (Collett 1998, "
            "Angst & Clark 2006, Dumas 2008). "
            "Addiction: OUD incidence vs cumulative MME (Vowles 2015, "
            "Edlund 2014, Bohnert 2018, Nielsen 2012). "
            "mme_to_dopamine_factor is a dimensionless bridge requiring "
            "future validation against microdialysis data."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    if verbose:
        print(f"\nCalibrated parameters written to: {output}")

    return results


def build_tolerance_config(params: dict, compound_class: str = "full_agonist") -> dict:
    """
    Convert calibrated_params.json into a tolerance_config dict suitable
    for passing to ``PopulationSimulation.run_simulation()``.
    """
    tol_key = "tolerance" if compound_class == "full_agonist" else "tolerance_partial_agonist"
    tol = params.get(tol_key, params.get("tolerance", {}))
    add = params.get("addiction", {})

    return {
        "tolerance": {
            "model": tol.get("model", "sigmoid"),
            "max_factor": tol.get("max_factor", 3.0),
            "half_life_days": tol.get("half_life_days", 14.0),
            "addiction_model": add.get("model", "linear"),
            "addiction_slope": add.get("addiction_slope", 0.005),
            "addiction_threshold": add.get("addiction_threshold", 60.0),
        }
    }


def load_calibrated_params(path: Path = DEFAULT_OUTPUT) -> dict:
    """Load previously fitted parameters from disk."""
    if not path.exists():
        raise FileNotFoundError(
            f"No calibrated_params.json found at {path}. "
            "Run: python src/calibration/calibration_pipeline.py"
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calibrate ZeroPain tolerance and addiction model parameters from literature data."
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument(
        "--show-config", action="store_true",
        help="After fitting, print the tolerance_config dict for copy-paste use"
    )
    args = parser.parse_args()

    params = run_calibration(args.output, verbose=not args.quiet)

    if args.show_config:
        config = build_tolerance_config(params)
        print("\n--- tolerance_config (paste into your run) ---")
        print(json.dumps(config, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
