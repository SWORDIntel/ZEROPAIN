"""
Scenario templates and cohort generators for ZeroPain simulations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from patient_simulation_100k import PatientGenerationConfig, AgeDistribution, WeightDistribution


@dataclass
class CohortSpec:
    n: int = 200
    age_mean: float = 60.0
    age_std: float = 10.0
    weight_mean: float = 80.0
    weight_std: float = 15.0
    sex_ratio_male: float = 0.5
    renal_impaired_rate: float = 0.1
    hepatic_impaired_rate: float = 0.05
    baseline_tolerance: float = 0.05
    seed: Optional[int] = None


SCENARIO_TEMPLATES: Dict[str, Dict] = {
    "perioperative": {
        "horizon_days": 14,
        "taper": True,
        "monitor_days": 1,
        "objectives": {"pain_control": 0.8, "tolerance_cap": 0.2, "withdrawal_risk": 0.0},
    },
    "chronic": {
        "horizon_days": 90,
        "taper": False,
        "monitor_days": 7,
        "objectives": {"pain_control": 0.7, "tolerance_cap": 0.3, "withdrawal_risk": 0.05},
    },
    "breakthrough": {
        "horizon_days": 30,
        "taper": True,
        "monitor_days": 3,
        "objectives": {"pain_control": 0.85, "tolerance_cap": 0.25, "withdrawal_risk": 0.02},
    },
}


def build_generation_config(cohort: CohortSpec) -> PatientGenerationConfig:
    rng = np.random.default_rng(cohort.seed)
    age_dist = AgeDistribution(alpha=2.0, beta=3.0, min_age=18, max_age=90)
    weight_dist = WeightDistribution(
        male_mean=cohort.weight_mean + 5,
        male_std=cohort.weight_std,
        female_mean=max(45.0, cohort.weight_mean - 5),
        female_std=cohort.weight_std,
        min_weight=45.0,
        max_weight=140.0,
    )
    cfg = PatientGenerationConfig(
        population_size=cohort.n,
        sex_ratio_male=cohort.sex_ratio_male,
        age_distribution=age_dist,
        weight_distribution=weight_dist,
    )
    # adjust comorbidities for renal/hepatic
    cfg.comorbidity_prevalence["kidney_disease"] = cohort.renal_impaired_rate
    cfg.comorbidity_prevalence["liver_disease"] = cohort.hepatic_impaired_rate
    return cfg


def parse_cohort_spec(spec: str) -> CohortSpec:
    """
    Parse cohort spec like 'n=200,age=60±10,renal=0.3,hepatic=0.1,seed=42'
    """
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    params: Dict[str, float] = {}
    seed = None
    for part in parts:
        if "±" in part:
            key, rest = part.split("=")
            mean, std = rest.split("±")
            params[f"{key}_mean"] = float(mean)
            params[f"{key}_std"] = float(std)
        elif "=" in part:
            key, val = part.split("=")
            if key == "seed":
                seed = int(val)
            else:
                params[key] = float(val)
    return CohortSpec(
        n=int(params.get("n", 200)),
        age_mean=params.get("age_mean", 60.0),
        age_std=params.get("age_std", 10.0),
        weight_mean=params.get("weight_mean", 80.0),
        weight_std=params.get("weight_std", 15.0),
        sex_ratio_male=params.get("sex_ratio_male", 0.5),
        renal_impaired_rate=params.get("renal", 0.1),
        hepatic_impaired_rate=params.get("hepatic", 0.05),
        baseline_tolerance=params.get("baseline_tolerance", 0.05),
        seed=seed,
    )


def scenario_defaults(scenario_id: str) -> Dict:
    return SCENARIO_TEMPLATES.get(scenario_id, {})

