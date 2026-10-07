"""Held-out model comparison for synthetic physiology observations.

Candidate models:
1. null mean-only;
2. executive-state identity;
3. co-conscious weighted mixture;
4. mixture + switch-transition transient basis.

The fitter uses only NumPy least squares. It reports train/test RMSE and R² plus BIC.
The richer model only "wins" if it improves held-out prediction enough to justify its
additional parameters.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.observation_model import (
    FEATURE_NAMES,
    ObservationConfig,
    _mixture_weights,
    simulate_observations,
)
from research.dissociation.state_network import (
    StateNetworkConfig,
    StateNetworkParameters,
    StateNetworkTrace,
    simulate_state_network,
)


@dataclass
class ModelFit:
    name: str
    columns: int
    parameters: int
    train_rmse: float
    test_rmse: float
    train_r2: float
    test_r2: float
    bic: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def _split_mask(n: int, test_every: int = 5) -> tuple[np.ndarray, np.ndarray]:
    if test_every < 2:
        raise ValueError("test_every must be >= 2")
    idx = np.arange(n)
    test = idx % test_every == 0
    train = ~test
    if not np.any(train) or not np.any(test):
        raise ValueError("split produced empty train or test set")
    return train, test


def _design_null(trace: StateNetworkTrace, n_states: int, executive_weight: float) -> np.ndarray:
    del n_states, executive_weight
    return np.ones((len(trace.executive), 1), dtype=float)


def _design_executive(
    trace: StateNetworkTrace,
    n_states: int,
    executive_weight: float,
) -> np.ndarray:
    del executive_weight
    x = np.zeros((len(trace.executive), n_states), dtype=float)
    x[np.arange(len(trace.executive)), np.asarray(trace.executive)] = 1.0
    return x


def _design_mixture(
    trace: StateNetworkTrace,
    n_states: int,
    executive_weight: float,
) -> np.ndarray:
    rows = []
    for executive, active in zip(trace.executive, trace.coconscious):
        rows.append(
            _mixture_weights(
                active,
                executive,
                n_states,
                executive_weight,
            )
        )
    return np.asarray(rows, dtype=float)


def _transition_basis(
    trace: StateNetworkTrace,
    n_states: int,
    *,
    lags: int = 3,
) -> np.ndarray:
    """Ordered transition-pair basis at switch step and following lags."""

    if lags < 1:
        raise ValueError("lags must be >= 1")

    pairs = [
        (src, dst)
        for src in range(n_states)
        for dst in range(n_states)
        if src != dst
    ]
    pair_index = {pair: idx for idx, pair in enumerate(pairs)}
    basis = np.zeros((len(trace.executive), len(pairs) * lags), dtype=float)

    for step in range(1, len(trace.executive)):
        src = trace.executive[step - 1]
        dst = trace.executive[step]
        if src == dst:
            continue
        base = pair_index[(src, dst)] * lags
        for lag in range(lags):
            target = step + lag
            if target < len(trace.executive):
                basis[target, base + lag] = 1.0
    return basis


def build_designs(
    trace: StateNetworkTrace,
    *,
    n_states: int,
    executive_weight: float,
    transient_lags: int = 3,
) -> Dict[str, np.ndarray]:
    mixture = _design_mixture(trace, n_states, executive_weight)
    transient = _transition_basis(trace, n_states, lags=transient_lags)
    return {
        "null": _design_null(trace, n_states, executive_weight),
        "executive_state": _design_executive(trace, n_states, executive_weight),
        "mixture": mixture,
        "mixture_plus_transient": np.concatenate([mixture, transient], axis=1),
    }


def _fit_predict(
    x: np.ndarray,
    y: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    beta, *_ = np.linalg.lstsq(x[train], y[train], rcond=None)
    return x[train] @ beta, x[test] @ beta, beta


def _rmse(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - pred) ** 2)))


def _r2(y: np.ndarray, pred: np.ndarray) -> float:
    ss_res = float(np.sum((y - pred) ** 2))
    centered = y - np.mean(y, axis=0, keepdims=True)
    ss_tot = float(np.sum(centered * centered))
    if ss_tot <= 1e-12:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _bic(y: np.ndarray, pred: np.ndarray, parameters: int) -> float:
    residual = y - pred
    rss = max(float(np.sum(residual * residual)), 1e-12)
    n = y.size
    return float(n * np.log(rss / n) + parameters * np.log(n))


def compare_observation_models(
    trace: StateNetworkTrace,
    features: np.ndarray,
    *,
    n_states: int,
    executive_weight: float,
    transient_lags: int = 3,
    test_every: int = 5,
) -> list[ModelFit]:
    if len(features) != len(trace.executive):
        raise ValueError("feature rows must match trace length")

    train, test = _split_mask(len(features), test_every)
    designs = build_designs(
        trace,
        n_states=n_states,
        executive_weight=executive_weight,
        transient_lags=transient_lags,
    )

    fits: list[ModelFit] = []
    feature_count = features.shape[1]
    for name, x in designs.items():
        train_pred, test_pred, beta = _fit_predict(x, features, train, test)
        k = int(beta.size)
        fits.append(
            ModelFit(
                name=name,
                columns=x.shape[1],
                parameters=k,
                train_rmse=_rmse(features[train], train_pred),
                test_rmse=_rmse(features[test], test_pred),
                train_r2=_r2(features[train], train_pred),
                test_r2=_r2(features[test], test_pred),
                bic=_bic(features[train], train_pred, k),
            )
        )

    return sorted(fits, key=lambda fit: fit.test_rmse)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=int, default=4)
    p.add_argument("--steps", type=int, default=720)
    p.add_argument("--seed", type=int, default=83)
    p.add_argument("--transient-lags", type=int, default=3)
    p.add_argument("--test-every", type=int, default=5)
    p.add_argument("--meth", type=float, default=0.50)
    p.add_argument("--nmda", type=float, default=0.35)
    p.add_argument(
        "--output",
        default="runs/dissociation_model_comparison.json",
    )
    return p


def main() -> int:
    args = _parser().parse_args()
    inputs = MechanismInput(
        meth=args.meth,
        nmda_antagonism=args.nmda,
    )
    state_config = StateNetworkConfig(
        n_states=args.states,
        steps=args.steps,
        seed=args.seed,
        max_coconscious=min(3, args.states),
        sync_interval=max(24, args.steps // 5),
    )
    state_params = StateNetworkParameters()
    _, trace = simulate_state_network(
        inputs,
        config=state_config,
        params=state_params,
        return_trace=True,
    )

    obs_config = ObservationConfig(
        n_states=args.states,
        seed=args.seed + 100,
    )
    observations = simulate_observations(
        trace,
        inputs,
        config=obs_config,
    )

    fits = compare_observation_models(
        trace,
        observations.features,
        n_states=args.states,
        executive_weight=obs_config.executive_weight,
        transient_lags=args.transient_lags,
        test_every=args.test_every,
    )

    by_bic = sorted(fits, key=lambda fit: fit.bic)
    payload = {
        "schema_version": 1,
        "model": "synthetic_observation_model_comparison",
        "warning": (
            "Synthetic benchmark only. Model rankings describe data generated by "
            "this simulator and do not establish a clinical mechanism."
        ),
        "inputs": asdict(inputs),
        "state_config": asdict(state_config),
        "observation_config": asdict(obs_config),
        "feature_names": list(FEATURE_NAMES),
        "fits_by_test_rmse": [fit.to_dict() for fit in fits],
        "fits_by_bic": [fit.to_dict() for fit in by_bic],
        "best_test_rmse": fits[0].name,
        "best_bic": by_bic[0].name,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote model comparison to {out}")
    for fit in fits:
        print(
            f"{fit.name:24s} "
            f"k={fit.parameters:4d} "
            f"train_rmse={fit.train_rmse:.4f} "
            f"test_rmse={fit.test_rmse:.4f} "
            f"test_r2={fit.test_r2:+.3f} "
            f"BIC={fit.bic:+.1f}"
        )
    print(f"best_test_rmse={fits[0].name}")
    print(f"best_bic={by_bic[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
