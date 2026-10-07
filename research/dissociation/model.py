"""Mechanistic toy model for dissociative-state stability research.

This model is intentionally dimensionless. It is not a PK/PD model, does not map
parameters to human doses, and must not be interpreted as a treatment recommendation.

Purpose:
- separate methamphetamine-associated destabilization from wake-anchor disruption;
- perturb NMDA-dependent integration independently;
- explore MOR partial-agonist, KOR, and NOP hypotheses without assuming benefit;
- generate falsifiable state-transition outputs for later model comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import exp
from typing import Dict, Iterable

import numpy as np


def _clamp(x: np.ndarray | float, lo: float = 0.0, hi: float = 1.0):
    return np.clip(x, lo, hi)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


@dataclass(frozen=True)
class MechanismInput:
    """Dimensionless perturbation strengths, each in [0, 1].

    NOP direction is deliberately split into agonist/antagonist terms because the
    relevant direction for state stability is not assumed.
    """

    meth: float = 0.0
    nmda_antagonism: float = 0.0
    mor_partial_agonism: float = 0.0
    kor_agonism: float = 0.0
    kor_antagonism: float = 0.0
    nop_agonism: float = 0.0
    nop_antagonism: float = 0.0
    wake_anchor_disruption: float = 0.0

    def validate(self) -> None:
        for key, value in asdict(self).items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{key} must be in [0, 1], got {value!r}")


@dataclass(frozen=True)
class ModelParameters:
    """Hypothesis coefficients.

    Signs are explicit assumptions, not facts. Sensitivity analysis should vary them.
    """

    # Direct destabilizing inputs.
    meth_salience_weight: float = 1.15
    meth_control_weight: float = 0.80
    meth_integration_weight: float = 0.35
    nmda_integration_weight: float = 1.10
    nmda_control_weight: float = 0.45
    wake_coordination_weight: float = 1.05

    # Opioid-system hypotheses.
    mor_partial_control_weight: float = 0.35
    mor_partial_integration_weight: float = 0.15
    kor_agonist_control_weight: float = 0.45
    kor_agonist_integration_weight: float = 0.30
    kor_antagonist_control_weight: float = 0.30
    kor_antagonist_integration_weight: float = 0.20

    # NOP direction remains intentionally uncertain.
    nop_agonist_control_weight: float = 0.10
    nop_antagonist_control_weight: float = 0.00

    # State-transition equation.
    switch_intercept: float = -2.00
    switch_vulnerability_weight: float = 1.15
    switch_low_control_weight: float = 2.20
    switch_low_integration_weight: float = 1.75
    switch_salience_weight: float = 1.00
    switch_low_coordination_weight: float = 0.80

    # Dynamics / noise.
    inertia: float = 0.82
    process_noise: float = 0.035


@dataclass(frozen=True)
class PopulationConfig:
    n_subjects: int = 10_000
    steps: int = 240
    seed: int = 1


@dataclass
class SimulationSummary:
    mean_switches: float
    median_switches: float
    mean_switch_probability: float
    mean_persistence_steps: float
    executive_stability: float
    cortical_integration: float
    internal_coordination: float
    information_consistency: float
    salience_load: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class _Population:
    vulnerability: np.ndarray
    base_control: np.ndarray
    base_integration: np.ndarray
    base_coordination: np.ndarray


def make_population(config: PopulationConfig) -> _Population:
    rng = np.random.default_rng(config.seed)
    n = config.n_subjects

    # Wide but bounded heterogeneity. These are synthetic latent variables.
    vulnerability = _clamp(rng.beta(2.2, 2.5, n))
    base_control = _clamp(rng.normal(0.72, 0.10, n))
    base_integration = _clamp(rng.normal(0.76, 0.09, n))
    base_coordination = _clamp(rng.normal(0.74, 0.12, n))

    return _Population(
        vulnerability=vulnerability,
        base_control=base_control,
        base_integration=base_integration,
        base_coordination=base_coordination,
    )


def simulate(
    inputs: MechanismInput,
    *,
    config: PopulationConfig = PopulationConfig(),
    params: ModelParameters = ModelParameters(),
) -> SimulationSummary:
    """Run the synthetic state-gating model for one perturbation condition."""

    inputs.validate()
    pop = make_population(config)
    rng = np.random.default_rng(config.seed + 97)

    control = pop.base_control.copy()
    integration = pop.base_integration.copy()
    coordination = pop.base_coordination.copy()
    salience = np.full(config.n_subjects, 0.20, dtype=float)

    switch_counts = np.zeros(config.n_subjects, dtype=np.int32)
    switch_prob_acc = 0.0
    control_acc = 0.0
    integration_acc = 0.0
    coordination_acc = 0.0
    consistency_acc = 0.0
    salience_acc = 0.0

    # Static target levels induced by the condition.
    target_control = _clamp(
        pop.base_control
        - params.meth_control_weight * inputs.meth
        - params.nmda_control_weight * inputs.nmda_antagonism
        - params.kor_agonist_control_weight * inputs.kor_agonism
        + params.kor_antagonist_control_weight * inputs.kor_antagonism
        + params.mor_partial_control_weight * inputs.mor_partial_agonism
        + params.nop_agonist_control_weight * inputs.nop_agonism
        + params.nop_antagonist_control_weight * inputs.nop_antagonism
    )

    target_integration = _clamp(
        pop.base_integration
        - params.meth_integration_weight * inputs.meth
        - params.nmda_integration_weight * inputs.nmda_antagonism
        - params.kor_agonist_integration_weight * inputs.kor_agonism
        + params.kor_antagonist_integration_weight * inputs.kor_antagonism
        + params.mor_partial_integration_weight * inputs.mor_partial_agonism
    )

    target_coordination = _clamp(
        pop.base_coordination
        - params.wake_coordination_weight * inputs.wake_anchor_disruption
        - 0.15 * inputs.meth
    )

    target_salience = _clamp(
        0.20
        + params.meth_salience_weight * inputs.meth
        + 0.20 * inputs.nmda_antagonism
        + 0.15 * inputs.kor_agonism
        - 0.10 * inputs.kor_antagonism
    )

    inertia = params.inertia
    noise_scale = params.process_noise

    for _ in range(config.steps):
        control = _clamp(
            inertia * control
            + (1.0 - inertia) * target_control
            + rng.normal(0.0, noise_scale, config.n_subjects)
        )
        integration = _clamp(
            inertia * integration
            + (1.0 - inertia) * target_integration
            + rng.normal(0.0, noise_scale, config.n_subjects)
        )
        coordination = _clamp(
            inertia * coordination
            + (1.0 - inertia) * target_coordination
            + rng.normal(0.0, noise_scale, config.n_subjects)
        )
        salience = _clamp(
            inertia * salience
            + (1.0 - inertia) * target_salience
            + rng.normal(0.0, noise_scale, config.n_subjects)
        )

        linear = (
            params.switch_intercept
            + params.switch_vulnerability_weight * pop.vulnerability
            + params.switch_low_control_weight * (1.0 - control)
            + params.switch_low_integration_weight * (1.0 - integration)
            + params.switch_salience_weight * salience
            + params.switch_low_coordination_weight * (1.0 - coordination)
        )
        p_switch = _sigmoid(linear)
        switched = rng.random(config.n_subjects) < p_switch
        switch_counts += switched

        # Information consistency falls when integration and coordination are both low.
        consistency = _clamp(
            0.55 * integration
            + 0.45 * coordination
            - 0.12 * switched.astype(float)
        )

        switch_prob_acc += float(np.mean(p_switch))
        control_acc += float(np.mean(control))
        integration_acc += float(np.mean(integration))
        coordination_acc += float(np.mean(coordination))
        consistency_acc += float(np.mean(consistency))
        salience_acc += float(np.mean(salience))

    mean_p_switch = switch_prob_acc / config.steps
    mean_persistence = float("inf") if mean_p_switch <= 0 else 1.0 / mean_p_switch

    return SimulationSummary(
        mean_switches=float(np.mean(switch_counts)),
        median_switches=float(np.median(switch_counts)),
        mean_switch_probability=mean_p_switch,
        mean_persistence_steps=mean_persistence,
        executive_stability=control_acc / config.steps,
        cortical_integration=integration_acc / config.steps,
        internal_coordination=coordination_acc / config.steps,
        information_consistency=consistency_acc / config.steps,
        salience_load=salience_acc / config.steps,
    )


def compare_conditions(
    conditions: Dict[str, MechanismInput],
    *,
    config: PopulationConfig = PopulationConfig(),
    params: ModelParameters = ModelParameters(),
) -> Dict[str, SimulationSummary]:
    """Run multiple conditions using the same synthetic population seed."""

    return {
        name: simulate(inputs, config=config, params=params)
        for name, inputs in conditions.items()
    }
