"""Repeated-seed stability benchmark for observation-model selection.

Runs multiple independently generated synthetic datasets and records how often each
candidate observation model wins by held-out RMSE and BIC. This prevents architecture
choices from being driven by one favorable random realization.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.model_comparison import compare_observation_models
from research.dissociation.observation_model import ObservationConfig, simulate_observations
from research.dissociation.state_network import (
    StateNetworkConfig,
    StateNetworkParameters,
    simulate_state_network,
)


SCENARIOS = {
    "baseline": MechanismInput(),
    "meth": MechanismInput(meth=0.55),
    "nmda": MechanismInput(nmda_antagonism=0.45),
    "meth_nmda": MechanismInput(meth=0.55, nmda_antagonism=0.45),
}


def run_selection_stability(
    *,
    seeds: int = 8,
    steps: int = 480,
    n_states: int = 4,
    base_seed: int = 120,
    transient_lags: int = 3,
    test_every: int = 5,
) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be >= 1")

    rows = []
    for scenario_name, inputs in SCENARIOS.items():
        for offset in range(seeds):
            seed = base_seed + offset
            state_config = StateNetworkConfig(
                n_states=n_states,
                steps=steps,
                seed=seed,
                max_coconscious=min(3, n_states),
                sync_interval=max(24, steps // 5),
            )
            _, trace = simulate_state_network(
                inputs,
                config=state_config,
                params=StateNetworkParameters(),
                return_trace=True,
            )
            obs_config = ObservationConfig(
                n_states=n_states,
                seed=seed + 500,
            )
            observations = simulate_observations(trace, inputs, config=obs_config)
            fits = compare_observation_models(
                trace,
                observations.features,
                n_states=n_states,
                executive_weight=obs_config.executive_weight,
                transient_lags=transient_lags,
                test_every=test_every,
            )
            by_bic = sorted(fits, key=lambda fit: fit.bic)
            rows.append(
                {
                    "scenario": scenario_name,
                    "seed": seed,
                    "best_test_rmse": fits[0].name,
                    "best_bic": by_bic[0].name,
                    "fits": [fit.to_dict() for fit in fits],
                }
            )

    model_names = sorted(
        {
            fit["name"]
            for row in rows
            for fit in row["fits"]
        }
    )
    summary = {}
    for scenario_name in SCENARIOS:
        scenario_rows = [row for row in rows if row["scenario"] == scenario_name]
        rmse_wins = Counter(row["best_test_rmse"] for row in scenario_rows)
        bic_wins = Counter(row["best_bic"] for row in scenario_rows)

        metrics = {}
        for model_name in model_names:
            model_fits = [
                next(f for f in row["fits"] if f["name"] == model_name)
                for row in scenario_rows
            ]
            metrics[model_name] = {
                "median_test_rmse": float(
                    np.median([fit["test_rmse"] for fit in model_fits])
                ),
                "mean_test_rmse": float(
                    np.mean([fit["test_rmse"] for fit in model_fits])
                ),
                "median_test_r2": float(
                    np.median([fit["test_r2"] for fit in model_fits])
                ),
                "median_bic": float(
                    np.median([fit["bic"] for fit in model_fits])
                ),
                "test_rmse_wins": int(rmse_wins.get(model_name, 0)),
                "bic_wins": int(bic_wins.get(model_name, 0)),
            }

        summary[scenario_name] = {
            "runs": len(scenario_rows),
            "models": metrics,
        }

    return {
        "schema_version": 1,
        "model": "observation_model_selection_stability",
        "warning": (
            "Synthetic benchmark only. Winner frequencies reflect the current "
            "simulator and observation assumptions."
        ),
        "seeds": seeds,
        "steps": steps,
        "n_states": n_states,
        "base_seed": base_seed,
        "scenarios": {name: asdict(inputs) for name, inputs in SCENARIOS.items()},
        "summary": summary,
        "rows": rows,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--steps", type=int, default=480)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--base-seed", type=int, default=120)
    p.add_argument("--transient-lags", type=int, default=3)
    p.add_argument("--test-every", type=int, default=5)
    p.add_argument(
        "--output",
        default="runs/dissociation_model_selection_stability.json",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    result = run_selection_stability(
        seeds=args.seeds,
        steps=args.steps,
        n_states=args.states,
        base_seed=args.base_seed,
        transient_lags=args.transient_lags,
        test_every=args.test_every,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote model-selection stability benchmark to {out}")
    for scenario, record in result["summary"].items():
        print(f"scenario={scenario} runs={record['runs']}")
        ranked = sorted(
            record["models"].items(),
            key=lambda item: item[1]["median_test_rmse"],
        )
        for model, metrics in ranked:
            print(
                f"  {model:30s} "
                f"median_rmse={metrics['median_test_rmse']:.4f} "
                f"rmse_wins={metrics['test_rmse_wins']}/{record['runs']} "
                f"bic_wins={metrics['bic_wins']}/{record['runs']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
