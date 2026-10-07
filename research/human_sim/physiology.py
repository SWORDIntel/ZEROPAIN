"""Physiology parameter objects for the HumanSim research stack.

No built-in profile is asserted to be a validated human reference. Parameters should
ultimately be loaded from source-backed datasets with provenance and uncertainty.

Volumes use liters, flows use liters/hour, and partition coefficients are unitless.
Those units define the numerical interface; this module does NOT provide dose
conversion or administration guidance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class TissueSpec:
    name: str
    volume_l: float
    blood_flow_l_per_h: float
    partition_coefficient: float

    def validate(self) -> None:
        if not self.name:
            raise ValueError("tissue name cannot be blank")
        if self.volume_l <= 0:
            raise ValueError(f"{self.name}: volume_l must be positive")
        if self.blood_flow_l_per_h < 0:
            raise ValueError(f"{self.name}: blood_flow_l_per_h cannot be negative")
        if self.partition_coefficient <= 0:
            raise ValueError(f"{self.name}: partition_coefficient must be positive")


@dataclass(frozen=True)
class Physiology:
    central_volume_l: float
    tissues: tuple[TissueSpec, ...]
    hepatic_clearance_l_per_h: float = 0.0
    renal_clearance_l_per_h: float = 0.0
    plasma_unbound_fraction: float = 1.0
    brain_unbound_fraction: float = 1.0
    label: str = "custom"
    evidence_status: str = "user_supplied_or_synthetic"

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
        if self.hepatic_clearance_l_per_h < 0 or self.renal_clearance_l_per_h < 0:
            raise ValueError("clearance values cannot be negative")
        if not 0.0 < self.plasma_unbound_fraction <= 1.0:
            raise ValueError("plasma_unbound_fraction must be in (0,1]")
        if not 0.0 < self.brain_unbound_fraction <= 1.0:
            raise ValueError("brain_unbound_fraction must be in (0,1]")
        if "brain" not in names:
            raise ValueError("HumanSim physiology must include a 'brain' compartment")

    @property
    def tissue_map(self) -> Mapping[str, TissueSpec]:
        return {tissue.name: tissue for tissue in self.tissues}

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "tissues"},
            "tissues": [asdict(tissue) for tissue in self.tissues],
        }


def synthetic_reference_physiology() -> Physiology:
    """Runnable software fixture, explicitly not a sourced human reference table."""

    return Physiology(
        central_volume_l=5.0,
        tissues=(
            TissueSpec("brain", 1.4, 40.0, 1.2),
            TissueSpec("liver", 1.8, 75.0, 2.0),
            TissueSpec("kidney", 0.35, 55.0, 1.4),
            TissueSpec("peripheral", 30.0, 60.0, 1.8),
        ),
        hepatic_clearance_l_per_h=2.0,
        renal_clearance_l_per_h=1.0,
        plasma_unbound_fraction=0.7,
        brain_unbound_fraction=0.5,
        label="SYNTHETIC_REFERENCE_DO_NOT_USE_CLINICALLY",
        evidence_status="synthetic_fixture",
    )
