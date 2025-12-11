"""
PK/PD calibration utilities (NumPy/SciPy).
Provides population priors, simple covariate effects, and adaptive dosing hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple
import json
import math

import numpy as np
from scipy.optimize import minimize
from scipy.stats import lognorm


# -----------------------
# Data structures
# -----------------------


@dataclass
class PriorSpec:
    """Log-normal prior for PK parameters."""

    mu: float
    sigma: float
    lower: Optional[float] = None
    upper: Optional[float] = None

    def sample(self, rng: np.random.Generator) -> float:
        draw = lognorm(s=self.sigma, scale=math.exp(self.mu)).rvs(random_state=rng)
        if self.lower is not None:
            draw = max(draw, self.lower)
        if self.upper is not None:
            draw = min(draw, self.upper)
        return float(draw)


@dataclass
class CovariateMapping:
    """Linear covariate model: eta = X * beta."""

    betas: Dict[str, float] = field(default_factory=dict)
    interactions: Dict[Tuple[str, str], float] = field(default_factory=dict)

    def effect(self, covariates: Dict[str, float]) -> float:
        eta = 0.0
        for name, beta in self.betas.items():
            eta += beta * covariates.get(name, 0.0)
        for (a, b), beta in self.interactions.items():
            eta += beta * covariates.get(a, 0.0) * covariates.get(b, 0.0)
        return eta


@dataclass
class PKPDConfig:
    """Configuration for PK/PD calibration."""

    model: str = "one_compartment"
    priors: Dict[str, PriorSpec] = field(default_factory=dict)
    covariates: Dict[str, CovariateMapping] = field(default_factory=dict)
    use_off_diagonal: bool = False

    @staticmethod
    def from_dict(payload: Dict) -> "PKPDConfig":
        priors = {
            name: PriorSpec(
                mu=spec.get("mu", 0.0),
                sigma=spec.get("sigma", 0.5),
                lower=spec.get("lower"),
                upper=spec.get("upper"),
            )
            for name, spec in payload.get("priors", {}).items()
        }
        covariates = {
            name: CovariateMapping(
                betas=spec.get("betas", {}),
                interactions={
                    tuple(k.split("*")): v for k, v in spec.get("interactions", {}).items()
                },
            )
            for name, spec in payload.get("covariates", {}).items()
        }
        return PKPDConfig(
            model=payload.get("model", "one_compartment"),
            priors=priors,
            covariates=covariates,
            use_off_diagonal=payload.get("covariance", {}).get("use_off_diagonal", False),
        )


@dataclass
class DoseDecision:
    dose_mg: float
    rationale: str
    policy: str


# -----------------------
# Adaptive dosing policies
# -----------------------


class DosingPolicy:
    def propose_dose(self, state: Dict, pk_summary: Dict, pd_summary: Dict, constraints: Dict) -> DoseDecision:
        raise NotImplementedError


class FixedDosePolicy(DosingPolicy):
    def __init__(self, dose_mg: float):
        self.dose_mg = dose_mg

    def propose_dose(self, state: Dict, pk_summary: Dict, pd_summary: Dict, constraints: Dict) -> DoseDecision:
        return DoseDecision(dose_mg=self.dose_mg, rationale="fixed", policy="fixed")


class ExposureTargetPolicy(DosingPolicy):
    def __init__(self, target_auc: float, tolerance: float = 0.1, max_dose: float = 400.0):
        self.target_auc = target_auc
        self.tolerance = tolerance
        self.max_dose = max_dose

    def propose_dose(self, state: Dict, pk_summary: Dict, pd_summary: Dict, constraints: Dict) -> DoseDecision:
        auc = pk_summary.get("auc", 0.0)
        current_dose = state.get("current_dose_mg", constraints.get("default_dose_mg", 100.0))
        if auc <= 0:
            return DoseDecision(dose_mg=current_dose, rationale="fallback_auc", policy="exposure_target")
        ratio = self.target_auc / auc
        new_dose = min(current_dose * ratio, self.max_dose)
        new_dose = max(new_dose, constraints.get("min_dose_mg", 10.0))
        return DoseDecision(
            dose_mg=new_dose,
            rationale=f"target_auc={self.target_auc}",
            policy="exposure_target",
        )


class ToxicityConstrainedPolicy(DosingPolicy):
    def __init__(self, max_toxicity_prob: float = 0.05, step_mg: float = 10.0):
        self.max_toxicity_prob = max_toxicity_prob
        self.step_mg = step_mg

    def propose_dose(self, state: Dict, pk_summary: Dict, pd_summary: Dict, constraints: Dict) -> DoseDecision:
        tox_prob = pd_summary.get("toxicity_prob", 0.0)
        current_dose = state.get("current_dose_mg", constraints.get("default_dose_mg", 100.0))
        if tox_prob > self.max_toxicity_prob:
            new_dose = max(constraints.get("min_dose_mg", 10.0), current_dose - self.step_mg)
            rationale = f"tox_prob={tox_prob:.3f} > {self.max_toxicity_prob}"
        else:
            new_dose = min(constraints.get("max_dose_mg", 400.0), current_dose + self.step_mg)
            rationale = f"tox_prob={tox_prob:.3f} within limit"
        return DoseDecision(dose_mg=new_dose, rationale=rationale, policy="toxicity_constrained")


# -----------------------
# Calibration core
# -----------------------


def one_compartment(t: np.ndarray, dose: float, ka: float, cl: float, v: float) -> np.ndarray:
    # Simple oral absorption one-compartment with first-order absorption and elimination
    return (dose * ka / (v * (ka - cl / v))) * (np.exp(-cl * t / v) - np.exp(-ka * t))


def two_compartment(t: np.ndarray, dose: float, k12: float, k21: float, ke: float, v1: float) -> np.ndarray:
    # Simplified two-compartment (not full macro-constants), approximate split
    alpha = ke + k12
    beta = k21
    A = dose / v1
    return A * (np.exp(-alpha * t) + np.exp(-beta * t)) / 2.0


def _negative_log_posterior(params: np.ndarray, t: np.ndarray, y: np.ndarray, priors: Dict[str, PriorSpec], model: str, dose: float) -> float:
    # unpack params respecting model
    if model == "one_compartment":
        ka, cl, v = params
        pred = one_compartment(t, dose, ka=abs(ka), cl=abs(cl), v=abs(v))
    else:
        k12, k21, ke, v1 = params
        pred = two_compartment(t, dose, k12=abs(k12), k21=abs(k21), ke=abs(ke), v1=abs(v1))

    # likelihood: Gaussian with fixed sigma
    sigma = max(np.std(y) * 0.1, 1e-3)
    ll = -0.5 * np.sum(((y - pred) / sigma) ** 2)

    # priors
    lp = 0.0
    names = ["ka", "cl", "v"] if model == "one_compartment" else ["k12", "k21", "ke", "v1"]
    for val, name in zip(params, names):
        prior = priors.get(name)
        if prior:
            lp += lognorm.logpdf(abs(val), s=prior.sigma, scale=math.exp(prior.mu))

    return -(ll + lp)


def calibrate_pkpd(config: PKPDConfig, observations: Dict) -> Dict:
    """
    Calibrate PK/PD parameters using MAP (NumPy/SciPy).
    observations: {\"time\": [...], \"conc\": [...], \"dose\": float}
    """
    t = np.asarray(observations.get("time", []), dtype=float)
    y = np.asarray(observations.get("conc", []), dtype=float)
    dose = float(observations.get("dose", 100.0))

    if t.size == 0 or y.size == 0:
        # synth dataset for robustness
        t = np.linspace(0, 24, 24)
        y = one_compartment(t, dose=dose, ka=1.0, cl=8.0, v=50.0)

    model = config.model
    if model == "one_compartment":
        x0 = np.array([
            config.priors.get("ka", PriorSpec(0.0, 0.5)).sample(np.random.default_rng()),
            config.priors.get("cl", PriorSpec(2.0, 0.5)).sample(np.random.default_rng()),
            config.priors.get("v", PriorSpec(3.5, 0.5)).sample(np.random.default_rng()),
        ])
    else:
        x0 = np.array([
            config.priors.get("k12", PriorSpec(-1.0, 0.5)).sample(np.random.default_rng()),
            config.priors.get("k21", PriorSpec(-1.0, 0.5)).sample(np.random.default_rng()),
            config.priors.get("ke", PriorSpec(-1.0, 0.5)).sample(np.random.default_rng()),
            config.priors.get("v1", PriorSpec(3.5, 0.5)).sample(np.random.default_rng()),
        ])

    res = minimize(
        _negative_log_posterior,
        x0,
        args=(t, y, config.priors, model, dose),
        method="L-BFGS-B",
    )

    fitted = res.x
    names = ["ka", "cl", "v"] if model == "one_compartment" else ["k12", "k21", "ke", "v1"]
    params = {name: float(abs(val)) for name, val in zip(names, fitted)}

    pk_summary = {
        "auc": float(np.trapz(one_compartment(t, dose, params.get("ka", 1.0), params.get("cl", 1.0), params.get("v", 1.0)), t))
        if model == "one_compartment"
        else float(np.trapz(two_compartment(t, dose, params.get("k12", 0.1), params.get("k21", 0.1), params.get("ke", 0.1), params.get("v1", 10.0)), t)),
        "cmax": float(np.max(y) if y.size else 0.0),
        "params": params,
        "success": bool(res.success),
        "loss": float(res.fun),
        "iterations": res.nit,
    }

    return {
        "pk_summary": pk_summary,
        "config": _config_to_dict(config),
        "diagnostics": {
            "message": res.message,
            "status": int(res.status),
        },
    }


def _config_to_dict(config: PKPDConfig) -> Dict:
    return {
        "model": config.model,
        "priors": {
            k: {"mu": v.mu, "sigma": v.sigma, "lower": v.lower, "upper": v.upper}
            for k, v in config.priors.items()
        },
        "covariates": {
            k: {"betas": v.betas, "interactions": {f\"{a}*{b}\": w for (a, b), w in v.interactions.items()}}
            for k, v in config.covariates.items()
        },
        "use_off_diagonal": config.use_off_diagonal,
    }


def load_pkpd_config(path: str) -> PKPDConfig:
    with open(path, "r") as f:
        payload = json.load(f) if path.endswith(".json") else _load_yaml(f.read())
    return PKPDConfig.from_dict(payload.get("pkpd", payload))


def _load_yaml(text: str) -> Dict:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        return {}

