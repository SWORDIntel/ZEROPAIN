"""Discrete identity-state graph toy model.

This is a synthetic research model for state-transition and information-sharing
hypotheses. It is not a clinical model of DID and has no human dose mapping.

Compared with the scalar state-gating model, this layer explicitly represents:
- multiple identity states;
- one executive state at a time;
- state-specific fatigue and recovery;
- executive hand-off;
- state-specific access propensity;
- event-memory accessibility;
- gradual cross-state information sharing;
- periodic waking/synchronization events that can be disrupted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

import numpy as np

from research.dissociation.model import MechanismInput


def _sigmoid_scalar(x: float) -> float:
    x = max(-40.0, min(40.0, x))
    return 1.0 / (1.0 + np.exp(-x))


def _clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


@dataclass(frozen=True)
class StateGraphConfig:
    n_states: int = 4
    steps: int = 480
    seed: int = 13
    sync_interval: int = 96


@dataclass(frozen=True)
class StateGraphParameters:
    # State fatigue / recovery.
    fatigue_rate: float = 0.018
    recovery_rate: float = 0.010
    meth_fatigue_multiplier: float = 0.45

    # Switching.
    switch_intercept: float = -2.35
    fatigue_switch_weight: float = 1.25
    meth_switch_weight: float = 1.20
    nmda_switch_weight: float = 0.70
    mor_partial_switch_weight: float = -0.35
    kor_agonist_switch_weight: float = 0.55
    kor_antagonist_switch_weight: float = -0.30
    nop_agonist_switch_weight: float = 0.00
    nop_antagonist_switch_weight: float = 0.00

    # Information permeability.
    base_memory_permeability: float = 0.055
    meth_memory_penalty: float = 0.45
    nmda_memory_penalty: float = 0.55
    mor_partial_memory_bonus: float = 0.08
    kor_agonist_memory_penalty: float = 0.18
    kor_antagonist_memory_bonus: float = 0.10
    nop_agonist_memory_bonus: float = 0.00
    nop_antagonist_memory_bonus: float = 0.00

    # Periodic synchronization event.
    sync_boost: float = 0.55

    # Transition target choice.
    meth_choice_entropy: float = 0.35


@dataclass
class StateGraphSummary:
    switches: int
    switch_rate: float
    unique_executive_states: int
    normalized_occupancy_entropy: float
    low_energy_handoffs: int
    mean_executive_energy: float
    memory_divergence: float
    memory_consistency: float
    synchronization_events_expected: int
    synchronization_events_completed: int
    synchronization_completion_rate: float

    def to_dict(self) -> Dict[str, float | int]:
        return asdict(self)


def _memory_permeability(
    inputs: MechanismInput,
    params: StateGraphParameters,
) -> float:
    value = params.base_memory_permeability
    value *= 1.0 - params.meth_memory_penalty * inputs.meth
    value *= 1.0 - params.nmda_memory_penalty * inputs.nmda_antagonism
    value *= 1.0 - params.kor_agonist_memory_penalty * inputs.kor_agonism
    value += params.mor_partial_memory_bonus * inputs.mor_partial_agonism
    value += params.kor_antagonist_memory_bonus * inputs.kor_antagonism
    value += params.nop_agonist_memory_bonus * inputs.nop_agonism
    value += params.nop_antagonist_memory_bonus * inputs.nop_antagonism
    return _clamp01(value)


def _switch_probability(
    current_energy: float,
    inputs: MechanismInput,
    params: StateGraphParameters,
) -> float:
    logit = (
        params.switch_intercept
        + params.fatigue_switch_weight * (1.0 - current_energy)
        + params.meth_switch_weight * inputs.meth
        + params.nmda_switch_weight * inputs.nmda_antagonism
        + params.mor_partial_switch_weight * inputs.mor_partial_agonism
        + params.kor_agonist_switch_weight * inputs.kor_agonism
        + params.kor_antagonist_switch_weight * inputs.kor_antagonism
        + params.nop_agonist_switch_weight * inputs.nop_agonism
        + params.nop_antagonist_switch_weight * inputs.nop_antagonism
    )
    return float(_sigmoid_scalar(logit))


def _choose_next_state(
    current: int,
    energy: np.ndarray,
    access_bias: np.ndarray,
    inputs: MechanismInput,
    params: StateGraphParameters,
    rng: np.random.Generator,
) -> int:
    candidates = np.arange(len(energy))
    mask = candidates != current
    candidates = candidates[mask]

    weights = energy[candidates] * access_bias[candidates]
    uniform = np.ones_like(weights)
    entropy_mix = _clamp01(params.meth_choice_entropy * inputs.meth)
    weights = (1.0 - entropy_mix) * weights + entropy_mix * uniform

    total = float(np.sum(weights))
    if total <= 0.0:
        return int(rng.choice(candidates))
    probabilities = weights / total
    return int(rng.choice(candidates, p=probabilities))


def simulate_state_graph(
    inputs: MechanismInput,
    *,
    config: StateGraphConfig = StateGraphConfig(),
    params: StateGraphParameters = StateGraphParameters(),
) -> StateGraphSummary:
    inputs.validate()
    if config.n_states < 2:
        raise ValueError("n_states must be >= 2")
    if config.steps <= 0:
        raise ValueError("steps must be > 0")
    if config.sync_interval <= 0:
        raise ValueError("sync_interval must be > 0")

    rng = np.random.default_rng(config.seed)
    n = config.n_states

    energy = rng.uniform(0.72, 0.96, size=n)
    access_bias = rng.lognormal(mean=0.0, sigma=0.20, size=n)
    access_bias /= float(np.mean(access_bias))

    executive = int(np.argmax(access_bias))
    occupancy = np.zeros(n, dtype=np.int32)
    executive_energy_sum = 0.0
    switches = 0
    low_energy_handoffs = 0

    # Rows = states, columns = event memories. Values in [0, 1] represent
    # accessibility, not literal memory strength.
    knowledge = np.zeros((n, config.steps), dtype=np.float64)

    expected_syncs = config.steps // config.sync_interval
    completed_syncs = 0
    permeability = _memory_permeability(inputs, params)

    for step in range(config.steps):
        occupancy[executive] += 1
        executive_energy_sum += float(energy[executive])

        # A new event is initially fully accessible to the executive state.
        knowledge[executive, step] = 1.0

        # Existing information diffuses toward all states according to permeability.
        if step > 0 and permeability > 0.0:
            shared = np.max(knowledge[:, : step + 1], axis=0)
            knowledge[:, : step + 1] += permeability * (
                shared[None, :] - knowledge[:, : step + 1]
            )

        # Abstract waking/synchronization event.
        if (step + 1) % config.sync_interval == 0:
            disrupted = rng.random() < inputs.wake_anchor_disruption
            if not disrupted:
                completed_syncs += 1
                shared = np.max(knowledge[:, : step + 1], axis=0)
                knowledge[:, : step + 1] += params.sync_boost * (
                    shared[None, :] - knowledge[:, : step + 1]
                )

        # Fatigue current executive state, recover non-executive states.
        fatigue = params.fatigue_rate * (
            1.0 + params.meth_fatigue_multiplier * inputs.meth
        )
        energy[executive] = max(0.0, energy[executive] - fatigue)
        for state in range(n):
            if state != executive:
                energy[state] = min(1.0, energy[state] + params.recovery_rate)

        p_switch = _switch_probability(float(energy[executive]), inputs, params)
        if rng.random() < p_switch:
            if energy[executive] < 0.35:
                low_energy_handoffs += 1
            executive = _choose_next_state(
                executive,
                energy,
                access_bias,
                inputs,
                params,
                rng,
            )
            switches += 1

    occupied = occupancy > 0
    unique_states = int(np.sum(occupied))
    probs = occupancy[occupied].astype(float) / float(np.sum(occupancy))
    entropy = -float(np.sum(probs * np.log(probs)))
    max_entropy = float(np.log(n))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    event_range = np.max(knowledge, axis=0) - np.min(knowledge, axis=0)
    memory_divergence = float(np.mean(event_range))
    memory_consistency = 1.0 - memory_divergence

    sync_rate = (
        completed_syncs / expected_syncs
        if expected_syncs > 0
        else 1.0
    )

    return StateGraphSummary(
        switches=switches,
        switch_rate=switches / config.steps,
        unique_executive_states=unique_states,
        normalized_occupancy_entropy=normalized_entropy,
        low_energy_handoffs=low_energy_handoffs,
        mean_executive_energy=executive_energy_sum / config.steps,
        memory_divergence=memory_divergence,
        memory_consistency=memory_consistency,
        synchronization_events_expected=expected_syncs,
        synchronization_events_completed=completed_syncs,
        synchronization_completion_rate=sync_rate,
    )
