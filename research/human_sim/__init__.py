"""Multiscale virtual-human research modules.

This package is deliberately separate from ZeroPain's production/legacy PK/PD path.
It is a mechanistic research stack and does not provide human dosing recommendations.
"""

from research.human_sim.adaptation import AdaptationParameters, AdaptationState
from research.human_sim.competition import CompetitionState, LigandInteraction, competitive_state
from research.human_sim.disposition import CompoundDisposition
from research.human_sim.pbpk import PBPKState, PBPKTrace, simulate_pbpk
from research.human_sim.physiology import Physiology, TissueSpec
from research.human_sim.compound_pk import CompoundPKSpec
from research.human_sim.multiligand_engine import LigandSpec, MultiLigandResult, simulate_multiligand_chain
from research.human_sim.population import VirtualIndividual
from research.human_sim.receptors import ReceptorTarget, receptor_state

__all__ = [
    "Physiology",
    "TissueSpec",
    "CompoundPKSpec",
    "CompoundDisposition",
    "LigandInteraction",
    "CompetitionState",
    "competitive_state",
    "LigandSpec",
    "MultiLigandResult",
    "simulate_multiligand_chain",
    "VirtualIndividual",
    "PBPKState",
    "PBPKTrace",
    "simulate_pbpk",
    "ReceptorTarget",
    "receptor_state",
    "AdaptationParameters",
    "AdaptationState",
]
