"""Compatibility alias for the canonical HumanSim compound disposition model."""

from research.human_sim.disposition import (
    CompoundDisposition,
    synthetic_reference_disposition,
)

CompoundPKSpec = CompoundDisposition
synthetic_compound_pk = synthetic_reference_disposition

__all__ = [
    "CompoundPKSpec",
    "CompoundDisposition",
    "synthetic_compound_pk",
    "synthetic_reference_disposition",
]
