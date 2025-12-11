"""
Tolerance/addiction progression models.
Pluggable update functions for tolerance and withdrawal dynamics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import math


@dataclass
class ToleranceState:
    level: float = 0.0
    ceiling: float = 3.0


@dataclass
class WithdrawalState:
    severity: float = 0.0
    onset_delay_days: float = 2.0


class ToleranceModel:
    def update(self, state: ToleranceState, exposure: float, dt_days: float) -> ToleranceState:
        raise NotImplementedError


class LinearTolerance(ToleranceModel):
    def __init__(self, slope: float = 0.01, ceiling: float = 3.0):
        self.slope = slope
        self.ceiling = ceiling

    def update(self, state: ToleranceState, exposure: float, dt_days: float) -> ToleranceState:
        increment = self.slope * exposure * dt_days
        state.level = min(state.level + increment, self.ceiling)
        state.ceiling = self.ceiling
        return state


class SigmoidTolerance(ToleranceModel):
    def __init__(self, max_factor: float = 3.0, half_life_days: float = 14.0):
        self.max_factor = max_factor
        self.half_life_days = max(half_life_days, 1e-3)

    def update(self, state: ToleranceState, exposure: float, dt_days: float) -> ToleranceState:
        k = math.log(2) / self.half_life_days
        target = self.max_factor * (1 - math.exp(-k * exposure))
        delta = (target - state.level) * (1 - math.exp(-k * dt_days))
        state.level = max(0.0, min(state.level + delta, self.max_factor))
        state.ceiling = self.max_factor
        return state


class LaggedTolerance(ToleranceModel):
    def __init__(self, rise_tau: float = 7.0, decay_tau: float = 10.0, ceiling: float = 3.0):
        self.rise_tau = max(rise_tau, 1e-3)
        self.decay_tau = max(decay_tau, 1e-3)
        self.ceiling = ceiling

    def update(self, state: ToleranceState, exposure: float, dt_days: float) -> ToleranceState:
        if exposure > 0:
            delta = (self.ceiling - state.level) * (1 - math.exp(-dt_days / self.rise_tau))
        else:
            delta = -(state.level) * (1 - math.exp(-dt_days / self.decay_tau))
        state.level = max(0.0, min(state.level + delta, self.ceiling))
        state.ceiling = self.ceiling
        return state


class WithdrawalModel:
    def update(self, state: WithdrawalState, abstinence_metric: float, dt_days: float) -> WithdrawalState:
        raise NotImplementedError


class SimpleWithdrawal(WithdrawalModel):
    def __init__(self, onset_delay_days: float = 2.0, severity_scale: float = 1.0):
        self.onset_delay_days = onset_delay_days
        self.severity_scale = severity_scale

    def update(self, state: WithdrawalState, abstinence_metric: float, dt_days: float) -> WithdrawalState:
        if abstinence_metric <= 0:
            state.severity = max(0.0, state.severity - 0.1 * dt_days)
            return state

        if abstinence_metric > self.onset_delay_days:
            state.severity = min(1.0, state.severity + 0.05 * self.severity_scale * dt_days)
        else:
            state.severity = max(0.0, state.severity - 0.05 * dt_days)
        return state


def make_tolerance_model(config: Dict) -> ToleranceModel:
    name = config.get("model", "sigmoid")
    if name == "linear":
        return LinearTolerance(slope=config.get("slope", 0.01), ceiling=config.get("max_factor", 3.0))
    if name == "lagged":
        return LaggedTolerance(
            rise_tau=config.get("rise_tau", 7.0),
            decay_tau=config.get("decay_tau", 10.0),
            ceiling=config.get("max_factor", 3.0),
        )
    return SigmoidTolerance(max_factor=config.get("max_factor", 3.0), half_life_days=config.get("half_life_days", 14.0))


def make_withdrawal_model(config: Dict) -> WithdrawalModel:
    wd = config.get("withdrawal", {})
    return SimpleWithdrawal(
        onset_delay_days=wd.get("onset_delay_days", 2.0),
        severity_scale=wd.get("severity_scale", 1.0),
    )

