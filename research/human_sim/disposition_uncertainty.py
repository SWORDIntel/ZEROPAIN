"""Explicit uncertainty propagation for compound disposition inputs.

No default biological uncertainty is invented. All coefficients of variation (CVs)
default to zero and must be supplied by the caller/source.

Sampling families:
- bounded fractions in (0,1): beta distribution matched to mean/CV;
- strictly positive quantities: lognormal matched to mean/CV.

This propagates *input uncertainty* only. It is separate from virtual-human
inter-individual variability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import numpy as np

from research.human_sim.external_disposition import (
    DispositionBuildResult,
    ExternalDispositionInputs,
    build_external_disposition,
)
from research.human_sim.physiology import Physiology


@dataclass(frozen=True)
class DispositionUncertainty:
    partition_cv_by_tissue: Mapping[str, float] = field(default_factory=dict)
    fu_plasma_cv: float = 0.0
    fu_brain_cv: float = 0.0
    blood_to_plasma_cv: float = 0.0
    kp_uu_brain_cv: float = 0.0
    intrinsic_hepatic_clearance_cv: float = 0.0
    gfr_cv: float = 0.0

    def validate(self, tissue_names: set[str]) -> None:
        unknown = set(self.partition_cv_by_tissue) - tissue_names
        if unknown:
            raise ValueError(f"uncertainty for unknown tissues: {sorted(unknown)}")
        values = [
            *self.partition_cv_by_tissue.values(),
            self.fu_plasma_cv,
            self.fu_brain_cv,
            self.blood_to_plasma_cv,
            self.kp_uu_brain_cv,
            self.intrinsic_hepatic_clearance_cv,
            self.gfr_cv,
        ]
        if any(value < 0 for value in values):
            raise ValueError("uncertainty CVs cannot be negative")
        if any(value > 5 for value in values):
            raise ValueError("uncertainty CV > 5 is rejected as numerically unreasonable")


def _sample_positive(
    rng: np.random.Generator,
    mean: float,
    cv: float,
    n: int,
) -> np.ndarray:
    if mean <= 0:
        raise ValueError("positive sampler mean must be > 0")
    if cv == 0:
        return np.full(n, mean, dtype=float)
    sigma2 = np.log1p(cv * cv)
    sigma = np.sqrt(sigma2)
    mu = np.log(mean) - 0.5 * sigma2
    return rng.lognormal(mean=mu, sigma=sigma, size=n)


def _sample_fraction(
    rng: np.random.Generator,
    mean: float,
    cv: float,
    n: int,
) -> np.ndarray:
    if not 0.0 < mean <= 1.0:
        raise ValueError("fraction mean must be in (0,1]")
    if cv == 0:
        return np.full(n, mean, dtype=float)
    if mean >= 1.0:
        raise ValueError("nonzero uncertainty around fraction mean=1 is unsupported")

    variance = (mean * cv) ** 2
    maximum_variance = mean * (1.0 - mean)
    if variance >= maximum_variance:
        raise ValueError(
            "fraction mean/CV imply beta variance outside the feasible range"
        )

    concentration = mean * (1.0 - mean) / variance - 1.0
    alpha = mean * concentration
    beta = (1.0 - mean) * concentration
    return rng.beta(alpha, beta, size=n)


def sample_external_dispositions(
    physiology: Physiology,
    base: ExternalDispositionInputs,
    uncertainty: DispositionUncertainty,
    *,
    samples: int = 1000,
    seed: int = 1,
) -> list[DispositionBuildResult]:
    if samples < 1:
        raise ValueError("samples must be positive")
    physiology.validate()
    base.validate()
    tissue_names = set(physiology.tissue_map)
    uncertainty.validate(tissue_names)

    rng = np.random.default_rng(seed)

    partition_draws = {
        tissue: _sample_positive(
            rng,
            float(value),
            float(uncertainty.partition_cv_by_tissue.get(tissue, 0.0)),
            samples,
        )
        for tissue, value in base.tissue_partition_coefficients.items()
    }
    fu_plasma = _sample_fraction(
        rng, base.fu_plasma, uncertainty.fu_plasma_cv, samples
    )
    fu_brain = _sample_fraction(
        rng, base.fu_brain, uncertainty.fu_brain_cv, samples
    )
    blood_to_plasma = _sample_positive(
        rng,
        base.blood_to_plasma_ratio,
        uncertainty.blood_to_plasma_cv,
        samples,
    )

    kp_uu = (
        _sample_positive(
            rng,
            base.kp_uu_brain,
            uncertainty.kp_uu_brain_cv,
            samples,
        )
        if base.kp_uu_brain is not None
        else None
    )
    clint = (
        _sample_positive(
            rng,
            base.intrinsic_hepatic_clearance_l_per_h,
            uncertainty.intrinsic_hepatic_clearance_cv,
            samples,
        )
        if base.intrinsic_hepatic_clearance_l_per_h is not None
        else None
    )
    gfr = (
        _sample_positive(
            rng,
            base.gfr_l_per_h,
            uncertainty.gfr_cv,
            samples,
        )
        if base.gfr_l_per_h is not None
        else None
    )

    results = []
    for index in range(samples):
        draw = replace(
            base,
            tissue_partition_coefficients={
                tissue: float(values[index])
                for tissue, values in partition_draws.items()
            },
            fu_plasma=float(fu_plasma[index]),
            fu_brain=float(fu_brain[index]),
            blood_to_plasma_ratio=float(blood_to_plasma[index]),
            kp_uu_brain=None if kp_uu is None else float(kp_uu[index]),
            intrinsic_hepatic_clearance_l_per_h=(
                None if clint is None else float(clint[index])
            ),
            gfr_l_per_h=None if gfr is None else float(gfr[index]),
        )
        results.append(build_external_disposition(physiology, draw))
    return results


def summarize_disposition_samples(
    results: list[DispositionBuildResult],
) -> dict:
    if not results:
        raise ValueError("results cannot be empty")

    tissues = sorted(results[0].disposition.tissue_partition_coefficients)

    def stats(values) -> dict[str, float]:
        array = np.asarray(values, dtype=float)
        return {
            "mean": float(np.mean(array)),
            "sd": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
            "q05": float(np.quantile(array, 0.05)),
            "q50": float(np.quantile(array, 0.50)),
            "q95": float(np.quantile(array, 0.95)),
        }

    payload = {
        "samples": len(results),
        "partition_coefficients": {
            tissue: stats([
                result.disposition.tissue_partition_coefficients[tissue]
                for result in results
            ])
            for tissue in tissues
        },
    }

    hepatic = [
        result.diagnostics["well_stirred_hepatic_reference"]
        for result in results
    ]
    if all(item is not None for item in hepatic):
        payload["well_stirred_hepatic_clearance_l_per_h"] = stats(
            [item["clearance_l_per_h"] for item in hepatic]
        )

    renal = [
        result.diagnostics["filtration_only_renal_reference"]
        for result in results
    ]
    if all(item is not None for item in renal):
        payload["filtration_only_renal_clearance_l_per_h"] = stats(
            [item["clearance_l_per_h"] for item in renal]
        )

    return payload
