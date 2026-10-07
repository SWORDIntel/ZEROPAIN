"""Build HumanSim compound disposition from external partition predictions.

HumanSim intentionally delegates complex tissue-partition prediction to established
backends such as httk/Schmitt or PK-Sim rather than duplicating those algorithms.

This builder:
- normalizes partition-coefficient basis;
- optionally uses measured/predicted Kp,uu,brain to set brain total Kp;
- computes reference clearance diagnostics;
- keeps legacy PBPK tissue-clearance fields at zero unless explicitly supplied as
  tissue-concentration clearance parameters.

No human dose conversion is performed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from research.human_sim.disposition import CompoundDisposition
from research.human_sim.disposition_mechanisms import (
    PartitionBasis,
    blood_unbound_fraction,
    brain_total_kp_from_kpuu,
    convert_partition_map,
    filtration_only_renal_clearance,
    well_stirred_hepatic_clearance,
)
from research.human_sim.physiology import Physiology


@dataclass(frozen=True)
class ExternalDispositionInputs:
    label: str
    tissue_partition_coefficients: Mapping[str, float]
    partition_basis: PartitionBasis | str
    fu_plasma: float
    fu_brain: float
    source_id: str
    method: str
    blood_to_plasma_ratio: float = 1.0
    kp_uu_brain: float | None = None
    intrinsic_hepatic_clearance_l_per_h: float | None = None
    gfr_l_per_h: float | None = None
    tissue_based_hepatic_clearance_l_per_h: float = 0.0
    tissue_based_renal_clearance_l_per_h: float = 0.0

    def validate(self) -> None:
        if not self.label:
            raise ValueError("label cannot be blank")
        if not self.source_id:
            raise ValueError("source_id cannot be blank")
        if not self.method:
            raise ValueError("method cannot be blank")
        if not self.tissue_partition_coefficients:
            raise ValueError("partition coefficients cannot be empty")
        PartitionBasis(self.partition_basis)
        if not 0.0 < self.fu_plasma <= 1.0:
            raise ValueError("fu_plasma must be in (0,1]")
        if not 0.0 < self.fu_brain <= 1.0:
            raise ValueError("fu_brain must be in (0,1]")
        if self.blood_to_plasma_ratio <= 0:
            raise ValueError("blood_to_plasma_ratio must be positive")
        if self.kp_uu_brain is not None and self.kp_uu_brain < 0:
            raise ValueError("kp_uu_brain cannot be negative")
        if (
            self.intrinsic_hepatic_clearance_l_per_h is not None
            and self.intrinsic_hepatic_clearance_l_per_h < 0
        ):
            raise ValueError("intrinsic hepatic clearance cannot be negative")
        if self.gfr_l_per_h is not None and self.gfr_l_per_h < 0:
            raise ValueError("GFR cannot be negative")
        if self.tissue_based_hepatic_clearance_l_per_h < 0:
            raise ValueError("tissue-based hepatic clearance cannot be negative")
        if self.tissue_based_renal_clearance_l_per_h < 0:
            raise ValueError("tissue-based renal clearance cannot be negative")


@dataclass(frozen=True)
class DispositionBuildResult:
    disposition: CompoundDisposition
    diagnostics: Mapping[str, object]

    def to_dict(self) -> dict:
        return {
            "disposition": self.disposition.to_dict(),
            "diagnostics": dict(self.diagnostics),
        }


def build_external_disposition(
    physiology: Physiology,
    inputs: ExternalDispositionInputs,
) -> DispositionBuildResult:
    physiology.validate()
    inputs.validate()

    tissue_names = set(physiology.tissue_map)
    supplied = set(inputs.tissue_partition_coefficients)
    if supplied != tissue_names:
        missing = tissue_names - supplied
        extra = supplied - tissue_names
        raise ValueError(
            f"partition tissue mismatch: missing={sorted(missing)} extra={sorted(extra)}"
        )

    partitions = convert_partition_map(
        inputs.tissue_partition_coefficients,
        basis=inputs.partition_basis,
        fu_plasma=inputs.fu_plasma,
    )

    brain_override = None
    if inputs.kp_uu_brain is not None:
        brain_override = brain_total_kp_from_kpuu(
            inputs.kp_uu_brain,
            fu_plasma=inputs.fu_plasma,
            fu_brain=inputs.fu_brain,
        )
        partitions["brain"] = brain_override

    disposition = CompoundDisposition(
        label=inputs.label,
        tissue_partition_coefficients=partitions,
        hepatic_clearance_l_per_h=inputs.tissue_based_hepatic_clearance_l_per_h,
        renal_clearance_l_per_h=inputs.tissue_based_renal_clearance_l_per_h,
        plasma_unbound_fraction=inputs.fu_plasma,
        brain_unbound_fraction=inputs.fu_brain,
        evidence_status="external_prediction_or_measurement",
        source_ids=(inputs.source_id,),
    )
    disposition.validate(tissue_names)

    fu_blood = blood_unbound_fraction(
        fu_plasma=inputs.fu_plasma,
        blood_to_plasma_ratio=inputs.blood_to_plasma_ratio,
    )

    hepatic_reference = None
    if inputs.intrinsic_hepatic_clearance_l_per_h is not None:
        hepatic_reference = well_stirred_hepatic_clearance(
            hepatic_blood_flow_l_per_h=physiology.tissue_map["liver"].blood_flow_l_per_h,
            intrinsic_clearance_l_per_h=inputs.intrinsic_hepatic_clearance_l_per_h,
            fu_blood=fu_blood,
        ).to_dict()

    renal_reference = None
    if inputs.gfr_l_per_h is not None:
        renal_reference = filtration_only_renal_clearance(
            gfr_l_per_h=inputs.gfr_l_per_h,
            fu_plasma=inputs.fu_plasma,
        ).to_dict()

    diagnostics = {
        "source_id": inputs.source_id,
        "method": inputs.method,
        "input_partition_basis": PartitionBasis(inputs.partition_basis).value,
        "normalized_partition_basis": PartitionBasis.TISSUE_TO_PLASMA.value,
        "fu_plasma": inputs.fu_plasma,
        "fu_brain": inputs.fu_brain,
        "blood_to_plasma_ratio": inputs.blood_to_plasma_ratio,
        "derived_fu_blood": fu_blood,
        "kp_uu_brain": inputs.kp_uu_brain,
        "brain_kp_override": brain_override,
        "well_stirred_hepatic_reference": hepatic_reference,
        "filtration_only_renal_reference": renal_reference,
        "clearance_basis_warning": (
            "Reference hepatic/renal clearances are not automatically copied into "
            "the legacy PBPK tissue-concentration elimination fields."
        ),
    }
    return DispositionBuildResult(disposition=disposition, diagnostics=diagnostics)
