"""Compound-specific PK parameters for HumanSim.

These parameters deliberately do not live on the Physiology object:
- tissue:plasma partition coefficients are compound-specific;
- unbound fractions are compound-specific;
- systemic clearances are compound-specific.

Values in synthetic_compound_pk() are software fixtures only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class CompoundPKSpec:
    label: str
    tissue_partition_coefficients: Mapping[str, float]
    hepatic_clearance_l_per_h: float = 0.0
    renal_clearance_l_per_h: float = 0.0
    plasma_unbound_fraction: float = 1.0
    brain_unbound_fraction: float = 1.0
    evidence_status: str = "user_supplied_or_synthetic"

    def validate_for_tissues(self, tissue_names) -> None:
        names = set(tissue_names)
        supplied = set(self.tissue_partition_coefficients)
        missing = names - supplied
        unknown = supplied - names
        if missing:
            raise ValueError(f"missing tissue partition coefficients: {sorted(missing)}")
        if unknown:
            raise ValueError(f"partition coefficients for unknown tissues: {sorted(unknown)}")
        for name, value in self.tissue_partition_coefficients.items():
            if value <= 0:
                raise ValueError(f"{name}: partition coefficient must be positive")
        if self.hepatic_clearance_l_per_h < 0 or self.renal_clearance_l_per_h < 0:
            raise ValueError("clearance values cannot be negative")
        if not 0.0 < self.plasma_unbound_fraction <= 1.0:
            raise ValueError("plasma_unbound_fraction must be in (0,1]")
        if not 0.0 < self.brain_unbound_fraction <= 1.0:
            raise ValueError("brain_unbound_fraction must be in (0,1]")

    def to_dict(self) -> dict:
        return asdict(self)


def synthetic_compound_pk() -> CompoundPKSpec:
    return CompoundPKSpec(
        label="SYNTHETIC_COMPOUND_PK_DO_NOT_USE_CLINICALLY",
        tissue_partition_coefficients={
            "brain": 1.2,
            "liver": 2.0,
            "kidney": 1.4,
            "peripheral": 1.8,
        },
        hepatic_clearance_l_per_h=2.0,
        renal_clearance_l_per_h=1.0,
        plasma_unbound_fraction=0.7,
        brain_unbound_fraction=0.5,
        evidence_status="synthetic_fixture",
    )
