"""Compound-specific disposition parameters for HumanSim PBPK.

These parameters are deliberately NOT part of Physiology.

Physiology owns anatomy and blood flow.
Disposition owns compound/tissue partitioning, unbound fractions, and the legacy
organ-tissue elimination coefficients used by the current PBPK kernel.

IMPORTANT: hepatic_clearance_l_per_h and renal_clearance_l_per_h are currently
applied against total concentration in the liver/kidney tissue compartments. They are
NOT interchangeable with a blood-referenced well-stirred hepatic clearance or with a
plasma-referenced renal clearance. Source-backed external builders therefore leave
these fields at zero unless a tissue-concentration clearance is explicitly supplied.

This separation prevents a human profile from silently baking in one compound's
chemistry while also making the remaining elimination-model limitation explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class CompoundDisposition:
    label: str
    tissue_partition_coefficients: Mapping[str, float]
    hepatic_clearance_l_per_h: float = 0.0
    renal_clearance_l_per_h: float = 0.0
    plasma_unbound_fraction: float = 1.0
    brain_unbound_fraction: float = 1.0
    blood_to_plasma_ratio: float = 1.0
    hepatic_intrinsic_unbound_clearance_l_per_h: float = 0.0
    liver_unbound_fraction: float | None = None
    renal_gfr_l_per_h: float = 0.0
    evidence_status: str = "user_supplied_or_synthetic"
    source_ids: tuple[str, ...] = ()

    def validate(self, tissue_names: set[str] | None = None) -> None:
        if not self.label:
            raise ValueError("disposition label cannot be blank")
        if not self.tissue_partition_coefficients:
            raise ValueError("at least one tissue partition coefficient is required")
        for name, value in self.tissue_partition_coefficients.items():
            if value <= 0:
                raise ValueError(f"{name}: partition coefficient must be positive")
        if tissue_names is not None:
            missing = tissue_names - set(self.tissue_partition_coefficients)
            extra = set(self.tissue_partition_coefficients) - tissue_names
            if missing:
                raise ValueError(f"missing partition coefficients for {sorted(missing)}")
            if extra:
                raise ValueError(f"unknown partition coefficient tissues: {sorted(extra)}")
        if self.hepatic_clearance_l_per_h < 0 or self.renal_clearance_l_per_h < 0:
            raise ValueError("clearance values cannot be negative")
        if not 0.0 < self.plasma_unbound_fraction <= 1.0:
            raise ValueError("plasma_unbound_fraction must be in (0,1]")
        if not 0.0 < self.brain_unbound_fraction <= 1.0:
            raise ValueError("brain_unbound_fraction must be in (0,1]")
        if self.blood_to_plasma_ratio <= 0:
            raise ValueError("blood_to_plasma_ratio must be positive")
        if self.hepatic_intrinsic_unbound_clearance_l_per_h < 0:
            raise ValueError("hepatic intrinsic unbound clearance cannot be negative")
        if self.hepatic_intrinsic_unbound_clearance_l_per_h > 0:
            if self.liver_unbound_fraction is None:
                raise ValueError(
                    "liver_unbound_fraction is required when intrinsic hepatic clearance is used"
                )
            if not 0.0 < self.liver_unbound_fraction <= 1.0:
                raise ValueError("liver_unbound_fraction must be in (0,1]")
        elif self.liver_unbound_fraction is not None and not 0.0 < self.liver_unbound_fraction <= 1.0:
            raise ValueError("liver_unbound_fraction must be in (0,1]")
        if self.renal_gfr_l_per_h < 0:
            raise ValueError("renal_gfr_l_per_h cannot be negative")
        if self.plasma_unbound_fraction / self.blood_to_plasma_ratio > 1.0 + 1e-12:
            raise ValueError(
                "plasma_unbound_fraction / blood_to_plasma_ratio exceeds 1"
            )

    def to_dict(self) -> dict:
        value = asdict(self)
        value["tissue_partition_coefficients"] = dict(self.tissue_partition_coefficients)
        value["source_ids"] = list(self.source_ids)
        return value


def synthetic_reference_disposition() -> CompoundDisposition:
    """Software fixture only; values are not asserted as drug data."""

    return CompoundDisposition(
        label="SYNTHETIC_DISPOSITION_DO_NOT_USE_CLINICALLY",
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
