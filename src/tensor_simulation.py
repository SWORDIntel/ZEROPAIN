#!/usr/bin/env python3
"""
ZeroPain High-Performance PyTorch/CUDA Vectorized Simulation Engine
===================================================================

Massive-scale population simulation engine capable of running 10,000,000 (10M)
virtual patient trials with expanded pharmacogenomics (PGx), polysubstance
and street adulterant dynamics, multi-organ impairment, and dynamic receptor
kinetics (NOP dopamine clamp, tolerance hysteresis, ABCB1 metabolite efflux).

Architecture:
- Device: Auto-detects NVIDIA CUDA (Nebius H100 / L40S) with seamless CPU fallback.
- Scalability: Memory-efficient batched execution (250k - 1M patients per chunk).
- Streaming Analytics: Online quantile estimation (p50, p90, p99, p99.9, p99.99),
  real-time mortality, overdose, withdrawal, addiction, and adverse event counters.
- Vectorized Pharmacology: Multi-ligand competitive receptor binding, non-linear
  tissue distribution, portosystemic shunts, arterial blood gas kinetics, and hERG safety.
"""

from __future__ import annotations

import math
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Union, Any, Callable
from pathlib import Path

import torch

logger = logging.getLogger("zeropain.tensor_simulation")


# ============================================================================
# Device and Hardware Detection
# ============================================================================

def detect_device(requested_device: Optional[str] = None) -> torch.device:
    """
    Auto-detect the most optimal hardware device.
    Supports NVIDIA CUDA (e.g. Nebius H100, L40S, A100) with robust fallback to CPU.
    """
    if requested_device:
        return torch.device(requested_device)

    if torch.cuda.is_available():
        try:
            # Perform a test allocation to ensure CUDA driver/runtime integrity
            test_tensor = torch.zeros((4, 4), device="cuda", dtype=torch.float32)
            del test_tensor
            return torch.device("cuda")
        except Exception as e:
            logger.warning("CUDA reported available but probe allocation failed: %s. Falling back to CPU.", e)
            return torch.device("cpu")
    return torch.device("cpu")


# ============================================================================
# Pharmacological Compound Specifications
# ============================================================================

@dataclass
class TensorCompoundProfile:
    """Vector-ready pharmacological profile of an opioid, adjunct, or adulterant."""
    name: str
    ki_mor: float = float("inf")          # nM - MOR affinity
    ki_dor: float = float("inf")          # nM - DOR affinity
    ki_kor: float = float("inf")          # nM - KOR affinity
    ki_nop: float = float("inf")          # nM - NOP (nociceptin) affinity
    ki_alpha2: float = float("inf")       # nM - Alpha-2 adrenergic affinity (xylazine)
    g_protein_bias: float = 1.0           # G-protein pathway bias multiplier
    beta_arrestin_bias: float = 1.0       # Beta-arrestin2 pathway bias multiplier
    intrinsic_activity: float = 1.0       # Receptor activation efficacy (0.0 to 1.0)
    t_half: float = 4.0                   # Elimination half-life (hours)
    bioavailability: float = 0.5          # Baseline oral/sublingual bioavailability (0.0 to 1.0)
    lipophilicity: float = 1.0            # Vd adipose scaling factor (0.5 to 5.0)
    cyp3a4_fraction: float = 0.5          # Proportion of hepatic clearance via CYP3A4
    cyp2d6_fraction: float = 0.3          # Proportion of hepatic clearance via CYP2D6
    ugt2b7_fraction: float = 0.2          # Proportion of hepatic clearance via UGT2B7
    renal_fraction: float = 0.1           # Proportion of total clearance via renal excretion
    herg_ic50_uM: float = 100.0           # hERG potassium channel IC50 (uM) -> cardiac QTc risk
    reverses_tolerance: bool = False      # Actively promotes MOR resensitization
    prevents_withdrawal: bool = False     # Blunts precipitate/spontaneous withdrawal
    is_adulterant: bool = False           # Flag for toxic adulterants
    mw: float = 400.0                     # Molecular weight (g/mol) for molar biophase conversion
    unbound_fraction: float = 0.10        # Free fraction in plasma available to cross BBB (fu)
    v_dist_base: float = 1.5              # Baseline volume of distribution (L/kg)
    mechanism_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Built-in catalog of standard, therapeutic, experimental, and street compounds
COMPOUND_REGISTRY: Dict[str, TensorCompoundProfile] = {
    # Lead therapeutic candidates
    "SR-16435": TensorCompoundProfile(
        name="SR-16435",
        ki_mor=4.0,
        ki_nop=8.5,
        g_protein_bias=5.0,
        beta_arrestin_bias=0.2,
        intrinsic_activity=0.45,
        t_half=8.0,
        bioavailability=0.60,
        lipophilicity=1.2,
        mw=420.0,
        unbound_fraction=0.12,
        v_dist_base=1.6,
        cyp3a4_fraction=0.5,
        cyp2d6_fraction=0.5,
        ugt2b7_fraction=0.0,
        renal_fraction=0.1,
        herg_ic50_uM=85.0,
        reverses_tolerance=False,
        prevents_withdrawal=True,
        mechanism_notes="Bifunctional MOR partial agonist / NOP agonist; VTA dopamine ceiling and addiction block.",
    ),
    "SR-14968": TensorCompoundProfile(
        name="SR-14968",
        ki_mor=10.0,
        g_protein_bias=10.0,
        beta_arrestin_bias=0.1,
        intrinsic_activity=0.65,
        t_half=12.0,
        bioavailability=0.80,
        lipophilicity=1.1,
        mw=400.0,
        unbound_fraction=0.10,
        v_dist_base=1.4,
        cyp3a4_fraction=0.6,
        cyp2d6_fraction=0.4,
        ugt2b7_fraction=0.0,
        renal_fraction=0.15,
        herg_ic50_uM=60.0,
        reverses_tolerance=True,
        prevents_withdrawal=True,
        mechanism_notes="G-protein biased MOR agonist with active receptor resensitization and tolerance reversal.",
    ),
    "SR-14968-M": TensorCompoundProfile(
        name="SR-14968-M",
        ki_mor=10.0,
        g_protein_bias=10.0,
        beta_arrestin_bias=0.1,
        intrinsic_activity=0.65,
        t_half=12.0,
        bioavailability=0.80,
        lipophilicity=1.1,
        mw=416.0,
        unbound_fraction=0.10,
        v_dist_base=1.4,
        cyp3a4_fraction=0.6,
        cyp2d6_fraction=0.4,
        ugt2b7_fraction=0.0,
        renal_fraction=0.15,
        herg_ic50_uM=60.0,
        reverses_tolerance=True,
        prevents_withdrawal=True,
        mechanism_notes="Active metabolite of SR-14968; robust resensitization and withdrawal protection.",
    ),
    "SR-17018": TensorCompoundProfile(
        name="SR-17018",
        ki_mor=26.0,
        g_protein_bias=8.2,
        beta_arrestin_bias=0.01,
        intrinsic_activity=0.38,
        t_half=7.0,
        bioavailability=0.70,
        lipophilicity=1.1,
        mw=410.0,
        unbound_fraction=0.12,
        v_dist_base=1.5,
        cyp3a4_fraction=0.8,
        cyp2d6_fraction=0.2,
        ugt2b7_fraction=0.0,
        renal_fraction=0.1,
        herg_ic50_uM=75.0,
        reverses_tolerance=True,
        prevents_withdrawal=True,
        mechanism_notes="Biased MOR ligand restoring morphine sensitivity.",
    ),

    # Clinical reference opioids
    "Buprenorphine": TensorCompoundProfile(
        name="Buprenorphine",
        ki_mor=0.20,
        ki_dor=1.0,
        ki_kor=0.50,
        ki_nop=70.0,
        g_protein_bias=1.5,
        beta_arrestin_bias=0.8,
        intrinsic_activity=0.35,
        t_half=37.0,
        bioavailability=0.20,
        lipophilicity=2.5,
        mw=467.6,
        unbound_fraction=0.04,
        v_dist_base=3.5,
        cyp3a4_fraction=0.45,
        cyp2d6_fraction=0.05,
        ugt2b7_fraction=0.50,
        renal_fraction=0.10,
        herg_ic50_uM=45.0,
        reverses_tolerance=False,
        prevents_withdrawal=True,
        mechanism_notes="High affinity partial MOR agonist / KOR antagonist; shunted via UGT2B7 (B3G) and CYP3A4 (Norbuprenorphine).",
    ),
    "Levorphanol": TensorCompoundProfile(
        name="Levorphanol",
        ki_mor=0.225,
        ki_dor=2.4,
        ki_kor=4.2,
        g_protein_bias=1.0,
        beta_arrestin_bias=1.0,
        intrinsic_activity=0.90,
        t_half=14.0,
        bioavailability=0.50,
        lipophilicity=1.3,
        mw=257.4,
        unbound_fraction=0.60,
        v_dist_base=1.3,
        cyp3a4_fraction=0.40,
        cyp2d6_fraction=0.40,
        ugt2b7_fraction=0.20,
        renal_fraction=0.10,
        herg_ic50_uM=80.0,
        reverses_tolerance=False,
        prevents_withdrawal=True,
        mechanism_notes="Quad-action MOR agonist with non-competitive NMDA receptor block and SNRI activity.",
    ),
    "Morphine": TensorCompoundProfile(
        name="Morphine",
        ki_mor=1.8,
        ki_dor=90.0,
        ki_kor=120.0,
        g_protein_bias=1.0,
        beta_arrestin_bias=1.0,
        intrinsic_activity=1.0,
        t_half=3.0,
        bioavailability=0.30,
        lipophilicity=0.8,
        mw=285.3,
        unbound_fraction=0.65,
        v_dist_base=3.0,
        cyp3a4_fraction=0.05,
        cyp2d6_fraction=0.05,
        ugt2b7_fraction=0.80,
        renal_fraction=0.10,
        herg_ic50_uM=100.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        mechanism_notes="Standard MOR full agonist; metabolized to M6G (analgesic) and M3G (neurotoxic).",
    ),
    "Fentanyl": TensorCompoundProfile(
        name="Fentanyl",
        ki_mor=0.39,
        g_protein_bias=1.0,
        beta_arrestin_bias=1.2,
        intrinsic_activity=1.0,
        t_half=3.7,
        bioavailability=0.50,
        lipophilicity=3.5,
        mw=336.5,
        unbound_fraction=0.16,
        v_dist_base=4.0,
        cyp3a4_fraction=0.90,
        cyp2d6_fraction=0.05,
        ugt2b7_fraction=0.0,
        renal_fraction=0.05,
        herg_ic50_uM=30.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        mechanism_notes="Potent, highly lipophilic MOR full agonist with high beta-arrestin and respiratory depression.",
    ),
    "Methadone": TensorCompoundProfile(
        name="Methadone",
        ki_mor=0.80,
        g_protein_bias=1.2,
        beta_arrestin_bias=0.8,
        intrinsic_activity=1.0,
        t_half=24.0,
        bioavailability=0.85,
        lipophilicity=2.8,
        mw=309.4,
        unbound_fraction=0.12,
        v_dist_base=4.0,
        cyp3a4_fraction=0.70,
        cyp2d6_fraction=0.30,
        ugt2b7_fraction=0.0,
        renal_fraction=0.20,
        herg_ic50_uM=2.0,
        reverses_tolerance=False,
        prevents_withdrawal=True,
        mechanism_notes="Long-acting MOR agonist and NMDA blocker; potent hERG inhibitor causing QTc prolongation.",
    ),
    "Oxycodone": TensorCompoundProfile(
        name="Oxycodone",
        ki_mor=16.0,
        g_protein_bias=1.0,
        beta_arrestin_bias=1.0,
        intrinsic_activity=0.85,
        t_half=3.5,
        bioavailability=0.65,
        lipophilicity=1.1,
        mw=315.4,
        unbound_fraction=0.55,
        v_dist_base=2.6,
        cyp3a4_fraction=0.50,
        cyp2d6_fraction=0.45,
        ugt2b7_fraction=0.05,
        renal_fraction=0.15,
        herg_ic50_uM=90.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
    ),

    # Street adulterants & lethal synthetic analogues
    "Carfentanil": TensorCompoundProfile(
        name="Carfentanil",
        ki_mor=0.02,
        g_protein_bias=0.9,
        beta_arrestin_bias=1.6,
        intrinsic_activity=1.0,
        t_half=8.0,
        bioavailability=0.50,
        lipophilicity=4.8,
        cyp3a4_fraction=0.95,
        cyp2d6_fraction=0.05,
        ugt2b7_fraction=0.0,
        renal_fraction=0.02,
        herg_ic50_uM=15.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        is_adulterant=True,
        mechanism_notes="Ultra-potent synthetic opioid (10,000x morphine); massive lipophilic tissue depot and refractory respiratory depression.",
    ),
    "Xylazine": TensorCompoundProfile(
        name="Xylazine",
        ki_mor=float("inf"),
        ki_alpha2=15.0,
        g_protein_bias=1.0,
        beta_arrestin_bias=0.8,
        intrinsic_activity=0.90,
        t_half=0.8,
        bioavailability=0.85,
        lipophilicity=1.4,
        cyp3a4_fraction=0.70,
        cyp2d6_fraction=0.10,
        ugt2b7_fraction=0.0,
        renal_fraction=0.20,
        herg_ic50_uM=50.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        is_adulterant=True,
        mechanism_notes="Alpha-2 adrenergic agonist ('tranq'); induces profound bradycardia, hypotension, and synergistic respiratory collapse. Non-naloxone reversible.",
    ),
    "Isotonitazene": TensorCompoundProfile(
        name="Isotonitazene",
        ki_mor=0.0015,
        g_protein_bias=0.6,
        beta_arrestin_bias=2.4,
        intrinsic_activity=1.0,
        t_half=4.0,
        bioavailability=0.50,
        lipophilicity=3.0,
        cyp3a4_fraction=0.85,
        cyp2d6_fraction=0.15,
        ugt2b7_fraction=0.0,
        renal_fraction=0.05,
        herg_ic50_uM=20.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        is_adulterant=True,
        mechanism_notes="Novel synthetic benzimidazole opioid (nitazene class); 500x morphine potency, severe beta-arrestin recruitment, rapid tolerance, and extreme overdose fatality.",
    ),
    "Nitazene": TensorCompoundProfile(
        name="Nitazene",
        ki_mor=0.0015,
        g_protein_bias=0.6,
        beta_arrestin_bias=2.4,
        t_half=4.0,
        bioavailability=0.50,
        intrinsic_activity=1.0,
        lipophilicity=3.0,
        cyp3a4_fraction=0.85,
        cyp2d6_fraction=0.15,
        ugt2b7_fraction=0.0,
        renal_fraction=0.05,
        herg_ic50_uM=20.0,
        reverses_tolerance=False,
        prevents_withdrawal=False,
        is_adulterant=True,
        mechanism_notes="Synthetic 2-benzylbenzimidazole opioid class.",
    ),
}


# ============================================================================
# Cohort and Trial Configuration
# ============================================================================

@dataclass
class CohortConfig:
    """
    Cohort parameters controlling demographic, genetic, organ impairment,
    polysubstance co-exposure, and behavioral compliance distributions.
    """
    name: str = "standard"
    description: str = "Standard representative clinical trial cohort."

    # Demographic distributions
    sex_ratio_male: float = 0.50
    age_beta_a: float = 2.0
    age_beta_b: float = 3.0
    age_min: float = 18.0
    age_max: float = 85.0

    # Body composition & Anatomical extremes
    bmi_mean: float = 28.0
    bmi_sigma: float = 6.0
    cachexia_rate: float = 0.02          # BMI < 16, hypoalbuminemia
    morbid_obesity_rate: float = 0.05    # BMI > 50, massive adipose depot

    # Pharmacogenomics (PGx) Frequencies
    # UGT2B7 (Glucuronidation of buprenorphine to B3G)
    ugt2b7_poor_rate: float = 0.10       # Activity 0.35
    ugt2b7_rapid_rate: float = 0.25      # Activity 1.75
    # ABCB1 / MDR1 (P-gp BBB efflux pump)
    abcb1_deficient_rate: float = 0.10   # Activity 0.25 (Norbuprenorphine crosses BBB)
    abcb1_intermediate_rate: float = 0.30 # Activity 0.65
    # CYP2D6 (PM, IM, NM, UM)
    cyp2d6_pm_rate: float = 0.08
    cyp2d6_im_rate: float = 0.32
    cyp2d6_um_rate: float = 0.08
    # CYP3A4 (PM, IM, NM, UM)
    cyp3a4_pm_rate: float = 0.02
    cyp3a4_im_rate: float = 0.10
    cyp3a4_um_rate: float = 0.08
    # CYP2C19 & CYP2C9
    cyp2c19_pm_rate: float = 0.05
    cyp2c9_pm_rate: float = 0.06
    # OPRM1 A118G (rs1799971)
    oprm1_ag_rate: float = 0.26          # Heterozygote (reduced MOR signaling)
    oprm1_gg_rate: float = 0.04          # Homozygote (blunted euphoria, dose escalation)
    # COMT Val158Met (rs4680)
    comt_val_val_rate: float = 0.25      # Rapid DA clearance, high pain sensitivity, addiction seeking
    comt_met_met_rate: float = 0.25      # Slow DA clearance, low pain sensitivity

    # Multi-Organ Impairment Prevalences
    # Hepatic failure (Child-Pugh & MELD, portosystemic shunts)
    child_pugh_a_rate: float = 0.05
    child_pugh_b_rate: float = 0.03
    child_pugh_c_rate: float = 0.015
    # Renal failure (CKD stages & ESRD hemodialysis)
    ckd_stage2_rate: float = 0.15
    ckd_stage3_rate: float = 0.08
    ckd_stage4_rate: float = 0.03
    ckd_stage5_esrd_rate: float = 0.015
    # Pulmonary reserve (COPD GOLD 1-4 & Sleep Apnea)
    copd_gold1_rate: float = 0.08
    copd_gold2_rate: float = 0.06
    copd_gold3_rate: float = 0.03
    copd_gold4_rate: float = 0.01
    sleep_apnea_rate: float = 0.12

    # Polysubstance & Street Adulterant Exposure Rates
    street_fentanyl_rate: float = 0.00
    street_fentanyl_dose_mg: float = 1.0
    carfentanil_rate: float = 0.00
    carfentanil_dose_ug: float = 20.0
    xylazine_rate: float = 0.00
    xylazine_dose_mg: float = 50.0
    nitazene_rate: float = 0.00
    nitazene_dose_mg: float = 0.5
    alcohol_rate: float = 0.05           # Acute BAC > 0.08 g/dL
    benzo_rate: float = 0.08             # Diazepam / Alprazolam
    gabapentinoid_rate: float = 0.12     # Gabapentin / Pregabalin
    ssri_rate: float = 0.18              # CYP2D6 inhibitor
    antipsychotic_rate: float = 0.05     # QTc burden

    # Behavioral Compliance Mechanics
    compliance_rate: float = 0.90        # Probability of full protocol compliance
    weekend_binge_rate: float = 0.05     # Taking 2x dose on Friday/Saturday
    missed_dose_prob: float = 0.05       # Randomly skipping dose
    abrupt_cessation_challenge: bool = False # Stop dosing abruptly at cessation_day

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CohortConfig:
        """Create a CohortConfig from a dictionary with automatic alias translation."""
        import dataclasses
        alias_map = {
            "pgx_ugt2b7_poor_rate": "ugt2b7_poor_rate",
            "pgx_cyp2d6_poor_rate": "cyp2d6_pm_rate",
            "pgx_cyp3a4_poor_rate": "cyp3a4_pm_rate",
            "pgx_oprm1_a118g_rate": "oprm1_ag_rate",
            "pgx_comt_met_rate": "comt_met_met_rate",
            "pgx_abcb1_efflux_loss": "abcb1_deficient_rate",
            "ckd_stage_5_rate": "ckd_stage5_esrd_rate",
            "copd_severe_rate": "copd_gold4_rate",
        }
        preset_name = data.get("cohort", data.get("name", "standard"))
        base_cfg = COHORT_PRESETS.get(preset_name, cls())
        base_dict = base_cfg.to_dict()

        valid_fields = {f.name for f in dataclasses.fields(cls)}
        for k, v in data.items():
            if v is None:
                continue
            canonical = alias_map.get(k, k)
            if canonical in valid_fields:
                base_dict[canonical] = v
        return cls(**base_dict)


# Standard Cohort Presets
COHORT_PRESETS: Dict[str, CohortConfig] = {
    "standard": CohortConfig(
        name="standard",
        description="General outpatient clinical cohort with natural population diversity.",
    ),
    "polysubstance_crisis": CohortConfig(
        name="polysubstance_crisis",
        description="High-risk cohort exposed to street opioids, alcohol, and CNS depressants.",
        street_fentanyl_rate=0.45,
        street_fentanyl_dose_mg=1.5,
        xylazine_rate=0.35,
        xylazine_dose_mg=60.0,
        alcohol_rate=0.40,
        benzo_rate=0.35,
        gabapentinoid_rate=0.25,
        compliance_rate=0.70,
        weekend_binge_rate=0.20,
        missed_dose_prob=0.15,
    ),
    "multi_organ_failure": CohortConfig(
        name="multi_organ_failure",
        description="Severe hepatic, renal, and pulmonary disease cohort with anatomical extremes.",
        cachexia_rate=0.15,
        morbid_obesity_rate=0.20,
        child_pugh_a_rate=0.20,
        child_pugh_b_rate=0.25,
        child_pugh_c_rate=0.15,
        ckd_stage2_rate=0.20,
        ckd_stage3_rate=0.25,
        ckd_stage4_rate=0.15,
        ckd_stage5_esrd_rate=0.10,
        copd_gold2_rate=0.15,
        copd_gold3_rate=0.15,
        copd_gold4_rate=0.08,
        sleep_apnea_rate=0.35,
        ugt2b7_poor_rate=0.20,
        abcb1_deficient_rate=0.20,
    ),
    "zombie_market": CohortConfig(
        name="zombie_market",
        description="Worst-case street illicit contamination: Fentanyl + Xylazine ('Tranq') + Nitazenes.",
        street_fentanyl_rate=0.75,
        street_fentanyl_dose_mg=2.5,
        carfentanil_rate=0.10,
        carfentanil_dose_ug=50.0,
        xylazine_rate=0.65,
        xylazine_dose_mg=100.0,
        nitazene_rate=0.40,
        nitazene_dose_mg=1.2,
        alcohol_rate=0.50,
        benzo_rate=0.45,
        compliance_rate=0.50,
        weekend_binge_rate=0.35,
        missed_dose_prob=0.25,
        abrupt_cessation_challenge=True,
    ),
}


@dataclass
class TensorProtocolConfig:
    """Protocol dosage schedule for the simulation."""
    compounds: List[str]
    doses: List[float]               # mg per administration
    frequencies: List[float]         # doses per day (e.g. 1.0 = QD, 2.0 = BID, 3.0 = TID, 4.0 = QID)
    duration_days: int = 90          # Length of trial horizon (days)
    time_step_hours: float = 6.0     # Temporal discretization step (hours)
    cessation_day: Optional[int] = None # Day to abruptly halt dosing for withdrawal challenge

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# High-Resolution Streaming Quantile / Statistics Accumulator
# ============================================================================

class StreamingHistogram:
    """
    Fixed-memory, high-resolution histogram for streaming quantile estimation
    across tens of millions of simulated patients without memory growth.
    """
    def __init__(self, val_min: float, val_max: float, num_bins: int = 5000, device: torch.device = torch.device("cpu")):
        self.val_min = float(val_min)
        self.val_max = float(val_max)
        self.num_bins = int(num_bins)
        self.device = device
        self.bin_width = (self.val_max - self.val_min) / self.num_bins
        self.counts = torch.zeros(self.num_bins, dtype=torch.int64, device=self.device)
        self.total_count = 0
        self.sum_val = 0.0
        self.sum_sq_val = 0.0
        self.min_observed = float("inf")
        self.max_observed = float("-inf")

    def update(self, values: torch.Tensor):
        """Update histogram with a 1D tensor of observed values."""
        if values.numel() == 0:
            return
        v = values.detach()
        n = v.numel()
        self.total_count += n
        self.sum_val += float(v.sum().item())
        self.sum_sq_val += float((v * v).sum().item())

        v_min = float(v.min().item())
        v_max = float(v.max().item())
        if v_min < self.min_observed:
            self.min_observed = v_min
        if v_max > self.max_observed:
            self.max_observed = v_max

        # Map to bin indices
        bin_indices = torch.clamp(
            ((v - self.val_min) / (self.val_max - self.val_min) * (self.num_bins - 1)).long(),
            0,
            self.num_bins - 1,
        )
        b_counts = torch.bincount(bin_indices, minlength=self.num_bins)
        self.counts += b_counts.to(self.device)

    def get_percentile(self, q: float) -> float:
        """
        Compute estimated percentile q in [0, 100].
        Supports extreme tails (e.g. p99.9, p99.99).
        """
        if self.total_count == 0:
            return 0.0
        target = (q / 100.0) * self.total_count
        cum = torch.cumsum(self.counts, dim=0)
        idx = torch.searchsorted(cum, torch.tensor(target, device=self.device)).item()
        idx = min(max(idx, 0), self.num_bins - 1)
        return self.val_min + (idx + 0.5) * self.bin_width

    def get_mean(self) -> float:
        return self.sum_val / max(self.total_count, 1)

    def get_std(self) -> float:
        if self.total_count <= 1:
            return 0.0
        mean = self.get_mean()
        var = max(0.0, (self.sum_sq_val / self.total_count) - (mean * mean))
        return math.sqrt(var)


@dataclass
class SimulationSummary:
    """Comprehensive statistical summary across the complete simulated population."""
    total_patients: int
    device: str
    chunk_size: int
    elapsed_seconds: float
    throughput_patients_per_sec: float

    # Core Clinical Endpoints
    analgesia_maintained_rate: float      # Adequate analgesia (pain < 4, analgesia > 0.5)
    withdrawal_rate: float                # Patients experiencing withdrawal (COWS > 15)
    addiction_rate: float                 # Patients developing craving / compulsive reinforcement
    respiratory_depression_rate: float    # Patients with severe respiratory depression (drive < 0.40)
    overdose_rate: float                  # Severe acute overdose episodes
    fatal_overdose_rate: float            # Fatal hypercapnic/hypoxic respiratory arrest
    cardiac_fatal_rate: float             # Fatal QTc prolongation / Torsades de Pointes
    mortality_rate: float                 # Combined all-cause mortality rate

    # Adverse Events Breakdown
    adverse_events_rates: Dict[str, float]

    # Percentiles for continuous monitoring metrics
    percentiles: Dict[str, Dict[str, float]]

    # Metadata
    cohort_name: str
    protocol_compounds: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self, filepath: Union[str, Path]):
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# ============================================================================
# Vectorized Patient Tensor Cohort Generator
# ============================================================================

class TensorPatientGenerator:
    """
    Vectorized generator that constructs high-dimensional patient demographic,
    genetic, organ impairment, and polysubstance feature tensors directly in PyTorch.
    """
    def __init__(self, config: CohortConfig, device: torch.device, seed: int = 42):
        self.config = config
        self.device = device
        self.generator = torch.Generator(device=self.device).manual_seed(seed)

    def generate_batch(self, n: int) -> Dict[str, torch.Tensor]:
        """Generate a vectorized patient cohort of size n."""
        dev = self.device
        cfg = self.config
        gen = self.generator

        # 1. Demographics
        is_male = torch.bernoulli(torch.full((n,), cfg.sex_ratio_male, device=dev), generator=gen)
        # Age distribution via Beta sampling mapped to [age_min, age_max]
        beta_sample = torch.distributions.Beta(cfg.age_beta_a, cfg.age_beta_b).sample((n,)).to(dev)
        age = cfg.age_min + beta_sample * (cfg.age_max - cfg.age_min)

        # 2. Body composition & Extremes (Cachexia vs Morbid Obesity)
        bmi_base = torch.normal(mean=cfg.bmi_mean, std=cfg.bmi_sigma, size=(n,), device=dev, generator=gen)
        bmi = torch.clamp(bmi_base, 14.0, 70.0)

        # Force cachexia and morbid obesity according to cohort rates
        cachexia_mask = torch.bernoulli(torch.full((n,), cfg.cachexia_rate, device=dev), generator=gen).bool()
        obesity_mask = torch.bernoulli(torch.full((n,), cfg.morbid_obesity_rate, device=dev), generator=gen).bool()
        bmi = torch.where(cachexia_mask, torch.empty((n,), device=dev).uniform_(13.5, 15.9, generator=gen), bmi)
        bmi = torch.where(obesity_mask, torch.empty((n,), device=dev).uniform_(50.1, 68.0, generator=gen), bmi)

        # Height (cm) sex-stratified
        height_male = torch.normal(176.0, 7.0, size=(n,), device=dev, generator=gen)
        height_female = torch.normal(163.0, 6.5, size=(n,), device=dev, generator=gen)
        height_cm = torch.where(is_male.bool(), height_male, height_female)
        weight_kg = torch.clamp(bmi * ((height_cm / 100.0) ** 2), 35.0, 260.0)

        # Plasma Albumin (g/dL): Normal 4.2 +/- 0.35, cachexia down to 1.8 - 2.6
        albumin_base = torch.normal(4.2, 0.35, size=(n,), device=dev, generator=gen)
        albumin = torch.where(cachexia_mask, torch.empty((n,), device=dev).uniform_(1.8, 2.5, generator=gen), albumin_base)
        albumin = torch.clamp(albumin, 1.5, 5.5)

        # 3. Pharmacogenomics (PGx)
        # UGT2B7: 0 = Poor (0.35), 1 = Normal (1.0), 2 = Rapid (1.75)
        ugt_rnd = torch.rand(n, device=dev, generator=gen)
        ugt2b7_activity = torch.where(
            ugt_rnd < cfg.ugt2b7_poor_rate,
            torch.full((n,), 0.35, device=dev),
            torch.where(
                ugt_rnd < (cfg.ugt2b7_poor_rate + cfg.ugt2b7_rapid_rate),
                torch.full((n,), 1.75, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )

        # ABCB1 / MDR1 P-gp Efflux: Deficient (0.25), Intermediate (0.65), Normal (1.0)
        abcb1_rnd = torch.rand(n, device=dev, generator=gen)
        abcb1_activity = torch.where(
            abcb1_rnd < cfg.abcb1_deficient_rate,
            torch.full((n,), 0.25, device=dev),
            torch.where(
                abcb1_rnd < (cfg.abcb1_deficient_rate + cfg.abcb1_intermediate_rate),
                torch.full((n,), 0.65, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )

        # CYP3A4 4-tier: PM (0.05), IM (0.55), NM (1.00), UM (2.00)
        cyp3a4_rnd = torch.rand(n, device=dev, generator=gen)
        cyp3a4_activity = torch.where(
            cyp3a4_rnd < cfg.cyp3a4_pm_rate,
            torch.full((n,), 0.05, device=dev),
            torch.where(
                cyp3a4_rnd < (cfg.cyp3a4_pm_rate + cfg.cyp3a4_im_rate),
                torch.full((n,), 0.55, device=dev),
                torch.where(
                    cyp3a4_rnd < (cfg.cyp3a4_pm_rate + cfg.cyp3a4_im_rate + cfg.cyp3a4_um_rate),
                    torch.full((n,), 2.00, device=dev),
                    torch.full((n,), 1.00, device=dev),
                ),
            ),
        )

        # CYP2D6 4-tier: PM (0.05), IM (0.55), NM (1.00), UM (2.00)
        cyp2d6_rnd = torch.rand(n, device=dev, generator=gen)
        cyp2d6_activity = torch.where(
            cyp2d6_rnd < cfg.cyp2d6_pm_rate,
            torch.full((n,), 0.05, device=dev),
            torch.where(
                cyp2d6_rnd < (cfg.cyp2d6_pm_rate + cfg.cyp2d6_im_rate),
                torch.full((n,), 0.55, device=dev),
                torch.where(
                    cyp2d6_rnd < (cfg.cyp2d6_pm_rate + cfg.cyp2d6_im_rate + cfg.cyp2d6_um_rate),
                    torch.full((n,), 2.00, device=dev),
                    torch.full((n,), 1.00, device=dev),
                ),
            ),
        )

        # OPRM1 A118G: AA (1.0), AG (0.75 expression, 0.80 G-coupling), GG (0.45 expression, 0.55 G-coupling)
        oprm1_rnd = torch.rand(n, device=dev, generator=gen)
        oprm1_coupling = torch.where(
            oprm1_rnd < cfg.oprm1_gg_rate,
            torch.full((n,), 0.55, device=dev),
            torch.where(
                oprm1_rnd < (cfg.oprm1_gg_rate + cfg.oprm1_ag_rate),
                torch.full((n,), 0.80, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )
        oprm1_expression = torch.where(
            oprm1_rnd < cfg.oprm1_gg_rate,
            torch.full((n,), 0.45, device=dev),
            torch.where(
                oprm1_rnd < (cfg.oprm1_gg_rate + cfg.oprm1_ag_rate),
                torch.full((n,), 0.75, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )

        # COMT Val158Met: Val/Val (1.4x DA clearance, 1.3x pain sensitivity), Met/Met (0.6x clearance, 0.8x pain)
        comt_rnd = torch.rand(n, device=dev, generator=gen)
        comt_da_clearance = torch.where(
            comt_rnd < cfg.comt_val_val_rate,
            torch.full((n,), 1.40, device=dev),
            torch.where(
                comt_rnd < (cfg.comt_val_val_rate + cfg.comt_met_met_rate),
                torch.full((n,), 0.60, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )
        comt_pain_mult = torch.where(
            comt_rnd < cfg.comt_val_val_rate,
            torch.full((n,), 1.30, device=dev),
            torch.where(
                comt_rnd < (cfg.comt_val_val_rate + cfg.comt_met_met_rate),
                torch.full((n,), 0.80, device=dev),
                torch.full((n,), 1.00, device=dev),
            ),
        )

        # 4. Multi-Organ Impairment & Extremes
        # Hepatic failure: Child-Pugh A, B, C & Portosystemic shunt fraction
        cp_rnd = torch.rand(n, device=dev, generator=gen)
        is_cp_c = cp_rnd < cfg.child_pugh_c_rate
        is_cp_b = (~is_cp_c) & (cp_rnd < (cfg.child_pugh_c_rate + cfg.child_pugh_b_rate))
        is_cp_a = (~is_cp_c) & (~is_cp_b) & (cp_rnd < (cfg.child_pugh_c_rate + cfg.child_pugh_b_rate + cfg.child_pugh_a_rate))

        portosystemic_shunt = (
            torch.zeros(n, device=dev)
            + 0.10 * is_cp_a.float()
            + 0.35 * is_cp_b.float()
            + 0.70 * is_cp_c.float()
        )
        hepatic_clearance_factor = (
            torch.ones(n, device=dev)
            - 0.25 * is_cp_a.float()
            - 0.55 * is_cp_b.float()
            - 0.85 * is_cp_c.float()
        )

        # Renal failure (eGFR ml/min): Normal 100, CKD 2: 75, CKD 3: 45, CKD 4: 22, CKD 5 / ESRD: 10
        ckd_rnd = torch.rand(n, device=dev, generator=gen)
        egfr = torch.where(
            ckd_rnd < cfg.ckd_stage5_esrd_rate,
            torch.full((n,), 10.0, device=dev),
            torch.where(
                ckd_rnd < (cfg.ckd_stage5_esrd_rate + cfg.ckd_stage4_rate),
                torch.full((n,), 22.0, device=dev),
                torch.where(
                    ckd_rnd < (cfg.ckd_stage5_esrd_rate + cfg.ckd_stage4_rate + cfg.ckd_stage3_rate),
                    torch.full((n,), 45.0, device=dev),
                    torch.where(
                        ckd_rnd < (cfg.ckd_stage5_esrd_rate + cfg.ckd_stage4_rate + cfg.ckd_stage3_rate + cfg.ckd_stage2_rate),
                        torch.full((n,), 75.0, device=dev),
                        torch.full((n,), 105.0, device=dev),
                    ),
                ),
            ),
        )

        # Pulmonary Reserve: Severe COPD (GOLD 1-4) & Sleep Apnea
        copd_rnd = torch.rand(n, device=dev, generator=gen)
        is_gold4 = copd_rnd < cfg.copd_gold4_rate
        is_gold3 = (~is_gold4) & (copd_rnd < (cfg.copd_gold4_rate + cfg.copd_gold3_rate))
        is_gold2 = (~is_gold4) & (~is_gold3) & (copd_rnd < (cfg.copd_gold4_rate + cfg.copd_gold3_rate + cfg.copd_gold2_rate))
        is_gold1 = (~is_gold4) & (~is_gold3) & (~is_gold2) & (copd_rnd < (cfg.copd_gold4_rate + cfg.copd_gold3_rate + cfg.copd_gold2_rate + cfg.copd_gold1_rate))

        is_osa = torch.bernoulli(torch.full((n,), cfg.sleep_apnea_rate, device=dev), generator=gen).bool()
        # Elevate OSA in morbid obesity
        is_osa = is_osa | (obesity_mask & (torch.rand(n, device=dev, generator=gen) < 0.40))

        # Baseline PaCO2 (mmHg): Normal ~40, severe COPD/OSA chronic hypercapnia up to 55-60 mmHg
        base_paco2 = (
            torch.full((n,), 40.0, device=dev)
            + 3.0 * is_gold1.float()
            + 6.0 * is_gold2.float()
            + 11.0 * is_gold3.float()
            + 16.0 * is_gold4.float()
            + 5.0 * is_osa.float()
        )
        pulmonary_reserve = torch.clamp(
            torch.ones(n, device=dev)
            - 0.12 * is_gold1.float()
            - 0.25 * is_gold2.float()
            - 0.45 * is_gold3.float()
            - 0.65 * is_gold4.float()
            - 0.20 * is_osa.float(),
            0.15,
            1.00,
        )

        # Baseline Cardiac QTc interval (ms)
        qtc_male = torch.normal(410.0, 14.0, size=(n,), device=dev, generator=gen)
        qtc_female = torch.normal(425.0, 15.0, size=(n,), device=dev, generator=gen)
        base_qtc = torch.where(is_male.bool(), qtc_male, qtc_female)

        # Baseline Pain Severity (0-10) modulated by COMT and comorbidity
        pain_base = torch.distributions.Beta(3.0, 2.0).sample((n,)).to(dev) * 8.0 + 1.0
        baseline_pain = torch.clamp(pain_base * comt_pain_mult, 1.0, 10.0)

        # 5. Polysubstance & Street Adulterant Exposures
        exp_fentanyl = torch.bernoulli(torch.full((n,), cfg.street_fentanyl_rate, device=dev), generator=gen) * cfg.street_fentanyl_dose_mg
        exp_carfentanil = torch.bernoulli(torch.full((n,), cfg.carfentanil_rate, device=dev), generator=gen) * cfg.carfentanil_dose_ug
        exp_xylazine = torch.bernoulli(torch.full((n,), cfg.xylazine_rate, device=dev), generator=gen) * cfg.xylazine_dose_mg
        exp_nitazene = torch.bernoulli(torch.full((n,), cfg.nitazene_rate, device=dev), generator=gen) * cfg.nitazene_dose_mg
        exp_alcohol = torch.bernoulli(torch.full((n,), cfg.alcohol_rate, device=dev), generator=gen)  # Acute intoxication
        exp_benzo = torch.bernoulli(torch.full((n,), cfg.benzo_rate, device=dev), generator=gen)
        exp_gabapentinoid = torch.bernoulli(torch.full((n,), cfg.gabapentinoid_rate, device=dev), generator=gen)
        exp_ssri = torch.bernoulli(torch.full((n,), cfg.ssri_rate, device=dev), generator=gen)
        exp_antipsychotic = torch.bernoulli(torch.full((n,), cfg.antipsychotic_rate, device=dev), generator=gen)

        # 6. Behavioral Compliance Patterns
        is_compliant = torch.bernoulli(torch.full((n,), cfg.compliance_rate, device=dev), generator=gen).bool()
        is_weekend_binger = torch.bernoulli(torch.full((n,), cfg.weekend_binge_rate, device=dev), generator=gen).bool()

        return {
            "is_male": is_male,
            "age": age,
            "weight_kg": weight_kg,
            "bmi": bmi,
            "albumin": albumin,
            "baseline_pain": baseline_pain,
            "ugt2b7_activity": ugt2b7_activity,
            "abcb1_activity": abcb1_activity,
            "cyp3a4_activity": cyp3a4_activity,
            "cyp2d6_activity": cyp2d6_activity,
            "oprm1_coupling": oprm1_coupling,
            "oprm1_expression": oprm1_expression,
            "comt_da_clearance": comt_da_clearance,
            "portosystemic_shunt": portosystemic_shunt,
            "hepatic_clearance_factor": hepatic_clearance_factor,
            "egfr": egfr,
            "base_paco2": base_paco2,
            "pulmonary_reserve": pulmonary_reserve,
            "base_qtc": base_qtc,
            "exp_fentanyl": exp_fentanyl,
            "exp_carfentanil": exp_carfentanil,
            "exp_xylazine": exp_xylazine,
            "exp_nitazene": exp_nitazene,
            "exp_alcohol": exp_alcohol,
            "exp_benzo": exp_benzo,
            "exp_gabapentinoid": exp_gabapentinoid,
            "exp_ssri": exp_ssri,
            "exp_antipsychotic": exp_antipsychotic,
            "is_compliant": is_compliant,
            "is_weekend_binger": is_weekend_binger,
        }


# ============================================================================
# Vectorized Longitudinal Tensor Simulation Engine
# ============================================================================

class TensorPopulationSimulation:
    """
    High-Performance PyTorch/CUDA Vectorized Simulation Engine.
    Executes large-scale clinical trials (up to 10M patients) in streamed batches
    with complete mathematical modeling of PGx, organ failure, polysubstance dynamics,
    VTA dopamine clamping by NOP, and tolerance hysteresis.
    """
    def __init__(
        self,
        device: Optional[str] = None,
        seed: int = 42,
        chunk_size: int = 250_000,
        compound_database: Optional[Dict[str, TensorCompoundProfile]] = None,
    ):
        self.device = detect_device(device)
        self.seed = seed
        self.chunk_size = chunk_size
        self.compounds = dict(COMPOUND_REGISTRY)
        if compound_database:
            self.compounds.update(compound_database)

        logger.info("Initialized TensorPopulationSimulation on device: %s (chunk_size=%d)", self.device, self.chunk_size)

    def _resolve_compound(self, name: str) -> TensorCompoundProfile:
        """Resolve compound name or raise clear error."""
        if name in self.compounds:
            return self.compounds[name]
        # Case-insensitive search
        for k, v in self.compounds.items():
            if k.lower() == name.lower():
                return v
        raise ValueError(f"Unknown compound '{name}'. Available: {list(self.compounds.keys())}")

    def simulate_chunk(
        self,
        cohort: Dict[str, torch.Tensor],
        protocol: TensorProtocolConfig,
        cohort_config: CohortConfig,
        chunk_seed: int,
    ) -> Dict[str, torch.Tensor]:
        """
        Longitudinal simulation loop for a single batch of N patients.
        Fully vectorized on the designated compute device (CPU or CUDA).
        """
        dev = self.device
        n = cohort["age"].shape[0]
        gen = torch.Generator(device=dev).manual_seed(chunk_seed)

        # Temporal discretization
        time_step = protocol.time_step_hours
        hours_per_day = 24.0
        n_steps = int((protocol.duration_days * hours_per_day) / time_step)
        dt_days = time_step / hours_per_day

        # Resolve primary protocol compounds
        primary_profiles = [self._resolve_compound(c) for c in protocol.compounds]
        doses = torch.tensor(protocol.doses, device=dev, dtype=torch.float32)
        freqs = torch.tensor(protocol.frequencies, device=dev, dtype=torch.float32)

        # Adulterant profiles
        fentanyl_profile = self._resolve_compound("Fentanyl")
        carfentanil_profile = self._resolve_compound("Carfentanil")
        xylazine_profile = self._resolve_compound("Xylazine")
        nitazene_profile = self._resolve_compound("Isotonitazene")

        # --------------------------------------------------------------------
        # Pharmacokinetics: Clearance and Volume of Distribution Tensors
        # --------------------------------------------------------------------
        weight_kg = cohort["weight_kg"]
        albumin = cohort["albumin"]
        egfr = cohort["egfr"]
        cyp3a4_act = cohort["cyp3a4_activity"]
        cyp2d6_act = cohort["cyp2d6_activity"]
        ugt2b7_act = cohort["ugt2b7_activity"]
        abcb1_act = cohort["abcb1_activity"]
        hep_clear_factor = cohort["hepatic_clearance_factor"]
        shunt_frac = cohort["portosystemic_shunt"]

        # SSRI inhibition on CYP2D6
        effective_cyp2d6 = torch.where(cohort["exp_ssri"].bool(), cyp2d6_act * 0.35, cyp2d6_act)

        # Acute alcohol inhibition on CYP3A4
        effective_cyp3a4 = torch.where(cohort["exp_alcohol"].bool(), cyp3a4_act * 0.60, cyp3a4_act)

        # Precompute per-compound PK parameters for primary drugs
        compound_pk = []
        for p, dose, freq in zip(primary_profiles, doses, freqs):
            # Volume of distribution adjusted for base Vd, lipophilicity and morbid obesity
            # Morbid obesity expands lipophilic depot
            v_dist = weight_kg * (p.v_dist_base * (0.8 + 0.2 * (cohort["bmi"] / 25.0) * p.lipophilicity))

            # Oral bioavailability enhanced by portosystemic shunt (bypasses first-pass)
            bioavail = torch.clamp(p.bioavailability + (1.0 - p.bioavailability) * shunt_frac, 0.05, 1.00)

            # Clearance multiplier factoring in PGx and organ failure
            metabolic_sum = (
                p.cyp3a4_fraction * effective_cyp3a4
                + p.cyp2d6_fraction * effective_cyp2d6
                + p.ugt2b7_fraction * ugt2b7_act
            )
            metabolic_sum = torch.clamp(metabolic_sum, 0.05, 4.0)

            # Combined systemic clearance (hepatic + renal)
            cl_mult = (1.0 - p.renal_fraction) * hep_clear_factor * metabolic_sum + p.renal_fraction * (egfr / 100.0)
            cl_mult = torch.clamp(cl_mult, 0.05, 3.5)

            adj_t_half = torch.clamp(p.t_half / cl_mult, 0.5, 80.0)
            k_elim = 0.693 / adj_t_half

            # Initial concentration pulse per dose (ug/L or nM equivalent)
            c_dose_pulse = (dose * bioavail * 1000.0) / v_dist

            compound_pk.append({
                "profile": p,
                "freq": freq.item(),
                "k_elim": k_elim,
                "c_dose_pulse": c_dose_pulse,
                "dose_interval_hrs": 24.0 / freq.item(),
                "is_buprenorphine": (p.name == "Buprenorphine"),
            })

        # --------------------------------------------------------------------
        # Dynamic State Variables (N patients)
        # --------------------------------------------------------------------
        c_plasma_primary = [torch.zeros(n, device=dev) for _ in primary_profiles]
        c_norbuprenorphine_plasma = torch.zeros(n, device=dev)
        c_norbuprenorphine_brain = torch.zeros(n, device=dev)

        # Adulterants concentration state
        c_fentanyl = torch.zeros(n, device=dev)
        c_carfentanil = torch.zeros(n, device=dev)
        c_xylazine = torch.zeros(n, device=dev)
        c_nitazene = torch.zeros(n, device=dev)

        # Pharmacodynamic states
        tolerance_state = torch.zeros(n, device=dev)  # Functional tolerance [0.0, 1.0]
        addiction_state = torch.zeros(n, device=dev)  # Cumulative dopamine reinforcement score
        cum_analgesia = torch.zeros(n, device=dev)
        cum_pain = torch.zeros(n, device=dev)
        cum_respiratory_dep = torch.zeros(n, device=dev)
        min_respiratory_drive = torch.ones(n, device=dev)
        max_paco2 = cohort["base_paco2"].clone()
        min_spo2 = torch.full((n,), 98.0, device=dev)
        max_qtc = cohort["base_qtc"].clone()
        max_dopamine_peak = torch.zeros(n, device=dev)
        max_withdrawal_cows = torch.zeros(n, device=dev)
        min_free_mor_fraction = torch.ones(n, device=dev)
        last_day_max_free_mor_fraction = torch.zeros(n, device=dev)

        # Binary event flags across the longitudinal horizon
        fatal_respiratory_arrest = torch.zeros(n, dtype=torch.bool, device=dev)
        fatal_cardiac_arrest = torch.zeros(n, dtype=torch.bool, device=dev)
        severe_overdose_event = torch.zeros(n, dtype=torch.bool, device=dev)
        severe_respiratory_dep_event = torch.zeros(n, dtype=torch.bool, device=dev)
        severe_withdrawal_event = torch.zeros(n, dtype=torch.bool, device=dev)
        persistent_sedation_event = torch.zeros(n, dtype=torch.bool, device=dev)
        severe_nausea_event = torch.zeros(n, dtype=torch.bool, device=dev)
        constipation_event = torch.zeros(n, dtype=torch.bool, device=dev)

        # Receptor genetic expression and coupling
        oprm1_exp = cohort["oprm1_expression"]
        oprm1_coupling = cohort["oprm1_coupling"]
        pulmonary_reserve = cohort["pulmonary_reserve"]

        # Adulterant exposures
        has_exp_fentanyl = cohort["exp_fentanyl"] > 0
        has_exp_carfentanil = cohort["exp_carfentanil"] > 0
        has_exp_xylazine = cohort["exp_xylazine"] > 0
        has_exp_nitazene = cohort["exp_nitazene"] > 0
        has_exp_benzo = cohort["exp_benzo"] > 0
        has_exp_gaba = cohort["exp_gabapentinoid"] > 0
        has_exp_alcohol = cohort["exp_alcohol"] > 0
        has_exp_antipsychotic = cohort["exp_antipsychotic"] > 0

        # Precompute adulterant elimination rates
        k_elim_fentanyl = 0.693 / 3.7
        k_elim_carfentanil = 0.693 / 8.0
        k_elim_xylazine = 0.693 / 0.8
        k_elim_nitazene = 0.693 / 4.0

        # Pulse adulterant concentrations on day 1 or intermittent weekends
        v_dist_std = weight_kg * 1.0
        c_fentanyl += (cohort["exp_fentanyl"] * 0.5 * 1000.0) / v_dist_std
        c_carfentanil += (cohort["exp_carfentanil"] * 0.001 * 0.5 * 1000.0) / (v_dist_std * 1.5)
        c_xylazine += (cohort["exp_xylazine"] * 0.85 * 1000.0) / v_dist_std
        c_nitazene += (cohort["exp_nitazene"] * 0.5 * 1000.0) / v_dist_std

        # --------------------------------------------------------------------
        # Time-Stepping Longitudinal Loop
        # --------------------------------------------------------------------
        for step in range(n_steps):
            t_hours = step * time_step
            t_days = t_hours / hours_per_day
            day_idx = int(t_days)
            is_weekend = (day_idx % 7) in [5, 6]

            # Cessation withdrawal challenge: halt all dosing after cessation day
            under_cessation = False
            if protocol.cessation_day is not None and day_idx >= protocol.cessation_day:
                under_cessation = True
            elif cohort_config.abrupt_cessation_challenge and day_idx >= int(protocol.duration_days * 0.80):
                under_cessation = True

            # 1. Update Pharmacokinetics & Administer Doses
            for idx, c_meta in enumerate(compound_pk):
                # Exponential decay over time_step
                c_plasma_primary[idx] *= torch.exp(-c_meta["k_elim"] * time_step)

                if not under_cessation:
                    # Dose timing check
                    dose_interval = c_meta["dose_interval_hrs"]
                    if (t_hours % dose_interval) < time_step:
                        # Adherence and behavioral modulation
                        miss_mask = torch.bernoulli(torch.full((n,), cohort_config.missed_dose_prob, device=dev), generator=gen).bool()
                        take_dose = cohort["is_compliant"] | (~miss_mask)

                        dose_factor = torch.ones(n, device=dev)
                        if is_weekend:
                            # Weekend bingeing
                            dose_factor = torch.where(cohort["is_weekend_binger"], torch.full((n,), 2.0, device=dev), dose_factor)

                        c_plasma_primary[idx] += c_meta["c_dose_pulse"] * dose_factor * take_dose.float()

                # Buprenorphine Norbuprenorphine Shunting & ABCB1 BBB Mechanics
                if c_meta["is_buprenorphine"]:
                    # CYP3A4 converts buprenorphine to Norbuprenorphine; UGT2B7 clears to inactive B3G
                    # When UGT2B7 is low, more parent is converted by CYP3A4 to Norbuprenorphine
                    shunt_to_norbup = (0.25 * cyp3a4_act) / (0.25 * cyp3a4_act + 0.50 * ugt2b7_act)
                    formation_norbup = c_plasma_primary[idx] * shunt_to_norbup * 0.15

                    c_norbuprenorphine_plasma = (c_norbuprenorphine_plasma * math.exp(-0.693 / 35.0 * time_step)) + formation_norbup

                    # ABCB1 P-glycoprotein BBB Efflux:
                    # Normally P-gp keeps norbuprenorphine out of the CNS (penetration ~0.08)
                    # If ABCB1 is deficient, brain penetration surges up to 4x!
                    brain_penetration = 0.08 / torch.clamp(abcb1_act, 0.20, 1.20)
                    c_norbuprenorphine_brain = c_norbuprenorphine_plasma * brain_penetration

            # Eliminate street adulterants
            c_fentanyl *= math.exp(-k_elim_fentanyl * time_step)
            c_carfentanil *= math.exp(-k_elim_carfentanil * time_step)
            c_xylazine *= math.exp(-k_elim_xylazine * time_step)
            c_nitazene *= math.exp(-k_elim_nitazene * time_step)

            # Re-dose street adulterants on weekends for polysubstance cohorts
            if is_weekend and not under_cessation:
                if (t_hours % 24.0) < time_step:
                    weekend_hit = torch.bernoulli(torch.full((n,), 0.35, device=dev), generator=gen)
                    c_fentanyl += (cohort["exp_fentanyl"] * weekend_hit * 0.5 * 1000.0) / v_dist_std
                    c_xylazine += (cohort["exp_xylazine"] * weekend_hit * 0.85 * 1000.0) / v_dist_std

            # ----------------------------------------------------------------
            # 2. Multi-Ligand Competitive Receptor Binding Kinetics
            # ----------------------------------------------------------------
            # Receptors: MOR, DOR, KOR, NOP, Alpha-2
            # Sum of (C_i / Ki) for competitive displacement
            denom_mor = torch.ones(n, device=dev)
            denom_dor = torch.ones(n, device=dev)
            denom_kor = torch.ones(n, device=dev)
            denom_nop = torch.ones(n, device=dev)
            denom_a2 = torch.ones(n, device=dev)

            # Primary compounds (biophase free concentration in nM)
            for idx, c_meta in enumerate(compound_pk):
                cp = c_meta["profile"]
                conc = c_plasma_primary[idx] * (1000.0 / cp.mw) * cp.unbound_fraction
                if cp.ki_mor < 1e5:
                    denom_mor += (conc / cp.ki_mor)
                if cp.ki_dor < 1e5:
                    denom_dor += (conc / cp.ki_dor)
                if cp.ki_kor < 1e5:
                    denom_kor += (conc / cp.ki_kor)
                if cp.ki_nop < 1e5:
                    denom_nop += (conc / cp.ki_nop)

            # Norbuprenorphine (active metabolite) in brain biophase nM
            c_norbup_nM = c_norbuprenorphine_brain * (1000.0 / 413.6) * 0.15
            denom_mor += (c_norbup_nM / 0.40)

            # Adulterants in biophase nM
            c_fent_nM = c_fentanyl * (1000.0 / 336.5) * 0.16
            c_carf_nM = c_carfentanil * (1000.0 / 394.5) * 0.15
            c_nita_nM = c_nitazene * (1000.0 / 410.5) * 0.10
            c_xyla_nM = c_xylazine * (1000.0 / 220.3) * 0.30

            denom_mor += (c_fent_nM / fentanyl_profile.ki_mor)
            denom_mor += (c_carf_nM / carfentanil_profile.ki_mor)
            denom_mor += (c_nita_nM / nitazene_profile.ki_mor)
            denom_a2 += (c_xyla_nM / xylazine_profile.ki_alpha2)

            free_mor_fraction = 1.0 / denom_mor
            min_free_mor_fraction = torch.minimum(min_free_mor_fraction, free_mor_fraction)
            if day_idx >= protocol.duration_days - 1:
                last_day_max_free_mor_fraction = torch.maximum(
                    last_day_max_free_mor_fraction, free_mor_fraction)

            # Fractional activation: E_G = sum( (C_i/Ki)/denom * intrinsic_i * g_bias_i )
            mor_g_act = torch.zeros(n, device=dev)
            mor_beta_act = torch.zeros(n, device=dev)
            dor_g_act = torch.zeros(n, device=dev)
            kor_g_act = torch.zeros(n, device=dev)
            nop_g_act = torch.zeros(n, device=dev)
            reversing_tolerance_present = torch.zeros(n, dtype=torch.bool, device=dev)
            preventing_withdrawal_present = torch.zeros(n, dtype=torch.bool, device=dev)

            for idx, c_meta in enumerate(compound_pk):
                cp = c_meta["profile"]
                conc = c_plasma_primary[idx] * (1000.0 / cp.mw) * cp.unbound_fraction
                occ_mor = (conc / cp.ki_mor) / denom_mor if cp.ki_mor < 1e5 else 0.0
                mor_g_act += occ_mor * cp.intrinsic_activity * cp.g_protein_bias
                mor_beta_act += occ_mor * cp.intrinsic_activity * cp.beta_arrestin_bias

                if cp.ki_dor < 1e5:
                    dor_g_act += ((conc / cp.ki_dor) / denom_dor) * cp.intrinsic_activity
                if cp.ki_kor < 1e5:
                    kor_g_act += ((conc / cp.ki_kor) / denom_kor) * cp.intrinsic_activity
                if cp.ki_nop < 1e5:
                    nop_g_act += ((conc / cp.ki_nop) / denom_nop) * cp.intrinsic_activity

                if cp.reverses_tolerance and (conc.mean() > 0.01):
                    reversing_tolerance_present = reversing_tolerance_present | (conc > 0.05)
                if cp.prevents_withdrawal and (conc.mean() > 0.01):
                    preventing_withdrawal_present = preventing_withdrawal_present | (conc > 0.05)

            # Norbuprenorphine contribution in CNS (high beta-arrestin / respiratory depressant)
            occ_norbup = (c_norbup_nM / 0.40) / denom_mor
            mor_g_act += occ_norbup * 1.0 * 1.0
            mor_beta_act += occ_norbup * 1.0 * 1.5

            # Adulterants contribution
            occ_fent = (c_fent_nM / fentanyl_profile.ki_mor) / denom_mor
            mor_g_act += occ_fent * fentanyl_profile.intrinsic_activity * fentanyl_profile.g_protein_bias
            mor_beta_act += occ_fent * fentanyl_profile.intrinsic_activity * fentanyl_profile.beta_arrestin_bias

            occ_carf = (c_carf_nM / carfentanil_profile.ki_mor) / denom_mor
            mor_g_act += occ_carf * carfentanil_profile.intrinsic_activity * carfentanil_profile.g_protein_bias
            mor_beta_act += occ_carf * carfentanil_profile.intrinsic_activity * carfentanil_profile.beta_arrestin_bias

            occ_nita = (c_nita_nM / nitazene_profile.ki_mor) / denom_mor
            mor_g_act += occ_nita * nitazene_profile.intrinsic_activity * nitazene_profile.g_protein_bias
            mor_beta_act += occ_nita * nitazene_profile.intrinsic_activity * nitazene_profile.beta_arrestin_bias

            # Alpha-2 activation by Xylazine
            a2_act = ((c_xyla_nM / xylazine_profile.ki_alpha2) / denom_a2) * xylazine_profile.intrinsic_activity

            # Modulate MOR signaling by OPRM1 genotype (A118G variant)
            mor_g_act = mor_g_act * oprm1_exp * oprm1_coupling
            mor_beta_act = mor_beta_act * oprm1_exp

            # ----------------------------------------------------------------
            # 3. Dynamic Receptor Mechanics: NOP Dopamine Clamp & Tolerance
            # ----------------------------------------------------------------
            # VTA Dopamine Regulation:
            # MOR activation disinhibits DA neurons. BUT NOP activation (SR-16435)
            # directly hyperpolarizes DA neurons via GIRK channels, clamping DA surge.
            da_mor_drive = (mor_g_act ** 2) / (0.35 ** 2 + mor_g_act ** 2 + 1e-6)
            nop_clamp = 1.0 / (1.0 + (nop_g_act / 0.15) ** 2)  # Active dopamine ceiling
            kor_oppose = 1.0 - 0.25 * torch.clamp(kor_g_act, 0.0, 1.0)  # KOR dysphoria/anti-reward

            net_da_surge_pct = da_mor_drive * nop_clamp * kor_oppose * 350.0  # Max surge up to 350%
            max_dopamine_peak = torch.maximum(max_dopamine_peak, net_da_surge_pct)

            # Addiction state progression (reinforcement integration)
            addiction_stimulus = torch.clamp(net_da_surge_pct - 30.0, min=0.0) / 100.0
            addiction_state = addiction_state * math.exp(-0.01 * dt_days) + addiction_stimulus * dt_days * 5.0

            # Tolerance Hysteresis: Beta-arrestin internalization vs G-protein resensitization
            # High beta-arrestin (Fentanyl, Nitazenes) accelerates tolerance.
            # High G-protein bias ligands (SR-14968, SR-17018) actively reverse tolerance!
            tol_induction = 0.08 * mor_beta_act
            tol_resens = torch.where(
                reversing_tolerance_present,
                0.25 * mor_g_act * tolerance_state,
                0.01 * tolerance_state,
            )
            tolerance_state = torch.clamp(tolerance_state + (tol_induction - tol_resens) * dt_days, 0.0, 0.95)

            # ----------------------------------------------------------------
            # 4. Analgesia & Pain Control
            # ----------------------------------------------------------------
            # Analgesia efficacy reduced by tolerance
            effective_tol = torch.where(reversing_tolerance_present, tolerance_state * 0.3, tolerance_state)
            analgesia_level = torch.clamp(mor_g_act * (1.0 - effective_tol) + 0.15 * dor_g_act, 0.0, 1.0)

            # Additive synergy from gabapentinoids
            analgesia_level = torch.clamp(analgesia_level + 0.08 * has_exp_gaba.float(), 0.0, 1.0)

            pain_relief = analgesia_level * cohort["baseline_pain"]
            current_pain = torch.clamp(cohort["baseline_pain"] - pain_relief, 0.0, 10.0)

            cum_analgesia += analgesia_level
            cum_pain += current_pain

            # ----------------------------------------------------------------
            # 5. Respiratory Dynamics & Arterial Blood Gas (ABG) Kinetics
            # ----------------------------------------------------------------
            # Respiratory drive suppressed by MOR beta-arrestin, alcohol, benzos, and xylazine
            resp_inhibition = (mor_beta_act ** 1.8) / (0.45 ** 1.8 + mor_beta_act ** 1.8 + 1e-6)

            # Synergistic depressant multipliers:
            # Alcohol: +100% depression; Benzos: +150% depression; Xylazine: +120% depression
            synergy_mult = (
                1.0
                + 1.0 * has_exp_alcohol.float()
                + 1.5 * has_exp_benzo.float()
                + 1.2 * (a2_act / 0.5)
            )

            current_resp_drive = torch.clamp(pulmonary_reserve * (1.0 - resp_inhibition * synergy_mult * 0.85), 0.02, 1.0)
            min_respiratory_drive = torch.minimum(min_respiratory_drive, current_resp_drive)

            # Arterial PaCO2 (mmHg): severe hypoventilation elevates PaCO2 above 75-80 mmHg
            current_paco2 = cohort["base_paco2"] + (38.0 * (1.0 - current_resp_drive)) / (current_resp_drive + 0.15)
            max_paco2 = torch.maximum(max_paco2, current_paco2)

            # Arterial Oxygen Saturation (SpO2, %):
            current_spo2 = torch.clamp(99.0 - 0.70 * (current_paco2 - 40.0) - 25.0 * (1.0 - current_resp_drive), 35.0, 100.0)
            min_spo2 = torch.minimum(min_spo2, current_spo2)

            # Respiratory events
            severe_respiratory_dep_event = severe_respiratory_dep_event | (current_resp_drive < 0.40) | (current_spo2 < 85.0)
            severe_overdose_event = severe_overdose_event | (current_resp_drive < 0.25) | (current_paco2 > 70.0)
            fatal_respiratory_arrest = fatal_respiratory_arrest | (current_resp_drive < 0.12) | (current_paco2 > 85.0) | (current_spo2 < 55.0)

            # ----------------------------------------------------------------
            # 6. Cardiac Electrophysiology (hERG & QTc Interval)
            # ----------------------------------------------------------------
            delta_qtc = torch.zeros(n, device=dev)
            for idx, c_meta in enumerate(compound_pk):
                cp = c_meta["profile"]
                conc = c_plasma_primary[idx]
                if cp.herg_ic50_uM < 500.0:
                    conc_uM = conc / cp.mw  # exact conversion from ug/L to uM using MW
                    delta_qtc += (conc_uM / (conc_uM + cp.herg_ic50_uM)) * 65.0

            # Polypharmacy QTc burden
            delta_qtc += 18.0 * has_exp_antipsychotic.float() + 10.0 * cohort["exp_ssri"].float()
            current_qtc = cohort["base_qtc"] + delta_qtc
            max_qtc = torch.maximum(max_qtc, current_qtc)

            # Cardiac Torsades de Pointes fatality threshold: QTc > 500 ms
            severe_qtc_mask = current_qtc > 500.0
            cardiac_event_prob = torch.clamp((current_qtc - 500.0) * 0.0005, 0.0, 0.05)
            cardiac_hit = torch.bernoulli(cardiac_event_prob, generator=gen).bool() & severe_qtc_mask
            fatal_cardiac_arrest = fatal_cardiac_arrest | cardiac_hit

            # ----------------------------------------------------------------
            # 7. Withdrawal Assessment (COWS Equivalent)
            # ----------------------------------------------------------------
            # Triggered if under cessation and no withdrawal-protective drug present
            if under_cessation:
                rebound_hyperalgesia = tolerance_state * 25.0
                cows_score = torch.where(
                    preventing_withdrawal_present,
                    torch.full((n,), 5.0, device=dev),  # Mild / protected
                    torch.clamp(15.0 + rebound_hyperalgesia * (1.0 - mor_g_act), 0.0, 50.0),
                )
                max_withdrawal_cows = torch.maximum(max_withdrawal_cows, cows_score)
                severe_withdrawal_event = severe_withdrawal_event | (cows_score > 15.0)

            # ----------------------------------------------------------------
            # 8. Adverse Events Tracking
            # ----------------------------------------------------------------
            persistent_sedation_event = persistent_sedation_event | ((mor_beta_act > 0.65) | has_exp_benzo.bool())
            severe_nausea_event = severe_nausea_event | (mor_beta_act > 0.50)
            constipation_event = constipation_event | (mor_g_act > 0.30)

        # --------------------------------------------------------------------
        # Outcome Aggregation for the Batch
        # --------------------------------------------------------------------
        mean_pain = cum_pain / n_steps
        mean_analgesia = cum_analgesia / n_steps

        # Success: Adequate pain control without severe tolerance
        success_mask = (mean_pain < 4.0) & (mean_analgesia > 0.50) & (tolerance_state < 0.50)
        addiction_flag = (addiction_state > 35.0) | (max_dopamine_peak > 200.0)
        total_mortality = fatal_respiratory_arrest | fatal_cardiac_arrest

        return {
            "mean_pain": mean_pain,
            "mean_analgesia": mean_analgesia,
            "final_tolerance": tolerance_state,
            "addiction_score": addiction_state,
            "max_dopamine_peak": max_dopamine_peak,
            "min_respiratory_drive": min_respiratory_drive,
            "max_paco2": max_paco2,
            "min_spo2": min_spo2,
            "max_qtc": max_qtc,
            "max_withdrawal_cows": max_withdrawal_cows,
            "peak_mor_occupancy": 1.0 - min_free_mor_fraction,
            "last_day_trough_free_mor_fraction": last_day_max_free_mor_fraction,
            "success": success_mask,
            "withdrawal_flag": severe_withdrawal_event,
            "addiction_flag": addiction_flag,
            "respiratory_dep_flag": severe_respiratory_dep_event,
            "overdose_flag": severe_overdose_event,
            "fatal_overdose_flag": fatal_respiratory_arrest,
            "cardiac_fatal_flag": fatal_cardiac_arrest,
            "mortality_flag": total_mortality,
            "sedation_flag": persistent_sedation_event,
            "nausea_flag": severe_nausea_event,
            "constipation_flag": constipation_event,
        }

    def run(
        self,
        total_patients: int = 10_000_000,
        protocol: Optional[Union[TensorProtocolConfig, Dict[str, Any]]] = None,
        cohort: Union[CohortConfig, str, Dict[str, Any]] = "standard",
        chunk_size: Optional[int] = None,
        verbose: bool = True,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ) -> SimulationSummary:
        """
        Execute simulation across `total_patients` in streaming chunks.
        Supports 10M patients within strictly bounded memory.
        """
        start_time = time.time()
        effective_chunk_size = chunk_size or self.chunk_size

        # Resolve CohortConfig
        if isinstance(cohort, str):
            if cohort in COHORT_PRESETS:
                cohort_cfg = COHORT_PRESETS[cohort]
            else:
                raise ValueError(f"Unknown cohort preset '{cohort}'. Available: {list(COHORT_PRESETS.keys())}")
        elif isinstance(cohort, dict):
            cohort_cfg = CohortConfig.from_dict(cohort)
        elif isinstance(cohort, CohortConfig):
            cohort_cfg = cohort
        else:
            raise TypeError("cohort must be a CohortConfig, preset name string, or dict.")

        # Resolve TensorProtocolConfig
        if protocol is None:
            # Default to standard ZEROPAIN SR-16435 trial
            protocol_cfg = TensorProtocolConfig(
                compounds=["SR-16435"],
                doses=[20.0],
                frequencies=[2.0],
                duration_days=90,
                time_step_hours=6.0,
            )
        elif isinstance(protocol, dict):
            protocol_cfg = TensorProtocolConfig(**protocol)
        elif isinstance(protocol, TensorProtocolConfig):
            protocol_cfg = protocol
        else:
            # Duck-type ProtocolConfig from patient_simulation.py
            protocol_cfg = TensorProtocolConfig(
                compounds=list(protocol.compounds),
                doses=list(protocol.doses),
                frequencies=list(protocol.frequencies),
                duration_days=getattr(protocol, "duration", getattr(protocol, "duration_days", 90)),
                time_step_hours=getattr(protocol, "time_step_hours", 6.0),
            )

        n_chunks = max(1, math.ceil(total_patients / effective_chunk_size))
        if verbose:
            print(f"=== ZEROPAIN Tensor Simulation Engine ===")
            print(f"  Target Population : {total_patients:,} virtual patients")
            print(f"  Execution Device  : {self.device}")
            print(f"  Batch/Chunk Size  : {effective_chunk_size:,} patients ({n_chunks} chunks)")
            print(f"  Cohort Preset     : {cohort_cfg.name} ({cohort_cfg.description})")
            print(f"  Protocol Regimen  : {protocol_cfg.compounds} (Doses: {protocol_cfg.doses} mg, Freq: {protocol_cfg.frequencies}/day)")
            print(f"  Trial Horizon     : {protocol_cfg.duration_days} days (dt={protocol_cfg.time_step_hours}h)")
            print("=========================================")

        # Streaming Histograms for Continuous Metrics
        hist_pain = StreamingHistogram(0.0, 10.0, num_bins=2000, device=self.device)
        hist_analgesia = StreamingHistogram(0.0, 1.0, num_bins=2000, device=self.device)
        hist_tolerance = StreamingHistogram(0.0, 1.0, num_bins=2000, device=self.device)
        hist_addiction = StreamingHistogram(0.0, 100.0, num_bins=2000, device=self.device)
        hist_resp_drive = StreamingHistogram(0.0, 1.0, num_bins=2000, device=self.device)
        hist_paco2 = StreamingHistogram(30.0, 100.0, num_bins=2000, device=self.device)
        hist_spo2 = StreamingHistogram(40.0, 100.0, num_bins=2000, device=self.device)
        hist_qtc = StreamingHistogram(350.0, 650.0, num_bins=2000, device=self.device)
        hist_dopamine = StreamingHistogram(0.0, 500.0, num_bins=2000, device=self.device)
        hist_peak_mor_occupancy = StreamingHistogram(0.0, 1.0, num_bins=2000, device=self.device)
        hist_trough_free_mor = StreamingHistogram(0.0, 1.0, num_bins=2000, device=self.device)

        # Streaming Binary Counters
        count_analgesia_maintained = 0
        count_withdrawal = 0
        count_addiction = 0
        count_resp_dep = 0
        count_overdose = 0
        count_fatal_overdose = 0
        count_cardiac_fatal = 0
        count_mortality = 0
        count_sedation = 0
        count_nausea = 0
        count_constipation = 0

        simulated_count = 0

        # Execute Chunked Simulation
        generator = TensorPatientGenerator(cohort_cfg, self.device, seed=self.seed)

        for chunk_idx in range(n_chunks):
            chunk_n = min(effective_chunk_size, total_patients - simulated_count)
            if chunk_n <= 0:
                break

            t0_chunk = time.time()

            # 1. Vectorized cohort generation
            batch_cohort = generator.generate_batch(chunk_n)

            # 2. Vectorized longitudinal simulation
            chunk_seed = self.seed + chunk_idx * 1000 + 17
            chunk_results = self.simulate_chunk(batch_cohort, protocol_cfg, cohort_cfg, chunk_seed)

            # 3. Accumulate continuous streaming metrics
            hist_pain.update(chunk_results["mean_pain"])
            hist_analgesia.update(chunk_results["mean_analgesia"])
            hist_tolerance.update(chunk_results["final_tolerance"])
            hist_addiction.update(chunk_results["addiction_score"])
            hist_resp_drive.update(chunk_results["min_respiratory_drive"])
            hist_paco2.update(chunk_results["max_paco2"])
            hist_spo2.update(chunk_results["min_spo2"])
            hist_qtc.update(chunk_results["max_qtc"])
            hist_dopamine.update(chunk_results["max_dopamine_peak"])
            hist_peak_mor_occupancy.update(chunk_results["peak_mor_occupancy"])
            hist_trough_free_mor.update(chunk_results["last_day_trough_free_mor_fraction"])

            # 4. Accumulate binary counters
            count_analgesia_maintained += int(chunk_results["success"].sum().item())
            count_withdrawal += int(chunk_results["withdrawal_flag"].sum().item())
            count_addiction += int(chunk_results["addiction_flag"].sum().item())
            count_resp_dep += int(chunk_results["respiratory_dep_flag"].sum().item())
            count_overdose += int(chunk_results["overdose_flag"].sum().item())
            count_fatal_overdose += int(chunk_results["fatal_overdose_flag"].sum().item())
            count_cardiac_fatal += int(chunk_results["cardiac_fatal_flag"].sum().item())
            count_mortality += int(chunk_results["mortality_flag"].sum().item())
            count_sedation += int(chunk_results["sedation_flag"].sum().item())
            count_nausea += int(chunk_results["nausea_flag"].sum().item())
            count_constipation += int(chunk_results["constipation_flag"].sum().item())

            simulated_count += chunk_n
            chunk_time = time.time() - t0_chunk
            chunk_throughput = chunk_n / max(chunk_time, 1e-6)

            if verbose:
                pct_done = (simulated_count / total_patients) * 100.0
                print(
                    f"  [Chunk {chunk_idx + 1:3d}/{n_chunks}] "
                    f"Completed: {simulated_count:,}/{total_patients:,} ({pct_done:5.1f}%) | "
                    f"Throughput: {chunk_throughput:,.0f} pts/sec"
                )

            if progress_callback:
                progress_callback(simulated_count, total_patients, chunk_throughput)

            # Reclaim GPU/CPU memory
            del batch_cohort
            del chunk_results
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

        elapsed_total = time.time() - start_time
        total_throughput = simulated_count / max(elapsed_total, 1e-6)

        # Compute percentiles (p50, p90, p99, p99.9, p99.99)
        quantiles = [50.0, 90.0, 99.0, 99.9, 99.99]
        q_keys = ["p50", "p90", "p99", "p99.9", "p99.99"]

        percentiles_dict = {
            "pain_score": {k: hist_pain.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "analgesia_level": {k: hist_analgesia.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "respiratory_drive": {k: hist_resp_drive.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "paco2_mmHg": {k: hist_paco2.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "spo2_percent": {k: hist_spo2.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "qtc_interval_ms": {k: hist_qtc.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "tolerance_level": {k: hist_tolerance.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "dopamine_peak_surge": {k: hist_dopamine.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "addiction_score": {k: hist_addiction.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "peak_mor_occupancy": {k: hist_peak_mor_occupancy.get_percentile(q) for k, q in zip(q_keys, quantiles)},
            "last_day_trough_free_mor_fraction": {k: hist_trough_free_mor.get_percentile(q) for k, q in zip(q_keys, quantiles)},
        }

        # Rates as fractions of total population
        denom = max(simulated_count, 1)
        summary = SimulationSummary(
            total_patients=simulated_count,
            device=str(self.device),
            chunk_size=effective_chunk_size,
            elapsed_seconds=round(elapsed_total, 3),
            throughput_patients_per_sec=round(total_throughput, 1),
            analgesia_maintained_rate=count_analgesia_maintained / denom,
            withdrawal_rate=count_withdrawal / denom,
            addiction_rate=count_addiction / denom,
            respiratory_depression_rate=count_resp_dep / denom,
            overdose_rate=count_overdose / denom,
            fatal_overdose_rate=count_fatal_overdose / denom,
            cardiac_fatal_rate=count_cardiac_fatal / denom,
            mortality_rate=count_mortality / denom,
            adverse_events_rates={
                "persistent_sedation": count_sedation / denom,
                "severe_nausea": count_nausea / denom,
                "constipation": count_constipation / denom,
                "severe_respiratory_depression": count_resp_dep / denom,
            },
            percentiles=percentiles_dict,
            cohort_name=cohort_cfg.name,
            protocol_compounds=protocol_cfg.compounds,
        )

        if verbose:
            print("\n=== SIMULATION RESULTS ===")
            print(f"  Patients Evaluated     : {summary.total_patients:,}")
            print(f"  Execution Time         : {summary.elapsed_seconds:.2f} s ({summary.throughput_patients_per_sec:,.0f} pts/sec)")
            print(f"  Analgesia Maintained   : {summary.analgesia_maintained_rate * 100:.2f}%")
            print(f"  Withdrawal Rate        : {summary.withdrawal_rate * 100:.2f}%")
            print(f"  Addiction / Craving    : {summary.addiction_rate * 100:.2f}%")
            print(f"  Respiratory Depression : {summary.respiratory_depression_rate * 100:.2f}%")
            print(f"  Severe Overdoses       : {summary.overdose_rate * 100:.2f}%")
            print(f"  Fatal Respiratory Arr. : {summary.fatal_overdose_rate * 100:.4f}%")
            print(f"  Cardiac Arrhythmic Mor.: {summary.cardiac_fatal_rate * 100:.4f}%")
            print(f"  Total Mortality        : {summary.mortality_rate * 100:.4f}%")
            print("  Selected Tail Percentiles:")
            print(f"    Pain Score [p50 / p90 / p99]          : {percentiles_dict['pain_score']['p50']:.2f} / {percentiles_dict['pain_score']['p90']:.2f} / {percentiles_dict['pain_score']['p99']:.2f}")
            print(f"    Min Resp Drive [p50 / p99 / p99.99]   : {percentiles_dict['respiratory_drive']['p50']:.3f} / {percentiles_dict['respiratory_drive']['p99']:.3f} / {percentiles_dict['respiratory_drive']['p99.99']:.3f}")
            print(f"    Peak PaCO2 [p50 / p99 / p99.99]       : {percentiles_dict['paco2_mmHg']['p50']:.1f} / {percentiles_dict['paco2_mmHg']['p99']:.1f} / {percentiles_dict['paco2_mmHg']['p99.99']:.1f} mmHg")
            print(f"    Peak QTc [p50 / p99 / p99.99]         : {percentiles_dict['qtc_interval_ms']['p50']:.1f} / {percentiles_dict['qtc_interval_ms']['p99']:.1f} / {percentiles_dict['qtc_interval_ms']['p99.99']:.1f} ms")
            print(f"    Dopamine Surge [p50 / p90 / p99]      : {percentiles_dict['dopamine_peak_surge']['p50']:.1f}% / {percentiles_dict['dopamine_peak_surge']['p90']:.1f}% / {percentiles_dict['dopamine_peak_surge']['p99']:.1f}%")
            print("==========================\n")

        return summary


# Export alias for compatibility
TensorSimulationEngine = TensorPopulationSimulation


# ============================================================================
# Functional API Entrypoint
# ============================================================================

def run_tensor_simulation(
    total_patients: int = 10_000_000,
    protocol: Optional[Union[TensorProtocolConfig, Dict[str, Any]]] = None,
    cohort: Union[CohortConfig, str, Dict[str, Any]] = "standard",
    chunk_size: int = 250_000,
    device: Optional[str] = None,
    seed: int = 42,
    verbose: bool = True,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
) -> SimulationSummary:
    """
    Main functional entrypoint for executing massive-scale tensor population simulations.

    Args:
        total_patients: Total virtual patient cohort size (e.g. 10,000,000 for full trials).
        protocol: Treatment protocol or drug schedule (TensorProtocolConfig or dict).
        cohort: Target cohort preset ("standard", "polysubstance_crisis", "multi_organ_failure", "zombie_market") or custom CohortConfig.
        chunk_size: Vectorized batch size per iteration (defaults to 250,000).
        device: "cuda", "cpu", or None (auto-detect).
        seed: Random seed for deterministic reproducibility.
        verbose: If True, prints streaming progress and statistical tables.
        progress_callback: Optional callback func(completed, total, throughput).

    Returns:
        SimulationSummary containing streaming rates and tail percentiles.
    """
    sim = TensorPopulationSimulation(device=device, seed=seed, chunk_size=chunk_size)
    return sim.run(
        total_patients=total_patients,
        protocol=protocol,
        cohort=cohort,
        chunk_size=chunk_size,
        verbose=verbose,
        progress_callback=progress_callback,
    )
