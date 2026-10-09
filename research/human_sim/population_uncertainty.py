"""Empirical uncertainty summaries for imported HumanSim virtual populations.

This module quantifies:
1. empirical inter-individual variation present in the imported population;
2. sampling uncertainty of summary statistics via nonparametric bootstrap;
3. empirical correlations among reduced physiology variables.

It does NOT convert these intervals into biological/model uncertainty and does not
invent parameter distributions beyond the supplied virtual individuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from research.human_sim.population import VirtualIndividual


@dataclass(frozen=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    confidence: float
    resamples: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
            "resamples": self.resamples,
        }


def percentile_bootstrap_interval(
    values: Sequence[float],
    *,
    statistic: str = "median",
    confidence: float = 0.95,
    resamples: int = 1000,
    seed: int = 1,
) -> BootstrapInterval:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("bootstrap requires at least two one-dimensional values")
    if not np.all(np.isfinite(values)):
        raise ValueError("bootstrap values must be finite")
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be in (0.5,1)")
    if resamples < 50:
        raise ValueError("resamples must be >= 50")
    if statistic not in {"mean", "median"}:
        raise ValueError("statistic must be mean or median")

    fn = np.mean if statistic == "mean" else np.median
    estimate = float(fn(values))
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(resamples, len(values)), replace=True)
    estimates = fn(draws, axis=1)

    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(estimates, [alpha, 1.0 - alpha])
    return BootstrapInterval(
        estimate=estimate,
        lower=float(lower),
        upper=float(upper),
        confidence=confidence,
        resamples=resamples,
    )


def physiology_matrix(
    individuals: Sequence[VirtualIndividual],
) -> tuple[list[str], np.ndarray]:
    if len(individuals) < 2:
        raise ValueError("at least two virtual individuals are required")

    tissue_names = ("brain", "liver", "kidney", "peripheral")
    names = ["central_volume_l"]
    for tissue in tissue_names:
        names.extend([
            f"{tissue}_volume_l",
            f"{tissue}_flow_l_per_h",
        ])

    rows = []
    for individual in individuals:
        physiology = individual.physiology
        physiology.validate()
        row = [physiology.central_volume_l]
        for tissue in tissue_names:
            spec = physiology.tissue_map[tissue]
            row.extend([spec.volume_l, spec.blood_flow_l_per_h])
        rows.append(row)

    matrix = np.asarray(rows, dtype=float)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("physiology matrix contains non-finite values")
    return names, matrix


def correlation_report(
    individuals: Sequence[VirtualIndividual],
) -> dict:
    names, matrix = physiology_matrix(individuals)

    if len(individuals) < 3:
        return {
            "variables": names,
            "matrix": None,
            "status": "insufficient_n_for_correlation",
            "n": len(individuals),
        }

    sd = np.std(matrix, axis=0, ddof=1)
    variable = sd > 1e-12
    corr = np.full((len(names), len(names)), np.nan, dtype=float)
    if np.any(variable):
        sub = np.corrcoef(matrix[:, variable], rowvar=False)
        if np.ndim(sub) == 0:
            sub = np.asarray([[1.0]])
        indices = np.flatnonzero(variable)
        for i, src_i in enumerate(indices):
            for j, src_j in enumerate(indices):
                corr[src_i, src_j] = sub[i, j]

    return {
        "variables": names,
        "matrix": corr.tolist(),
        "status": "ok",
        "n": len(individuals),
        "zero_variance_variables": [
            names[index] for index, value in enumerate(variable) if not value
        ],
    }


def bootstrap_outcome_report(
    outcome_vectors: Mapping[str, Sequence[float]],
    *,
    confidence: float = 0.95,
    resamples: int = 1000,
    seed: int = 1,
) -> dict:
    result = {}
    for index, (name, values) in enumerate(sorted(outcome_vectors.items())):
        values = list(values)
        if len(values) < 2:
            result[name] = {
                "status": "insufficient_n",
                "n": len(values),
            }
            continue
        result[name] = {
            "status": "ok",
            "n": len(values),
            "median": percentile_bootstrap_interval(
                values,
                statistic="median",
                confidence=confidence,
                resamples=resamples,
                seed=seed + 101 * index,
            ).to_dict(),
            "mean": percentile_bootstrap_interval(
                values,
                statistic="mean",
                confidence=confidence,
                resamples=resamples,
                seed=seed + 101 * index + 1,
            ).to_dict(),
        }
    return result
