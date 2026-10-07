"""Synthetic physiological observation model for dissociative-state simulations.

This module converts latent state-network traces into standardized observation features.
It is intended to test analysis pipelines for:
- state-specific physiological clusters;
- co-conscious/blended observations as mixtures;
- brief switch transients;
- robustness of state classification under common-mode perturbation and noise.

Feature values are arbitrary standardized units. They are NOT clinical EEG/HR values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Sequence

import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.state_network import StateNetworkTrace


FEATURE_NAMES = (
    "autonomic_rate_z",
    "autonomic_variability_z",
    "eeg_delta_z",
    "eeg_theta_z",
    "eeg_alpha_z",
    "eeg_beta_z",
    "eeg_gamma_z",
)


@dataclass(frozen=True)
class ObservationConfig:
    n_states: int = 4
    seed: int = 53
    state_separation: float = 0.90
    base_noise_sd: float = 0.22
    executive_weight: float = 0.72
    switch_transient_amplitude: float = 0.85
    switch_transient_decay: float = 0.45
    meth_noise_multiplier: float = 0.55
    nmda_noise_multiplier: float = 0.35
    perturbation_shift_scale: float = 0.30


@dataclass
class ObservationSummary:
    steps: int
    feature_count: int
    pure_state_steps: int
    blended_steps: int
    nearest_signature_accuracy_pure: float
    between_state_separation: float
    within_state_variance: float
    blend_reconstruction_rmse: float
    switch_transient_mean_norm: float
    nonswitch_mean_residual_norm: float

    def to_dict(self) -> Dict[str, float | int]:
        return asdict(self)


@dataclass
class ObservationResult:
    features: np.ndarray
    state_signatures: np.ndarray
    expected_mixture: np.ndarray
    transient_component: np.ndarray
    summary: ObservationSummary


def _make_state_signatures(config: ObservationConfig) -> np.ndarray:
    rng = np.random.default_rng(config.seed)
    raw = rng.normal(0.0, 1.0, size=(config.n_states, len(FEATURE_NAMES)))
    raw -= np.mean(raw, axis=0, keepdims=True)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return config.state_separation * raw / norms


def _mixture_weights(
    active_states: Sequence[int],
    executive: int,
    n_states: int,
    executive_weight: float,
) -> np.ndarray:
    weights = np.zeros(n_states, dtype=float)
    unique = tuple(dict.fromkeys(active_states))
    if executive not in unique:
        unique = (executive, *unique)

    if len(unique) == 1:
        weights[executive] = 1.0
        return weights

    exec_weight = float(np.clip(executive_weight, 0.0, 1.0))
    weights[executive] = exec_weight
    others = [state for state in unique if state != executive]
    remainder = 1.0 - exec_weight
    for state in others:
        weights[state] = remainder / len(others)
    return weights


def _pairwise_signature_separation(signatures: np.ndarray) -> float:
    distances = []
    for i in range(len(signatures)):
        for j in range(i + 1, len(signatures)):
            distances.append(float(np.linalg.norm(signatures[i] - signatures[j])))
    return float(np.mean(distances)) if distances else 0.0


def _nearest_signature_accuracy(
    features: np.ndarray,
    executive: Sequence[int],
    coconscious: Sequence[Sequence[int]],
    signatures: np.ndarray,
) -> tuple[float, int]:
    correct = 0
    total = 0
    for idx, (obs, state, active) in enumerate(zip(features, executive, coconscious)):
        unique = tuple(dict.fromkeys(active))
        if len(unique) != 1:
            continue
        distances = np.linalg.norm(signatures - obs[None, :], axis=1)
        predicted = int(np.argmin(distances))
        correct += int(predicted == state)
        total += 1
    return (correct / total if total else 0.0), total


def simulate_observations(
    trace: StateNetworkTrace,
    inputs: MechanismInput,
    *,
    config: ObservationConfig = ObservationConfig(),
) -> ObservationResult:
    inputs.validate()
    if config.n_states < 2:
        raise ValueError("n_states must be >= 2")
    steps = len(trace.executive)
    if len(trace.coconscious) != steps:
        raise ValueError("executive and coconscious traces must have equal length")

    rng = np.random.default_rng(config.seed + 1)
    signatures = _make_state_signatures(config)
    expected = np.zeros((steps, len(FEATURE_NAMES)), dtype=float)
    transient = np.zeros_like(expected)
    features = np.zeros_like(expected)

    # Arbitrary standardized common-mode perturbation axis. It exists to test
    # confounding, not to assert a clinical methamphetamine EEG signature.
    perturbation_axis = np.array([1.0, -0.7, -0.2, 0.1, -0.3, 0.6, 0.5], dtype=float)
    perturbation_axis /= np.linalg.norm(perturbation_axis)

    noise_sd = config.base_noise_sd * (
        1.0
        + config.meth_noise_multiplier * inputs.meth
        + config.nmda_noise_multiplier * inputs.nmda_antagonism
    )
    common_shift = (
        config.perturbation_shift_scale
        * (inputs.meth + 0.5 * inputs.nmda_antagonism)
        * perturbation_axis
    )

    transient_state = np.zeros(len(FEATURE_NAMES), dtype=float)
    previous_exec = trace.executive[0] if steps else 0

    for step in range(steps):
        executive = trace.executive[step]
        active = trace.coconscious[step]
        weights = _mixture_weights(
            active,
            executive,
            config.n_states,
            config.executive_weight,
        )
        expected[step] = weights @ signatures

        switched = step > 0 and executive != previous_exec
        if switched:
            direction = signatures[executive] - signatures[previous_exec]
            norm = np.linalg.norm(direction)
            if norm > 0:
                direction = direction / norm
            transient_state = config.switch_transient_amplitude * direction
        else:
            transient_state *= config.switch_transient_decay

        transient[step] = transient_state
        features[step] = (
            expected[step]
            + transient_state
            + common_shift
            + rng.normal(0.0, noise_sd, len(FEATURE_NAMES))
        )
        previous_exec = executive

    accuracy, pure_steps = _nearest_signature_accuracy(
        features,
        trace.executive,
        trace.coconscious,
        signatures,
    )

    residual = features - expected - common_shift
    blended_mask = np.array(
        [len(tuple(dict.fromkeys(active))) > 1 for active in trace.coconscious],
        dtype=bool,
    )
    if np.any(blended_mask):
        blend_rmse = float(
            np.sqrt(np.mean((features[blended_mask] - expected[blended_mask] - common_shift) ** 2))
        )
    else:
        blend_rmse = 0.0

    pure_by_state = []
    for state in range(config.n_states):
        rows = [
            idx
            for idx, (exec_state, active) in enumerate(
                zip(trace.executive, trace.coconscious)
            )
            if exec_state == state and len(tuple(dict.fromkeys(active))) == 1
        ]
        if rows:
            arr = features[rows]
            centroid = np.mean(arr, axis=0)
            pure_by_state.extend(np.sum((arr - centroid) ** 2, axis=1).tolist())
    within_variance = float(np.mean(pure_by_state)) if pure_by_state else 0.0

    switched_mask = np.zeros(steps, dtype=bool)
    if steps > 1:
        switched_mask[1:] = np.array(trace.executive[1:]) != np.array(trace.executive[:-1])
    residual_norm = np.linalg.norm(residual, axis=1) if steps else np.array([], dtype=float)
    switch_norm = float(np.mean(residual_norm[switched_mask])) if np.any(switched_mask) else 0.0
    nonswitch_norm = (
        float(np.mean(residual_norm[~switched_mask]))
        if steps and np.any(~switched_mask)
        else 0.0
    )

    summary = ObservationSummary(
        steps=steps,
        feature_count=len(FEATURE_NAMES),
        pure_state_steps=pure_steps,
        blended_steps=int(np.sum(blended_mask)),
        nearest_signature_accuracy_pure=accuracy,
        between_state_separation=_pairwise_signature_separation(signatures),
        within_state_variance=within_variance,
        blend_reconstruction_rmse=blend_rmse,
        switch_transient_mean_norm=switch_norm,
        nonswitch_mean_residual_norm=nonswitch_norm,
    )
    return ObservationResult(
        features=features,
        state_signatures=signatures,
        expected_mixture=expected,
        transient_component=transient,
        summary=summary,
    )
