"""Mechanistic disposition conversions and reference-clearance equations.

These functions are deliberately small and independently testable.

Important concentration-basis distinction:
- HumanSim PBPK currently applies its legacy hepatic/renal clearance fields to tissue
  concentration inside the organ compartments.
- The well-stirred hepatic clearance below is defined relative to blood delivery.
- Therefore this module DOES NOT silently map well-stirred CLh into the legacy tissue
  elimination field.

That mapping requires a future organ-elimination refactor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping


class PartitionBasis(str, Enum):
    TISSUE_TO_PLASMA = "tissue_to_plasma"
    TISSUE_TO_UNBOUND_PLASMA = "tissue_to_unbound_plasma"


@dataclass(frozen=True)
class ClearanceResult:
    clearance_l_per_h: float
    extraction_ratio: float
    model: str

    def to_dict(self) -> dict:
        return asdict(self)


def tissue_partition_to_plasma(
    value: float,
    *,
    basis: PartitionBasis | str,
    fu_plasma: float,
) -> float:
    """Convert a tissue partition coefficient to total tissue:total plasma Kp.

    httk/Schmitt commonly reports Ktissue2pu = Ctissue / Cu,plasma.
    Since Cu,plasma = fu_plasma * Cplasma:

        Kp_tissue:plasma = Ktissue2pu * fu_plasma
    """

    basis = PartitionBasis(basis)
    if value <= 0:
        raise ValueError("partition coefficient must be positive")
    if not 0.0 < fu_plasma <= 1.0:
        raise ValueError("fu_plasma must be in (0,1]")

    if basis is PartitionBasis.TISSUE_TO_PLASMA:
        return float(value)
    return float(value * fu_plasma)


def convert_partition_map(
    values: Mapping[str, float],
    *,
    basis: PartitionBasis | str,
    fu_plasma: float,
) -> dict[str, float]:
    if not values:
        raise ValueError("partition map cannot be empty")
    return {
        name: tissue_partition_to_plasma(
            value,
            basis=basis,
            fu_plasma=fu_plasma,
        )
        for name, value in values.items()
    }


def brain_total_kp_from_kpuu(
    kp_uu_brain: float,
    *,
    fu_plasma: float,
    fu_brain: float,
) -> float:
    """Convert unbound brain:plasma ratio to total brain:plasma Kp.

    Kp,uu,brain = Cu,brain / Cu,plasma
                 = Kp,brain * fu_brain / fu_plasma

    therefore:
        Kp,brain = Kp,uu,brain * fu_plasma / fu_brain
    """

    if kp_uu_brain < 0:
        raise ValueError("kp_uu_brain cannot be negative")
    if not 0.0 < fu_plasma <= 1.0:
        raise ValueError("fu_plasma must be in (0,1]")
    if not 0.0 < fu_brain <= 1.0:
        raise ValueError("fu_brain must be in (0,1]")
    return float(kp_uu_brain * fu_plasma / fu_brain)


def blood_unbound_fraction(
    *,
    fu_plasma: float,
    blood_to_plasma_ratio: float,
) -> float:
    """Convert plasma free fraction to whole-blood free fraction.

    Assuming the same unbound concentration is referenced:
        fu_blood = fu_plasma / (Cblood / Cplasma)
    """

    if not 0.0 < fu_plasma <= 1.0:
        raise ValueError("fu_plasma must be in (0,1]")
    if blood_to_plasma_ratio <= 0:
        raise ValueError("blood_to_plasma_ratio must be positive")
    value = fu_plasma / blood_to_plasma_ratio
    if value > 1.0 + 1e-12:
        raise ValueError("derived fu_blood exceeds 1; check binding/B:P inputs")
    return float(min(value, 1.0))


def well_stirred_hepatic_clearance(
    *,
    hepatic_blood_flow_l_per_h: float,
    intrinsic_clearance_l_per_h: float,
    fu_blood: float,
) -> ClearanceResult:
    """Classic well-stirred hepatic clearance reference equation.

        CLh = Qh * fu_b * CLint / (Qh + fu_b * CLint)

    CLint must already be scaled to the same whole-organ L/h basis. This function
    performs no microsomal/hepatocyte scaling.
    """

    if hepatic_blood_flow_l_per_h <= 0:
        raise ValueError("hepatic blood flow must be positive")
    if intrinsic_clearance_l_per_h < 0:
        raise ValueError("intrinsic clearance cannot be negative")
    if not 0.0 < fu_blood <= 1.0:
        raise ValueError("fu_blood must be in (0,1]")

    q = hepatic_blood_flow_l_per_h
    capacity = fu_blood * intrinsic_clearance_l_per_h
    clearance = q * capacity / (q + capacity) if capacity > 0 else 0.0
    return ClearanceResult(
        clearance_l_per_h=float(clearance),
        extraction_ratio=float(clearance / q),
        model="well_stirred_reference",
    )


def filtration_only_renal_clearance(
    *,
    gfr_l_per_h: float,
    fu_plasma: float,
) -> ClearanceResult:
    """Glomerular-filtration-only renal reference.

        CLrenal,filtration = GFR * fu_plasma

    This deliberately excludes active secretion and tubular reabsorption.
    """

    if gfr_l_per_h < 0:
        raise ValueError("gfr_l_per_h cannot be negative")
    if not 0.0 < fu_plasma <= 1.0:
        raise ValueError("fu_plasma must be in (0,1]")

    clearance = gfr_l_per_h * fu_plasma
    return ClearanceResult(
        clearance_l_per_h=float(clearance),
        extraction_ratio=float(clearance / gfr_l_per_h) if gfr_l_per_h else 0.0,
        model="glomerular_filtration_only_reference",
    )
