"""Operational API routes for simulations, run registry, and compound editing."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user
from utils.experiment_tracking import ExperimentTracker
from opioid_analysis_tools import COMPOUND_DB, CompoundProfile

router = APIRouter()
RUN_BASE_DIR = Path(os.getenv("RUN_BASE_DIR", "runs"))
RUN_BASE_DIR.mkdir(parents=True, exist_ok=True)


class SimulationRequest(BaseModel):
    run_id: Optional[str] = None
    patient_count: int = Field(default=5000, ge=1, le=500_000)
    backend: str = Field(default="local", pattern="^(local|ray|dask)$")
    resume: bool = True
    batch_size: int = Field(default=256, ge=1, le=10_000)
    age_mean: float = Field(default=45.0, ge=0, le=110)
    age_std: float = Field(default=15.0, ge=0, le=40)
    sex_ratio_female: float = Field(default=0.5, ge=0, le=1)
    medication_prevalence: float = Field(default=0.2, ge=0, le=1)
    baseline_tolerance: float = Field(default=0.1, ge=0, le=1)
    receptor_target: str = Field(default="MOR")


class SimulationMetrics(BaseModel):
    analgesia_score: float
    side_effect_risk: float
    receptor_occupancy: float
    medication_exposure: float
    throughput_per_batch: float


class SimulationResponse(BaseModel):
    run_id: str
    signature_valid: bool
    signature_status: str
    metrics: SimulationMetrics
    config: Dict[str, Any]


class SettingsPayload(BaseModel):
    backend: str = Field(default="local")
    resume: bool = True
    batch_size: int = Field(default=256, ge=1, le=10_000)
    poll_interval_ms: int = Field(default=8000, ge=1000, le=60000)
    animations: bool = True


class SettingsResponse(BaseModel):
    saved: bool
    signature_valid: bool
    signature_status: str
    run_id: str


class CustomCompoundRequest(BaseModel):
    name: str
    ki_orthosteric: float
    ki_allosteric1: float = Field(default=float("inf"))
    ki_allosteric2: float = Field(default=float("inf"))
    g_protein_bias: float = Field(default=1.0, ge=0)
    beta_arrestin_bias: float = Field(default=1.0, ge=0)
    t_half: float = Field(default=3.0, ge=0)
    bioavailability: float = Field(default=0.3, ge=0, le=1)
    intrinsic_activity: float = Field(default=1.0, ge=0, le=1)
    tolerance_rate: float = Field(default=0.5, ge=0, le=1)
    prevents_withdrawal: bool = False
    reverses_tolerance: bool = False
    receptor_type: str = Field(default="MOR")
    pharmacological_activities: List[str] = Field(default_factory=list)
    mechanism_notes: str = ""
    run_id: Optional[str] = None


class CustomCompoundResponse(BaseModel):
    run_id: str
    compound: Dict[str, Any]
    signature_valid: bool
    signature_status: str


class RunSummary(BaseModel):
    run_id: str
    created_utc: Optional[str] = None
    backend: Optional[str] = None
    signature_valid: bool
    signature_status: str


class RunDetail(BaseModel):
    summary: RunSummary
    metadata: Dict[str, Any]
    metrics: List[Dict[str, Any]]
    audit: List[Dict[str, Any]]


@router.get("/runs", response_model=Dict[str, List[RunSummary]])
def list_runs(_: Dict = Depends(get_current_user)):
    runs: List[RunSummary] = []
    for path in sorted(RUN_BASE_DIR.glob("*/metadata.json"), reverse=True):
        run_dir = path.parent
        meta = _read_json(path)
        ok, msg = ExperimentTracker.verify_signature_for_run(run_dir)
        runs.append(
            RunSummary(
                run_id=run_dir.name,
                created_utc=meta.get("created_utc"),
                backend=meta.get("backend"),
                signature_valid=ok,
                signature_status=msg,
            )
        )
    return {"runs": runs}


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, _: Dict = Depends(get_current_user)):
    run_dir = RUN_BASE_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    meta = _read_json(run_dir / "metadata.json")
    config = _read_json(run_dir / "config.json")
    audit = _read_json_lines(run_dir / "audit.jsonl")
    metrics = _read_json_lines(run_dir / "metrics.jsonl")
    ok, msg = ExperimentTracker.verify_signature_for_run(run_dir)
    summary = RunSummary(
        run_id=run_id,
        created_utc=meta.get("created_utc"),
        backend=meta.get("backend"),
        signature_valid=ok,
        signature_status=msg,
    )
    merged_meta = {**meta, **{k: v for k, v in (config or {}).items() if k not in meta}}
    return RunDetail(summary=summary, metadata=merged_meta, metrics=metrics, audit=audit)


@router.post("/simulate", response_model=SimulationResponse)
def simulate(payload: SimulationRequest, user: Dict = Depends(get_current_user)):
    tracker = ExperimentTracker(base_dir=str(RUN_BASE_DIR), run_id=payload.run_id)
    tracker.record_config(payload.dict())
    metrics = _derive_sim_metrics(payload)
    tracker.log_metrics("simulation", metrics.dict())
    tracker.upsert_metadata({"backend": payload.backend, "user": user.get("username")})
    tracker.append_audit_event("simulation_requested", {"patient_count": payload.patient_count})
    tracker._refresh_signature()
    ok, msg = tracker.verify_signature()
    return SimulationResponse(
        run_id=tracker.run_id,
        signature_valid=ok,
        signature_status=msg,
        metrics=metrics,
        config=payload.dict(),
    )


@router.post("/settings/presets", response_model=SettingsResponse)
def save_settings(payload: SettingsPayload, user: Dict = Depends(get_current_user)):
    tracker = ExperimentTracker(base_dir=str(RUN_BASE_DIR), run_id=f"settings-{int(time.time())}")
    tracker.record_config(payload.dict())
    tracker.append_audit_event("settings_saved", {"user": user.get("username")})
    tracker._refresh_signature()
    ok, msg = tracker.verify_signature()
    return SettingsResponse(saved=True, signature_valid=ok, signature_status=msg, run_id=tracker.run_id)


@router.get("/settings/defaults", response_model=SettingsPayload)
def default_settings(_: Dict = Depends(get_current_user)):
    return SettingsPayload()


@router.get("/compounds/library")
def compound_library(_: Dict = Depends(get_current_user)):
    data = []
    for name in COMPOUND_DB.list_compounds():
        compound = COMPOUND_DB.get_compound(name)
        if not compound:
            continue
        bias = compound.get_bias_ratio()
        bias = 9999 if bias == float("inf") else bias
        data.append({
            "name": compound.name,
            "receptor_type": compound.receptor_type,
            "ki_orthosteric": compound.ki_orthosteric,
            "t_half": compound.t_half,
            "bias": bias,
            "bioavailability": compound.bioavailability,
            "activities": compound.pharmacological_activities,
            "safety": compound.calculate_safety_score(),
        })
    return {"compounds": data}


@router.post("/compounds/custom", response_model=CustomCompoundResponse)
def add_custom_compound(payload: CustomCompoundRequest, user: Dict = Depends(get_current_user)):
    profile = CompoundProfile(
        name=payload.name,
        ki_orthosteric=payload.ki_orthosteric,
        ki_allosteric1=payload.ki_allosteric1,
        ki_allosteric2=payload.ki_allosteric2,
        g_protein_bias=payload.g_protein_bias,
        beta_arrestin_bias=payload.beta_arrestin_bias,
        t_half=payload.t_half,
        bioavailability=payload.bioavailability,
        intrinsic_activity=payload.intrinsic_activity,
        tolerance_rate=payload.tolerance_rate,
        prevents_withdrawal=payload.prevents_withdrawal,
        reverses_tolerance=payload.reverses_tolerance,
        receptor_type=payload.receptor_type,
        pharmacological_activities=payload.pharmacological_activities,
        mechanism_notes=payload.mechanism_notes,
    )
    COMPOUND_DB.add_custom_compound(profile)
    tracker = ExperimentTracker(base_dir=str(RUN_BASE_DIR), run_id=payload.run_id)
    tracker.log_artifact(f"compound_{payload.name}.json", profile.to_dict())
    tracker.append_audit_event("custom_compound_saved", {"name": payload.name, "user": user.get("username")})
    tracker._refresh_signature()
    ok, msg = tracker.verify_signature()
    return CustomCompoundResponse(
        run_id=tracker.run_id,
        compound=profile.to_dict(),
        signature_valid=ok,
        signature_status=msg,
    )


def _derive_sim_metrics(payload: SimulationRequest) -> SimulationMetrics:
    occupancy = min(1.0, (payload.patient_count / 50_000) * (0.35 + payload.medication_prevalence * 0.25))
    analgesia = min(1.0, 0.45 + payload.medication_prevalence * 0.2 + payload.baseline_tolerance * 0.25 + occupancy * 0.2)
    side_effects = min(
        1.0,
        0.25
        + (1 - payload.sex_ratio_female) * 0.05
        + payload.age_mean / 200
        + payload.baseline_tolerance * 0.3,
    )
    throughput = round(payload.batch_size / max(payload.age_std, 1.0), 2)
    return SimulationMetrics(
        analgesia_score=round(analgesia, 3),
        side_effect_risk=round(side_effects, 3),
        receptor_occupancy=round(occupancy, 3),
        medication_exposure=round(payload.medication_prevalence, 3),
        throughput_per_batch=throughput,
    )


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {}


def _read_json_lines(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


__all__ = [
    "router",
]
