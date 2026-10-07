"""Synthetic belief/claim ledger for cross-state information integrity.

This layer models *content* rather than only memory accessibility. It is designed to
test a specific hypothesis: information divergence can progress from innocent
inconsistency to withholding and then to deliberate false reporting when pairwise trust
collapses.

Important:
- "misreport" is a model variable, not a claim that DID states generally deceive.
- no state has a fixed moral type;
- the same state may cooperate or misreport depending on current network conditions;
- ground truth is available only to the simulator for scoring, not to synthetic states.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, Sequence

import numpy as np

from research.dissociation.model import MechanismInput
from research.dissociation.state_network import (
    EventKind,
    TimelineEvent,
)


def _clamp01(x):
    return np.clip(x, 0.0, 1.0)


class CoordinationRegime(str, Enum):
    COOPERATIVE = "cooperative"
    FRAGMENTED = "fragmented"
    ADVERSARIAL = "adversarial"


@dataclass(frozen=True)
class FactEvent:
    step: int
    truth: int
    salience: float = 1.0
    label: str = ""

    def validate(self, steps: int) -> None:
        if not 0 <= self.step < steps:
            raise ValueError(f"fact step {self.step} outside [0, {steps})")
        if self.truth not in (-1, 1):
            raise ValueError("truth must be -1 or +1")
        if not 0.0 <= self.salience <= 1.0:
            raise ValueError("salience must be in [0, 1]")


@dataclass(frozen=True)
class BeliefNetworkConfig:
    n_states: int = 4
    steps: int = 480
    seed: int = 37
    sync_interval: int = 96
    max_coconscious: int = 2


@dataclass(frozen=True)
class BeliefNetworkParameters:
    # Executive dynamics.
    fatigue_rate: float = 0.015
    recovery_rate: float = 0.010
    meth_fatigue_multiplier: float = 0.40
    switch_intercept: float = -2.50
    fatigue_switch_weight: float = 1.20
    meth_switch_weight: float = 1.00
    nmda_switch_weight: float = 0.55

    # Observation/encoding.
    base_encoding_accuracy: float = 0.96
    meth_encoding_penalty: float = 0.14
    nmda_encoding_penalty: float = 0.20
    coconscious_observation_accuracy: float = 0.82

    # Communication.
    base_communication_probability: float = 0.18
    mor_partial_communication_bonus: float = 0.05
    kor_agonist_communication_penalty: float = 0.08
    kor_antagonist_communication_bonus: float = 0.05
    nmda_communication_penalty: float = 0.10

    # Pairwise trust.
    initial_trust_mean: float = 0.76
    initial_trust_sd: float = 0.06
    sync_trust_gain: float = 0.05
    missed_sync_trust_loss: float = 0.05
    contradiction_trust_loss: float = 0.10
    resolved_agreement_gain: float = 0.015

    # Withholding and false reporting.
    withholding_threshold: float = 0.52
    withholding_gain: float = 2.20
    misreport_threshold: float = 0.34
    misreport_gain: float = 1.80

    # Deliberately default to zero direct meth effect. If meth increases false
    # reporting in a fitted model, that should emerge through trust/divergence or
    # survive sensitivity analysis rather than being assumed.
    direct_meth_misreport_weight: float = 0.0

    # Synchronization/reconciliation.
    sync_reconciliation_probability: float = 0.72

    # Regime classification thresholds (model taxonomy only).
    cooperative_trust_threshold: float = 0.64
    cooperative_consistency_threshold: float = 0.74
    adversarial_trust_threshold: float = 0.38
    adversarial_false_report_threshold: float = 0.12


@dataclass
class BeliefNetworkSummary:
    switches: int
    switch_rate: float
    mean_pairwise_trust: float
    belief_consistency: float
    truth_accuracy: float
    false_consensus_rate: float
    communication_opportunities: int
    delivered_reports: int
    communication_opportunities_per_step: float
    withholding_events: int
    withholding_rate: float
    withholding_events_per_step: float
    false_report_events: int
    false_report_rate: float
    false_report_events_per_step: float
    sync_expected: int
    sync_completed: int
    cooperative_steps: int
    fragmented_steps: int
    adversarial_steps: int
    final_regime: str

    def to_dict(self) -> Dict[str, float | int | str]:
        return asdict(self)


@dataclass
class BeliefNetworkTrace:
    executive: list[int]
    mean_trust: list[float]
    consistency: list[float]
    truth_accuracy: list[float]
    regime: list[str]
    withholding_events: list[int]
    false_report_events: list[int]


def _sigmoid(x: float) -> float:
    x = max(-40.0, min(40.0, x))
    return float(1.0 / (1.0 + np.exp(-x)))


def _offdiag(matrix: np.ndarray) -> np.ndarray:
    return matrix[~np.eye(matrix.shape[0], dtype=bool)]


def _mean_trust(trust: np.ndarray) -> float:
    return float(np.mean(_offdiag(trust)))


def _encoding_accuracy(
    inputs: MechanismInput,
    params: BeliefNetworkParameters,
) -> float:
    value = (
        params.base_encoding_accuracy
        - params.meth_encoding_penalty * inputs.meth
        - params.nmda_encoding_penalty * inputs.nmda_antagonism
    )
    return float(_clamp01(value))


def _communication_probability(
    inputs: MechanismInput,
    params: BeliefNetworkParameters,
) -> float:
    value = (
        params.base_communication_probability
        + params.mor_partial_communication_bonus * inputs.mor_partial_agonism
        - params.kor_agonist_communication_penalty * inputs.kor_agonism
        + params.kor_antagonist_communication_bonus * inputs.kor_antagonism
        - params.nmda_communication_penalty * inputs.nmda_antagonism
    )
    return float(_clamp01(value))


def _withholding_probability(trust_value: float, params: BeliefNetworkParameters) -> float:
    deficit = max(0.0, params.withholding_threshold - trust_value)
    return float(_clamp01(params.withholding_gain * deficit))


def _false_report_probability(
    trust_value: float,
    inputs: MechanismInput,
    params: BeliefNetworkParameters,
) -> float:
    deficit = max(0.0, params.misreport_threshold - trust_value)
    p = (
        params.misreport_gain * deficit
        + params.direct_meth_misreport_weight * inputs.meth
    )
    return float(_clamp01(p))


def _switch_probability(
    energy: float,
    inputs: MechanismInput,
    params: BeliefNetworkParameters,
) -> float:
    logit = (
        params.switch_intercept
        + params.fatigue_switch_weight * (1.0 - energy)
        + params.meth_switch_weight * inputs.meth
        + params.nmda_switch_weight * inputs.nmda_antagonism
    )
    return _sigmoid(logit)


def _choose_next_state(
    current: int,
    energy: np.ndarray,
    access_bias: np.ndarray,
    trust: np.ndarray,
    rng: np.random.Generator,
) -> int:
    candidates = np.array([i for i in range(len(energy)) if i != current])
    weights = (
        0.55 * energy[candidates]
        + 0.25 * access_bias[candidates]
        + 0.20 * trust[current, candidates]
    )
    weights = np.maximum(weights, 1e-9)
    weights /= np.sum(weights)
    return int(rng.choice(candidates, p=weights))


def _choose_coconscious(
    executive: int,
    trust: np.ndarray,
    access_bias: np.ndarray,
    config: BeliefNetworkConfig,
    rng: np.random.Generator,
) -> tuple[int, ...]:
    selected = [executive]
    if config.max_coconscious <= 1:
        return tuple(selected)

    candidates = [i for i in range(config.n_states) if i != executive]
    candidates.sort(
        key=lambda i: trust[executive, i] * access_bias[i],
        reverse=True,
    )
    for candidate in candidates:
        p = 0.10 + 0.55 * trust[executive, candidate]
        if rng.random() < p:
            selected.append(candidate)
            if len(selected) >= config.max_coconscious:
                break
    return tuple(selected)


def _known_consistency(beliefs: np.ndarray, n_facts: int) -> float:
    if n_facts == 0:
        return 1.0
    scores = []
    for fact in range(n_facts):
        values = beliefs[:, fact]
        known = values[~np.isnan(values)]
        if len(known) <= 1:
            scores.append(1.0)
        else:
            counts = [np.sum(known == -1), np.sum(known == 1)]
            scores.append(max(counts) / len(known))
    return float(np.mean(scores))


def _truth_accuracy(
    beliefs: np.ndarray,
    truths: np.ndarray,
    n_facts: int,
) -> float:
    if n_facts == 0:
        return 1.0
    correct = 0
    known = 0
    for fact in range(n_facts):
        values = beliefs[:, fact]
        mask = ~np.isnan(values)
        correct += int(np.sum(values[mask] == truths[fact]))
        known += int(np.sum(mask))
    return correct / known if known else 1.0


def _false_consensus_rate(
    beliefs: np.ndarray,
    truths: np.ndarray,
    n_facts: int,
) -> float:
    if n_facts == 0:
        return 0.0
    false_consensus = 0
    eligible = 0
    for fact in range(n_facts):
        values = beliefs[:, fact]
        known = values[~np.isnan(values)]
        if len(known) < 2:
            continue
        eligible += 1
        if np.all(known == known[0]) and known[0] != truths[fact]:
            false_consensus += 1
    return false_consensus / eligible if eligible else 0.0


def _regime(
    mean_trust: float,
    consistency: float,
    recent_false_report_rate: float,
    params: BeliefNetworkParameters,
) -> CoordinationRegime:
    if (
        mean_trust <= params.adversarial_trust_threshold
        or recent_false_report_rate >= params.adversarial_false_report_threshold
    ):
        return CoordinationRegime.ADVERSARIAL
    if (
        mean_trust >= params.cooperative_trust_threshold
        and consistency >= params.cooperative_consistency_threshold
    ):
        return CoordinationRegime.COOPERATIVE
    return CoordinationRegime.FRAGMENTED


def default_sync_timeline(config: BeliefNetworkConfig) -> list[TimelineEvent]:
    return [
        TimelineEvent(step=step, kind=EventKind.WAKE, label="wake_sync")
        for step in range(config.sync_interval - 1, config.steps, config.sync_interval)
    ]


def simulate_belief_network(
    inputs: MechanismInput,
    facts: Sequence[FactEvent],
    *,
    config: BeliefNetworkConfig = BeliefNetworkConfig(),
    params: BeliefNetworkParameters = BeliefNetworkParameters(),
    timeline: Sequence[TimelineEvent] | None = None,
    return_trace: bool = False,
) -> BeliefNetworkSummary | tuple[BeliefNetworkSummary, BeliefNetworkTrace]:
    inputs.validate()
    if config.n_states < 2:
        raise ValueError("n_states must be >= 2")
    if config.max_coconscious < 1 or config.max_coconscious > config.n_states:
        raise ValueError("max_coconscious must be in [1, n_states]")

    facts = list(facts)
    for fact in facts:
        fact.validate(config.steps)
    facts_at: dict[int, list[tuple[int, FactEvent]]] = {}
    for idx, fact in enumerate(facts):
        facts_at.setdefault(fact.step, []).append((idx, fact))

    timeline = list(timeline) if timeline is not None else default_sync_timeline(config)
    for event in timeline:
        event.validate(config.steps)
    events_at: dict[int, list[TimelineEvent]] = {}
    for event in timeline:
        events_at.setdefault(event.step, []).append(event)

    rng = np.random.default_rng(config.seed)
    n = config.n_states
    n_facts = len(facts)

    energy = rng.uniform(0.74, 0.96, n)
    access_bias = rng.lognormal(0.0, 0.18, n)
    access_bias /= float(np.mean(access_bias))

    trust = rng.normal(params.initial_trust_mean, params.initial_trust_sd, (n, n))
    trust = _clamp01((trust + trust.T) / 2.0)
    np.fill_diagonal(trust, 1.0)

    beliefs = np.full((n, n_facts), np.nan, dtype=float)
    truths = np.array([fact.truth for fact in facts], dtype=float)

    executive = int(np.argmax(access_bias))
    switches = 0
    withholding_events = 0
    false_report_events = 0
    communication_opportunities = 0
    sync_expected = sum(event.kind in (EventKind.WAKE, EventKind.SYNC) for event in timeline)
    sync_completed = 0

    regime_counts = {
        CoordinationRegime.COOPERATIVE: 0,
        CoordinationRegime.FRAGMENTED: 0,
        CoordinationRegime.ADVERSARIAL: 0,
    }

    trace_exec: list[int] = []
    trace_trust: list[float] = []
    trace_consistency: list[float] = []
    trace_accuracy: list[float] = []
    trace_regime: list[str] = []
    trace_withholding: list[int] = []
    trace_false: list[int] = []

    encoding_accuracy = _encoding_accuracy(inputs, params)
    communication_probability = _communication_probability(inputs, params)

    recent_false_window: list[int] = []
    recent_opportunity_window: list[int] = []

    for step in range(config.steps):
        step_withholding = 0
        step_false = 0
        step_opportunities = 0

        coconscious = _choose_coconscious(
            executive,
            trust,
            access_bias,
            config,
            rng,
        )

        # New external facts are encoded by the executive and possibly by co-conscious states.
        for fact_idx, fact in facts_at.get(step, []):
            observed = fact.truth if rng.random() < encoding_accuracy else -fact.truth
            beliefs[executive, fact_idx] = observed
            for state in coconscious:
                if state == executive:
                    continue
                p_correct = (
                    params.coconscious_observation_accuracy
                    * encoding_accuracy
                    * (0.5 + 0.5 * fact.salience)
                )
                beliefs[state, fact_idx] = (
                    fact.truth if rng.random() < p_correct else -fact.truth
                )

        # Pairwise communication about known facts.
        for src in range(n):
            known_facts = np.flatnonzero(~np.isnan(beliefs[src]))
            if not len(known_facts):
                continue
            for dst in range(n):
                if src == dst:
                    continue
                for fact_idx in known_facts:
                    if rng.random() >= communication_probability:
                        continue
                    communication_opportunities += 1
                    step_opportunities += 1

                    p_withhold = _withholding_probability(trust[src, dst], params)
                    if rng.random() < p_withhold:
                        withholding_events += 1
                        step_withholding += 1
                        continue

                    report = beliefs[src, fact_idx]
                    p_false = _false_report_probability(
                        trust[src, dst],
                        inputs,
                        params,
                    )
                    if rng.random() < p_false:
                        report = -report
                        false_report_events += 1
                        step_false += 1

                    existing = beliefs[dst, fact_idx]
                    if np.isnan(existing):
                        # First transmission can earn a small amount of trust, but
                        # repeated restatement of the same claim must not ratchet
                        # trust toward 1.0 indefinitely.
                        trust[src, dst] += 0.25 * params.resolved_agreement_gain
                        trust[dst, src] += 0.25 * params.resolved_agreement_gain
                    elif existing != report:
                        trust[src, dst] -= params.contradiction_trust_loss
                        trust[dst, src] -= params.contradiction_trust_loss
                    # Existing agreement is informationally redundant: no trust gain.

                    beliefs[dst, fact_idx] = report

        # Synchronization compares currently held beliefs and reconciles toward majority,
        # not toward hidden ground truth. This permits false consensus.
        for event in events_at.get(step, []):
            if event.kind not in (EventKind.WAKE, EventKind.SYNC):
                continue
            disrupted = (
                event.kind == EventKind.WAKE
                and rng.random() < inputs.wake_anchor_disruption
            )
            if disrupted:
                trust -= params.missed_sync_trust_loss
                trust = _clamp01(trust)
                np.fill_diagonal(trust, 1.0)
                continue

            sync_completed += 1
            for fact_idx in range(n_facts):
                known = beliefs[:, fact_idx]
                mask = ~np.isnan(known)
                if np.sum(mask) < 2:
                    continue
                values = known[mask]
                majority = 1.0 if np.sum(values == 1) >= np.sum(values == -1) else -1.0
                for state in range(n):
                    if rng.random() < params.sync_reconciliation_probability:
                        beliefs[state, fact_idx] = majority
            trust += params.sync_trust_gain * (1.0 - trust)
            trust = _clamp01(trust)
            np.fill_diagonal(trust, 1.0)

        # Fatigue/recovery and executive handoff.
        fatigue = params.fatigue_rate * (
            1.0 + params.meth_fatigue_multiplier * inputs.meth
        )
        energy[executive] = max(0.0, energy[executive] - fatigue)
        for state in range(n):
            if state != executive:
                energy[state] = min(1.0, energy[state] + params.recovery_rate)

        if rng.random() < _switch_probability(float(energy[executive]), inputs, params):
            executive = _choose_next_state(
                executive,
                energy,
                access_bias,
                trust,
                rng,
            )
            switches += 1

        trust = _clamp01(trust)
        np.fill_diagonal(trust, 1.0)

        consistency = _known_consistency(beliefs, n_facts)
        accuracy = _truth_accuracy(beliefs, truths, n_facts)

        recent_false_window.append(step_false)
        recent_opportunity_window.append(step_opportunities)
        if len(recent_false_window) > 48:
            recent_false_window.pop(0)
            recent_opportunity_window.pop(0)
        recent_false_rate = (
            sum(recent_false_window) / max(1, sum(recent_opportunity_window))
        )

        regime = _regime(
            _mean_trust(trust),
            consistency,
            recent_false_rate,
            params,
        )
        regime_counts[regime] += 1

        if return_trace:
            trace_exec.append(executive)
            trace_trust.append(_mean_trust(trust))
            trace_consistency.append(consistency)
            trace_accuracy.append(accuracy)
            trace_regime.append(regime.value)
            trace_withholding.append(step_withholding)
            trace_false.append(step_false)

    final_consistency = _known_consistency(beliefs, n_facts)
    final_accuracy = _truth_accuracy(beliefs, truths, n_facts)
    final_false_consensus = _false_consensus_rate(beliefs, truths, n_facts)
    final_recent_false_rate = (
        sum(recent_false_window) / max(1, sum(recent_opportunity_window))
    )
    final_regime = _regime(
        _mean_trust(trust),
        final_consistency,
        final_recent_false_rate,
        params,
    )

    summary = BeliefNetworkSummary(
        switches=switches,
        switch_rate=switches / config.steps,
        mean_pairwise_trust=_mean_trust(trust),
        belief_consistency=final_consistency,
        truth_accuracy=final_accuracy,
        false_consensus_rate=final_false_consensus,
        communication_opportunities=communication_opportunities,
        delivered_reports=max(0, communication_opportunities - withholding_events),
        communication_opportunities_per_step=communication_opportunities / config.steps,
        withholding_events=withholding_events,
        withholding_rate=withholding_events / max(1, communication_opportunities),
        withholding_events_per_step=withholding_events / config.steps,
        false_report_events=false_report_events,
        false_report_rate=false_report_events / max(1, communication_opportunities),
        false_report_events_per_step=false_report_events / config.steps,
        sync_expected=sync_expected,
        sync_completed=sync_completed,
        cooperative_steps=regime_counts[CoordinationRegime.COOPERATIVE],
        fragmented_steps=regime_counts[CoordinationRegime.FRAGMENTED],
        adversarial_steps=regime_counts[CoordinationRegime.ADVERSARIAL],
        final_regime=final_regime.value,
    )

    if not return_trace:
        return summary

    return summary, BeliefNetworkTrace(
        executive=trace_exec,
        mean_trust=trace_trust,
        consistency=trace_consistency,
        truth_accuracy=trace_accuracy,
        regime=trace_regime,
        withholding_events=trace_withholding,
        false_report_events=trace_false,
    )
