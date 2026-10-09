"""State-specific memory/trust network with co-conscious occupancy and event timeline.

Research-only synthetic model. This is not a mechanistic claim about DID, a clinical
model, or a dosing system.

The purpose is to represent observations that the simpler state-graph model cannot:
- more than one state can be concurrently conscious/accessible;
- state-specific knowledge can diverge;
- information sharing depends on pairwise trust/permeability;
- repeated missed synchronization events can degrade internal coordination;
- withholding can emerge from low trust without being hard-coded as a moral trait;
- executive control can hand off as the active state fatigues;
- meth/NMDA/opioid-system hypotheses can modify these processes independently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, Iterable, Sequence

import numpy as np

from research.dissociation.model import MechanismInput


def _clamp01(x):
    return np.clip(x, 0.0, 1.0)


class EventKind(str, Enum):
    EXTERNAL = "external"
    STRESS = "stress"
    SYNC = "sync"
    WAKE = "wake"


@dataclass(frozen=True)
class TimelineEvent:
    step: int
    kind: EventKind
    intensity: float = 1.0
    label: str = ""

    def validate(self, steps: int) -> None:
        if not 0 <= self.step < steps:
            raise ValueError(f"event step {self.step} outside [0, {steps})")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("event intensity must be in [0, 1]")


@dataclass(frozen=True)
class StateNetworkConfig:
    n_states: int = 4
    steps: int = 480
    seed: int = 23
    max_coconscious: int = 2
    event_rate: float = 0.06
    sync_interval: int = 96


@dataclass(frozen=True)
class StateNetworkParameters:
    # Executive energy dynamics.
    fatigue_rate: float = 0.016
    recovery_rate: float = 0.010
    meth_fatigue_multiplier: float = 0.45

    # Executive switching.
    switch_intercept: float = -2.45
    fatigue_switch_weight: float = 1.35
    stress_switch_weight: float = 0.65
    meth_switch_weight: float = 1.15
    nmda_switch_weight: float = 0.65
    mor_partial_switch_weight: float = -0.30
    kor_agonist_switch_weight: float = 0.50
    kor_antagonist_switch_weight: float = -0.28
    nop_agonist_switch_weight: float = 0.0
    nop_antagonist_switch_weight: float = 0.0

    # Co-consciousness.
    coconscious_base: float = 0.18
    coconscious_trust_weight: float = 0.45
    coconscious_nmda_penalty: float = 0.22
    coconscious_meth_penalty: float = 0.12

    # Memory propagation.
    memory_share_rate: float = 0.12
    nmda_memory_penalty: float = 0.50
    meth_memory_penalty: float = 0.30
    mor_partial_memory_bonus: float = 0.06
    kor_agonist_memory_penalty: float = 0.16
    kor_antagonist_memory_bonus: float = 0.08

    # Pairwise trust/cooperation.
    initial_trust_mean: float = 0.72
    initial_trust_sd: float = 0.08
    sync_trust_gain: float = 0.055
    missed_sync_trust_loss: float = 0.045
    divergence_trust_loss: float = 0.005
    stress_trust_loss: float = 0.003
    meth_trust_loss_multiplier: float = 0.55
    kor_agonist_trust_penalty: float = 0.001
    kor_antagonist_trust_bonus: float = 0.001

    # Withholding is an emergent probability from low pairwise trust.
    withholding_threshold: float = 0.50
    withholding_gain: float = 2.4

    # Synchronization.
    sync_memory_gain: float = 0.50


@dataclass
class StateNetworkSummary:
    switches: int
    switch_rate: float
    unique_executive_states: int
    mean_coconscious_states: float
    blended_steps: int
    mean_pairwise_trust: float
    minimum_pairwise_trust: float
    memory_consistency: float
    memory_divergence: float
    withholding_events: int
    withholding_rate: float
    sync_expected: int
    sync_completed: int
    sync_completion_rate: float
    low_energy_handoffs: int
    final_energy_mean: float

    def to_dict(self) -> Dict[str, float | int]:
        return asdict(self)


@dataclass
class StateNetworkTrace:
    executive: list[int]
    coconscious: list[tuple[int, ...]]
    mean_trust: list[float]
    memory_consistency: list[float]
    withholding_events: list[int]


def _sigmoid(x: float) -> float:
    x = max(-40.0, min(40.0, x))
    return float(1.0 / (1.0 + np.exp(-x)))


def _memory_modifier(
    inputs: MechanismInput,
    params: StateNetworkParameters,
) -> float:
    value = 1.0
    value *= 1.0 - params.nmda_memory_penalty * inputs.nmda_antagonism
    value *= 1.0 - params.meth_memory_penalty * inputs.meth
    value *= 1.0 - params.kor_agonist_memory_penalty * inputs.kor_agonism
    value += params.mor_partial_memory_bonus * inputs.mor_partial_agonism
    value += params.kor_antagonist_memory_bonus * inputs.kor_antagonism
    return float(_clamp01(value))


def _switch_probability(
    energy: float,
    stress: float,
    inputs: MechanismInput,
    params: StateNetworkParameters,
) -> float:
    logit = (
        params.switch_intercept
        + params.fatigue_switch_weight * (1.0 - energy)
        + params.stress_switch_weight * stress
        + params.meth_switch_weight * inputs.meth
        + params.nmda_switch_weight * inputs.nmda_antagonism
        + params.mor_partial_switch_weight * inputs.mor_partial_agonism
        + params.kor_agonist_switch_weight * inputs.kor_agonism
        + params.kor_antagonist_switch_weight * inputs.kor_antagonism
        + params.nop_agonist_switch_weight * inputs.nop_agonism
        + params.nop_antagonist_switch_weight * inputs.nop_antagonism
    )
    return _sigmoid(logit)


def _offdiag_values(matrix: np.ndarray) -> np.ndarray:
    mask = ~np.eye(matrix.shape[0], dtype=bool)
    return matrix[mask]


def _mean_pairwise_trust(trust: np.ndarray) -> float:
    return float(np.mean(_offdiag_values(trust)))


def _memory_consistency(knowledge: np.ndarray, through_step: int) -> float:
    if through_step < 0:
        return 1.0
    used = knowledge[:, : through_step + 1]
    divergence = np.max(used, axis=0) - np.min(used, axis=0)
    return float(1.0 - np.mean(divergence))


def _choose_coconscious(
    executive: int,
    trust: np.ndarray,
    access_bias: np.ndarray,
    inputs: MechanismInput,
    config: StateNetworkConfig,
    params: StateNetworkParameters,
    rng: np.random.Generator,
) -> tuple[int, ...]:
    if config.max_coconscious <= 1:
        return (executive,)

    candidates = [i for i in range(config.n_states) if i != executive]
    selected = [executive]
    for candidate in sorted(
        candidates,
        key=lambda i: trust[executive, i] * access_bias[i],
        reverse=True,
    ):
        p = (
            params.coconscious_base
            + params.coconscious_trust_weight * trust[executive, candidate]
            - params.coconscious_nmda_penalty * inputs.nmda_antagonism
            - params.coconscious_meth_penalty * inputs.meth
        )
        if rng.random() < float(_clamp01(p)):
            selected.append(candidate)
            if len(selected) >= config.max_coconscious:
                break
    return tuple(selected)


def _choose_next_executive(
    current: int,
    energy: np.ndarray,
    trust: np.ndarray,
    access_bias: np.ndarray,
    rng: np.random.Generator,
) -> int:
    candidates = np.array([i for i in range(len(energy)) if i != current])
    trust_from_current = trust[current, candidates]
    weights = (
        0.55 * energy[candidates]
        + 0.25 * access_bias[candidates]
        + 0.20 * trust_from_current
    )
    weights = np.maximum(weights, 1e-9)
    weights /= np.sum(weights)
    return int(rng.choice(candidates, p=weights))


def build_default_timeline(
    config: StateNetworkConfig,
    *,
    include_wake_events: bool = True,
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    if include_wake_events:
        for step in range(config.sync_interval - 1, config.steps, config.sync_interval):
            events.append(TimelineEvent(step=step, kind=EventKind.WAKE, label="wake_sync"))
    return events


def simulate_state_network(
    inputs: MechanismInput,
    *,
    config: StateNetworkConfig = StateNetworkConfig(),
    params: StateNetworkParameters = StateNetworkParameters(),
    timeline: Sequence[TimelineEvent] | None = None,
    return_trace: bool = False,
) -> StateNetworkSummary | tuple[StateNetworkSummary, StateNetworkTrace]:
    inputs.validate()
    if config.n_states < 2:
        raise ValueError("n_states must be >= 2")
    if config.max_coconscious < 1 or config.max_coconscious > config.n_states:
        raise ValueError("max_coconscious must be in [1, n_states]")
    if config.steps <= 0:
        raise ValueError("steps must be > 0")

    events = list(timeline) if timeline is not None else build_default_timeline(config)
    for event in events:
        event.validate(config.steps)

    events_at: dict[int, list[TimelineEvent]] = {}
    for event in events:
        events_at.setdefault(event.step, []).append(event)

    rng = np.random.default_rng(config.seed)
    n = config.n_states

    energy = rng.uniform(0.72, 0.96, n)
    access_bias = rng.lognormal(mean=0.0, sigma=0.18, size=n)
    access_bias /= float(np.mean(access_bias))

    trust = rng.normal(params.initial_trust_mean, params.initial_trust_sd, size=(n, n))
    trust = _clamp01((trust + trust.T) / 2.0)
    np.fill_diagonal(trust, 1.0)

    knowledge = np.zeros((n, config.steps), dtype=float)

    executive = int(np.argmax(access_bias))
    occupancy = np.zeros(n, dtype=np.int32)
    switches = 0
    low_energy_handoffs = 0
    blended_steps = 0
    total_coconscious = 0
    withholding_events = 0
    sharing_opportunities = 0
    sync_expected = sum(event.kind in (EventKind.WAKE, EventKind.SYNC) for event in events)
    sync_completed = 0

    trace_exec: list[int] = []
    trace_coc: list[tuple[int, ...]] = []
    trace_trust: list[float] = []
    trace_consistency: list[float] = []
    trace_withholding: list[int] = []

    memory_modifier = _memory_modifier(inputs, params)
    stress = 0.0

    for step in range(config.steps):
        step_withholding = 0

        # Explicit timeline events.
        for event in events_at.get(step, []):
            if event.kind == EventKind.STRESS:
                stress = max(stress, event.intensity)
            elif event.kind == EventKind.EXTERNAL:
                stress = max(stress, 0.25 * event.intensity)
            elif event.kind in (EventKind.WAKE, EventKind.SYNC):
                disrupted_probability = (
                    inputs.wake_anchor_disruption
                    if event.kind == EventKind.WAKE
                    else 0.0
                )
                completed = rng.random() >= disrupted_probability
                if completed:
                    sync_completed += 1
                    shared = np.max(knowledge[:, : step + 1], axis=0)
                    knowledge[:, : step + 1] += params.sync_memory_gain * (
                        shared[None, :] - knowledge[:, : step + 1]
                    )
                    trust += params.sync_trust_gain * (1.0 - trust)
                    np.fill_diagonal(trust, 1.0)
                else:
                    trust -= params.missed_sync_trust_loss
                    trust = _clamp01(trust)
                    np.fill_diagonal(trust, 1.0)

        coconscious = _choose_coconscious(
            executive,
            trust,
            access_bias,
            inputs,
            config,
            params,
            rng,
        )
        total_coconscious += len(coconscious)
        if len(coconscious) > 1:
            blended_steps += 1

        # New event: executive has full access; co-conscious states get partial access.
        knowledge[executive, step] = 1.0
        for state in coconscious:
            if state != executive:
                knowledge[state, step] = max(knowledge[state, step], 0.70)

        # Pairwise sharing. Low trust can produce withholding.
        for src in range(n):
            for dst in range(n):
                if src == dst:
                    continue
                sharing_opportunities += 1
                low_trust = max(0.0, params.withholding_threshold - trust[src, dst])
                p_withhold = _clamp01(params.withholding_gain * low_trust)
                if rng.random() < p_withhold:
                    withholding_events += 1
                    step_withholding += 1
                    continue

                share_rate = params.memory_share_rate * trust[src, dst] * memory_modifier
                knowledge[dst, : step + 1] += share_rate * (
                    knowledge[src, : step + 1] - knowledge[dst, : step + 1]
                )

        # Divergent knowledge erodes pairwise trust slightly.
        state_means = np.mean(knowledge[:, : step + 1], axis=1)
        pairwise_divergence = np.abs(state_means[:, None] - state_means[None, :])
        trust -= params.divergence_trust_loss * pairwise_divergence

        # Stress and opioid-system assumptions modify trust dynamics.
        trust -= params.stress_trust_loss * stress
        trust -= (
            params.kor_agonist_trust_penalty
            * inputs.kor_agonism
            * (1.0 + params.meth_trust_loss_multiplier * inputs.meth)
        )
        trust += params.kor_antagonist_trust_bonus * inputs.kor_antagonism
        trust = _clamp01(trust)
        np.fill_diagonal(trust, 1.0)

        # Energy/fatigue.
        fatigue = params.fatigue_rate * (
            1.0 + params.meth_fatigue_multiplier * inputs.meth
        )
        energy[executive] = max(0.0, energy[executive] - fatigue)
        for state in range(n):
            if state != executive:
                energy[state] = min(1.0, energy[state] + params.recovery_rate)

        # Executive transition.
        p_switch = _switch_probability(
            float(energy[executive]),
            stress,
            inputs,
            params,
        )
        if rng.random() < p_switch:
            if energy[executive] < 0.35:
                low_energy_handoffs += 1
            executive = _choose_next_executive(
                executive,
                energy,
                trust,
                access_bias,
                rng,
            )
            switches += 1

        occupancy[executive] += 1

        # Stress decays unless renewed by the timeline.
        stress *= 0.86

        if return_trace:
            trace_exec.append(executive)
            trace_coc.append(coconscious)
            trace_trust.append(_mean_pairwise_trust(trust))
            trace_consistency.append(_memory_consistency(knowledge, step))
            trace_withholding.append(step_withholding)

    consistency = _memory_consistency(knowledge, config.steps - 1)
    offdiag = _offdiag_values(trust)
    withholding_rate = withholding_events / max(1, sharing_opportunities)
    sync_rate = sync_completed / max(1, sync_expected)

    summary = StateNetworkSummary(
        switches=switches,
        switch_rate=switches / config.steps,
        unique_executive_states=int(np.sum(occupancy > 0)),
        mean_coconscious_states=total_coconscious / config.steps,
        blended_steps=blended_steps,
        mean_pairwise_trust=float(np.mean(offdiag)),
        minimum_pairwise_trust=float(np.min(offdiag)),
        memory_consistency=consistency,
        memory_divergence=1.0 - consistency,
        withholding_events=withholding_events,
        withholding_rate=withholding_rate,
        sync_expected=sync_expected,
        sync_completed=sync_completed,
        sync_completion_rate=sync_rate,
        low_energy_handoffs=low_energy_handoffs,
        final_energy_mean=float(np.mean(energy)),
    )

    if not return_trace:
        return summary

    trace = StateNetworkTrace(
        executive=trace_exec,
        coconscious=trace_coc,
        mean_trust=trace_trust,
        memory_consistency=trace_consistency,
        withholding_events=trace_withholding,
    )
    return summary, trace
