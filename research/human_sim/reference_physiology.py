"""Literature-reference physiology composite and sanity audit.

This module is deliberately NOT a covariance model and NOT an individualized patient.
It combines published reference means into the reduced HumanSim topology so imported
virtual populations can be sanity-checked without replacing their native correlations.

Where a value is derived or model-reduced, that status is explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from research.human_sim.physiology import Physiology, TissueSpec
from research.human_sim.provenance import sources_dict


@dataclass(frozen=True)
class ReferenceQuantity:
    name: str
    value: float
    units: str
    source_ids: tuple[str, ...]
    derivation: str = ""
    evidence_status: str = "literature_reference"

    def to_dict(self) -> dict:
        value = asdict(self)
        value["source_ids"] = list(self.source_ids)
        return value


@dataclass(frozen=True)
class ReferencePhysiology:
    physiology: Physiology
    cardiac_output_l_per_h: float
    quantities: Mapping[str, ReferenceQuantity]

    def to_dict(self) -> dict:
        return {
            "physiology": self.physiology.to_dict(),
            "cardiac_output_l_per_h": self.cardiac_output_l_per_h,
            "quantities": {
                name: quantity.to_dict()
                for name, quantity in self.quantities.items()
            },
            "sources": sources_dict(
                ["icrp89", "atsdr_mann_pbpk", "lassen1985_cbf", "brown1997_pbpk"]
            ),
        }


@dataclass(frozen=True)
class PhysiologySanityReport:
    ratios_to_reference: Mapping[str, float]
    total_flow_l_per_h: float
    reference_cardiac_output_l_per_h: float
    total_flow_ratio: float
    broad_screen_flags: tuple[str, ...]

    @property
    def passed_broad_screen(self) -> bool:
        return not self.broad_screen_flags

    def to_dict(self) -> dict:
        return {
            "ratios_to_reference": dict(self.ratios_to_reference),
            "total_flow_l_per_h": self.total_flow_l_per_h,
            "reference_cardiac_output_l_per_h": self.reference_cardiac_output_l_per_h,
            "total_flow_ratio": self.total_flow_ratio,
            "broad_screen_flags": list(self.broad_screen_flags),
            "passed_broad_screen": self.passed_broad_screen,
        }


def adult_male_reference_composite() -> ReferencePhysiology:
    """Reduced adult-male reference assembled from cited sources.

    Source-backed components:
      - blood volume: 5.222 L (ATSDR/Mann table)
      - cardiac output: 5.29 L/min (ATSDR/Mann table)
      - liver flow: 0.32 + 1.02 L/min (hepatic + splanchnic)
      - kidney flow: 0.95 L/min
      - adult male brain mass: 1.450 kg (ICRP 89)
      - brain specific gravity: about 1.04 (ICRP 89)
      - global cerebral flow: about 50 mL/100 g/min (Lassen)

    Reduced-model assumptions:
      - liver/kidney densities are 1.05 kg/L, consistent with ICRP-based phantom use;
      - residual 'peripheral' volume uses the Mann table's 'Others' mass as a
        1 kg/L lump;
      - peripheral flow is the residual required to reconcile regional systemic
        flows with the 5.29 L/min cardiac-output reference.
    """

    central_volume_l = 5.222

    brain_mass_kg = 1.450
    brain_density_kg_per_l = 1.04
    brain_volume_l = brain_mass_kg / brain_density_kg_per_l

    liver_mass_kg = 1.800
    liver_density_kg_per_l = 1.05
    liver_volume_l = liver_mass_kg / liver_density_kg_per_l

    kidney_mass_kg = 0.310
    kidney_density_kg_per_l = 1.05
    kidney_volume_l = kidney_mass_kg / kidney_density_kg_per_l

    peripheral_volume_l = 55.277

    cardiac_output_l_per_min = 5.29
    brain_flow_l_per_min = 0.050 * (brain_mass_kg * 1000.0 / 100.0)
    liver_flow_l_per_min = 0.32 + 1.02
    kidney_flow_l_per_min = 0.95
    peripheral_flow_l_per_min = (
        cardiac_output_l_per_min
        - brain_flow_l_per_min
        - liver_flow_l_per_min
        - kidney_flow_l_per_min
    )
    if peripheral_flow_l_per_min <= 0:
        raise RuntimeError("reference residual peripheral flow is not positive")

    physiology = Physiology(
        central_volume_l=central_volume_l,
        tissues=(
            TissueSpec("brain", brain_volume_l, brain_flow_l_per_min * 60.0),
            TissueSpec("liver", liver_volume_l, liver_flow_l_per_min * 60.0),
            TissueSpec("kidney", kidney_volume_l, kidney_flow_l_per_min * 60.0),
            TissueSpec("peripheral", peripheral_volume_l, peripheral_flow_l_per_min * 60.0),
        ),
        label="LITERATURE_REFERENCE_ADULT_MALE_REDUCED",
        evidence_status="literature_reference_plus_explicit_reduction",
        source_ids=("icrp89", "atsdr_mann_pbpk", "lassen1985_cbf", "brown1997_pbpk"),
    )
    physiology.validate()

    quantities = {
        "central_volume_l": ReferenceQuantity(
            "central_volume_l", central_volume_l, "L", ("atsdr_mann_pbpk",)
        ),
        "brain_volume_l": ReferenceQuantity(
            "brain_volume_l", brain_volume_l, "L", ("icrp89",),
            derivation="1.450 kg / 1.04 kg/L",
        ),
        "liver_volume_l": ReferenceQuantity(
            "liver_volume_l", liver_volume_l, "L", ("icrp89",),
            derivation="1.800 kg / 1.05 kg/L",
        ),
        "kidney_volume_l": ReferenceQuantity(
            "kidney_volume_l", kidney_volume_l, "L", ("icrp89",),
            derivation="0.310 kg / 1.05 kg/L",
        ),
        "peripheral_volume_l": ReferenceQuantity(
            "peripheral_volume_l", peripheral_volume_l, "L", ("atsdr_mann_pbpk",),
            derivation="Mann 'Others' mass used as a 1 kg/L reduced lump",
            evidence_status="model_reduction_assumption",
        ),
        "cardiac_output_l_per_h": ReferenceQuantity(
            "cardiac_output_l_per_h", cardiac_output_l_per_min * 60.0, "L/h",
            ("atsdr_mann_pbpk",),
            derivation="5.29 L/min * 60",
        ),
        "brain_flow_l_per_h": ReferenceQuantity(
            "brain_flow_l_per_h", brain_flow_l_per_min * 60.0, "L/h",
            ("icrp89", "lassen1985_cbf"),
            derivation="50 mL/100 g/min * 1450 g",
        ),
        "liver_flow_l_per_h": ReferenceQuantity(
            "liver_flow_l_per_h", liver_flow_l_per_min * 60.0, "L/h",
            ("atsdr_mann_pbpk",),
            derivation="(0.32 hepatic + 1.02 splanchnic) L/min * 60",
        ),
        "kidney_flow_l_per_h": ReferenceQuantity(
            "kidney_flow_l_per_h", kidney_flow_l_per_min * 60.0, "L/h",
            ("atsdr_mann_pbpk",),
            derivation="0.95 L/min * 60",
        ),
        "peripheral_flow_l_per_h": ReferenceQuantity(
            "peripheral_flow_l_per_h", peripheral_flow_l_per_min * 60.0, "L/h",
            ("atsdr_mann_pbpk", "brown1997_pbpk"),
            derivation="cardiac output minus explicit brain/liver/kidney flows",
            evidence_status="model_reduction_derived",
        ),
    }

    return ReferencePhysiology(
        physiology=physiology,
        cardiac_output_l_per_h=cardiac_output_l_per_min * 60.0,
        quantities=quantities,
    )


def audit_physiology_against_reference(
    physiology: Physiology,
    *,
    reference: ReferencePhysiology | None = None,
    broad_lower_ratio: float = 0.5,
    broad_upper_ratio: float = 1.5,
) -> PhysiologySanityReport:
    """Very broad outlier screen, not a physiological normal-range classifier."""

    physiology.validate()
    reference = reference or adult_male_reference_composite()
    if broad_lower_ratio <= 0 or broad_upper_ratio <= broad_lower_ratio:
        raise ValueError("invalid broad-screen ratios")

    ratios = {
        "central_volume": physiology.central_volume_l / reference.physiology.central_volume_l,
    }
    for name in ("brain", "liver", "kidney", "peripheral"):
        ratios[f"{name}_volume"] = (
            physiology.tissue_map[name].volume_l
            / reference.physiology.tissue_map[name].volume_l
        )
        ratios[f"{name}_flow"] = (
            physiology.tissue_map[name].blood_flow_l_per_h
            / reference.physiology.tissue_map[name].blood_flow_l_per_h
        )

    total_flow = physiology.total_tissue_flow_l_per_h
    total_flow_ratio = total_flow / reference.cardiac_output_l_per_h

    flags = [
        f"{name} ratio={ratio:.3f}"
        for name, ratio in ratios.items()
        if ratio < broad_lower_ratio or ratio > broad_upper_ratio
    ]
    if total_flow_ratio < broad_lower_ratio or total_flow_ratio > broad_upper_ratio:
        flags.append(f"total_flow ratio={total_flow_ratio:.3f}")

    return PhysiologySanityReport(
        ratios_to_reference=ratios,
        total_flow_l_per_h=total_flow,
        reference_cardiac_output_l_per_h=reference.cardiac_output_l_per_h,
        total_flow_ratio=total_flow_ratio,
        broad_screen_flags=tuple(flags),
    )
