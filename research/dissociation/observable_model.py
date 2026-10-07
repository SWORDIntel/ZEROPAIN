"""Synthetic measurement adapter: simulator latents -> observable *proxies*.

IMPORTANT: No output channel is a clinical biomarker. In particular, the EEG and
wearable channels are fabricated summary-level proxies, not actual waveform features
and not validated signatures of dissociative pathology. They are included only to
test whether a blind measurement interface preserves *synthetic* identifiability.

The selection/fitting code receives *only these measurements*. It cannot read the
state simulator's hidden integration/control/salience/coordination metrics directly.

All inputs remain dimensionless. This module does not map to doses or interventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from research.dissociation.model import SimulationSummary


ALL_CHANNELS = (
    "observer_switch_rate",
    "paired_recall_success",
    "morning_plan_agreement",
    "wearable_arousal_index",
    "eeg_connectivity_index",
)

PANELS: dict[str, tuple[str, ...]] = {
    "switch_only": ("observer_switch_rate",),
    "observer_only": ALL_CHANNELS[:3],
    "observer_wearable": ALL_CHANNELS[:4],
    "multimodal": ALL_CHANNELS,
}

# Chosen uncertainty floors are synthetic study-design assumptions, not estimates
# from a cohort. Keeping them fixed prevents a condition subset from renormalizing
# away information it has lost.
UNCERTAINTY = {
    "observer_switch_rate": 0.035,
    "paired_recall_success": 0.055,
    "morning_plan_agreement": 0.065,
    "wearable_arousal_index": 0.12,
    "eeg_connectivity_index": 0.16,
}


@dataclass(frozen=True)
class MeasurementConfig:
    switch_sensitivity: float = 0.74
    switch_false_positive_rate: float = 0.025
    recall_trials: int = 100
    plan_trials: int = 60
    switch_checks: int = 250
    wearable_noise_sd: float = 0.12
    eeg_noise_sd: float = 0.16
    missing_probability: float = 0.10

    def validate(self) -> None:
        for name in (
            "switch_sensitivity", "switch_false_positive_rate", "missing_probability"
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0,1]")
        for name in ("recall_trials", "plan_trials", "switch_checks"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.wearable_noise_sd < 0 or self.eeg_noise_sd < 0:
            raise ValueError("sensor noise cannot be negative")


def _unit(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def expected_observables(
    summary: SimulationSummary,
    config: MeasurementConfig = MeasurementConfig(),
) -> dict[str, float]:
    """Return *model-expected readouts* of a hypothetical measurement process.

    These are not actual observations and are not identical to any hidden variable.
    They intentionally conflate multiple mechanisms, as real channels usually do.
    """
    config.validate()
    switch = _unit(summary.mean_switch_probability)
    return {
        "observer_switch_rate": _unit(
            config.switch_sensitivity * switch
            + config.switch_false_positive_rate * (1.0 - switch)
        ),
        "paired_recall_success": _unit(
            0.10 + 0.77 * summary.information_consistency
            - 0.13 * switch
        ),
        "morning_plan_agreement": _unit(
            0.08
            + 0.65 * summary.internal_coordination
            + 0.15 * summary.information_consistency
            - 0.08 * switch
        ),
        "wearable_arousal_index": (
            0.75 * summary.salience_load
            + 0.30 * (1.0 - summary.executive_stability)
            - 0.30
        ),
        "eeg_connectivity_index": (
            0.75 * summary.cortical_integration
            + 0.14 * summary.executive_stability
            - 0.18 * summary.salience_load
            - 0.42
        ),
    }


def select_channels(
    measurements: Mapping[str, float],
    panel: str | Sequence[str],
) -> np.ndarray:
    channels = PANELS[panel] if isinstance(panel, str) else tuple(panel)
    if not channels or any(name not in ALL_CHANNELS for name in channels):
        raise ValueError(f"invalid measurement panel: {panel}")
    return np.asarray([measurements[name] for name in channels], dtype=float)


def uncertainty_for(panel: str | Sequence[str]) -> np.ndarray:
    channels = PANELS[panel] if isinstance(panel, str) else tuple(panel)
    return np.asarray([UNCERTAINTY[name] for name in channels], dtype=float)


def sample_observables(
    summary: SimulationSummary,
    rng: np.random.Generator,
    *,
    config: MeasurementConfig = MeasurementConfig(),
) -> dict[str, float]:
    """Generate noisy reports, finite trials, and non-informative missingness.

    Missingness is independent of the physiological state in this first version.
    This is optimistic; informative missingness is future research.
    """
    config.validate()
    mu = expected_observables(summary, config)
    sample = {
        "observer_switch_rate": rng.binomial(
            config.switch_checks, mu["observer_switch_rate"]
        ) / config.switch_checks,
        "paired_recall_success": rng.binomial(
            config.recall_trials, mu["paired_recall_success"]
        ) / config.recall_trials,
        "morning_plan_agreement": rng.binomial(
            config.plan_trials, mu["morning_plan_agreement"]
        ) / config.plan_trials,
        "wearable_arousal_index": rng.normal(
            mu["wearable_arousal_index"], config.wearable_noise_sd
        ),
        "eeg_connectivity_index": rng.normal(
            mu["eeg_connectivity_index"], config.eeg_noise_sd
        ),
    }
    for channel in ALL_CHANNELS:
        if rng.random() < config.missing_probability:
            sample[channel] = float("nan")
    return sample
