"""Multiscale virtual-human research modules.

This package is deliberately separate from ZeroPain's production/legacy PK/PD path.
It is a mechanistic research stack and does not provide human dosing recommendations.
"""

from research.human_sim.physiology import Physiology, TissueSpec
from research.human_sim.pbpk import PBPKState, PBPKTrace, simulate_pbpk
from research.human_sim.receptors import ReceptorTarget, receptor_state
from research.human_sim.adaptation import AdaptationParameters, AdaptationState

__all__ = [
    "Physiology",
    "TissueSpec",
    "PBPKState",
    "PBPKTrace",
    "simulate_pbpk",
    "ReceptorTarget",
    "receptor_state",
    "AdaptationParameters",
    "AdaptationState",
]
