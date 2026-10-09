"""Physiology-only parameter objects for the HumanSim research stack.

Physiology contains anatomy/hemodynamics only. Compound-specific tissue partitioning,
unbound fractions and clearance live in CompoundPKSpec.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class TissueSpec:
    name: str
    volume_l: float
    blood_flow_l_per_h: float

    def validate(self) -> None:
        if not self.name:
            raise ValueError("tissue name cannot be blank")
        if self.volume_l <= 0:
            raise ValueError(f"{self.name}: volume_l must be positive")
        if self.blood_flow_l_per_h < 0:
            raise ValueError(f"{self.name}: blood_flow_l_per_h cannot be negative")


@dataclass(frozen=True)
class Physiology:
    central_volume_l: float
    tissues: tuple[TissueSpec, ...]
    label: str = "custom"
    evidence_status: str = "user_supplied_or_synthetic"
    source_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.central_volume_l <= 0:
            raise ValueError("central_volume_l must be positive")
        if not self.tissues:
            raise ValueError("at least one tissue compartment is required")
        names = [t.name for t in self.tissues]
        if len(set(names)) != len(names):
            raise ValueError("tissue names must be unique")
        for tissue in self.tissues:
            tissue.validate()
        if "brain" not in names:
            raise ValueError("HumanSim physiology must include a 'brain' compartment")

    @property
    def tissue_map(self) -> Mapping[str, TissueSpec]:
        return {tissue.name: tissue for tissue in self.tissues}

    @property
    def total_tissue_flow_l_per_h(self) -> float:
        return sum(tissue.blood_flow_l_per_h for tissue in self.tissues)

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "tissues"},
            "tissues": [asdict(tissue) for tissue in self.tissues],
            "source_ids": list(self.source_ids),
        }


def synthetic_reference_physiology() -> Physiology:
    """Runnable software fixture, explicitly not a sourced human reference table."""

    return Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0),
            TissueSpec("liver", 1.8, 75.0),
            TissueSpec("kidney", 0.35, 55.0),
            TissueSpec("peripheral", 30.0, 60.0),
        ),
        label="SYNTHETIC_REFERENCE_DO_NOT_USE_CLINICALLY",
        evidence_status="synthetic_fixture",
    )
