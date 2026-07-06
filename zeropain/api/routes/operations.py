"""Operational API routes for simulations, run registry, and compound editing."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import Job, utc_now
from zeropain.database.qihse_backend import mirror_database_record
from utils.experiment_tracking import ExperimentTracker
from opioid_analysis_tools import COMPOUND_DB, CompoundProfile
from opioid_optimization_framework import ProtocolConfig
from patient_simulation import (
    AgeDistribution,
    MedicationProfile,
    PatientGenerationConfig,
    PopulationSimulation,
)
from zeropain.cli.main import export_run
from zeropain.utils.hashing import stable_hash
from zeropain.utils.hardware import cpu_training_target

router = APIRouter()
RUN_BASE_DIR = Path(os.getenv("RUN_BASE_DIR", "runs"))
RUN_BASE_DIR.mkdir(parents=True, exist_ok=True)


class SimulationRequest(BaseModel):
    run_id: Optional[str] = None
    patient_count: int = Field(default=5000, ge=1, le=500_000)
    duration_days: int = Field(default=7, ge=1, le=365)
    seed: int = Field(default=42)
    compounds: List[str] = Field(default_factory=lambda: ["SR-17018"])
    doses: List[float] = Field(default_factory=lambda: [10.0])
    frequencies: List[float] = Field(default_factory=lambda: [2.0])
    preset: Optional[str] = Field(default=None, pattern="^(sr_combo_oxycodone|sr_combo_morphine|sr_combo_buprenorphine)$")
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


class SimulationProvenance(BaseModel):
    engine: str
    model: str
    mode: str
    decision_grade: str
    warning: str
    input_hash: str
    model_hash: str
    training_backend: str
    training_profile: str


class SimulationResponse(BaseModel):
    job_record_id: Optional[int] = None
    run_id: str
    signature_valid: bool
    signature_status: str
    metrics: SimulationMetrics
    config: Dict[str, Any]
    provenance: SimulationProvenance


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


class ProtocolPreset(BaseModel):
    preset: str
    compounds: List[str]
    doses: List[float]
    frequencies: List[float]
    warning: str


class JobStatusResponse(BaseModel):
    id: int
    job_type: str
    status: str
    payload: Dict[str, Any] | None = None
    created_at: str
    updated_at: str


@router.get("/jobs", response_model=Dict[str, List[JobStatusResponse]])
def list_jobs(
    _: Dict = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
):
    statement = select(Job).order_by(Job.updated_at.desc()).limit(max(1, min(limit, 200)))
    jobs = session.exec(statement).all()
    return {
        "jobs": [
            JobStatusResponse(
                id=job.id,
                job_type=job.job_type,
                status=job.status,
                payload=job.payload,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
            )
            for job in jobs
        ]
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: int, _: Dict = Depends(get_current_user), session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        payload=job.payload,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )


@router.get("/protocols/lead", response_model=Dict[str, List[ProtocolPreset]])
def lead_protocol_presets(_: Dict = Depends(get_current_user)):
    warning = "Virtual research starting point only; doses are placeholders for simulation sweeps, not clinical guidance."
    return {
        "presets": [
            ProtocolPreset(
                preset="sr_combo_oxycodone",
                compounds=["SR-17018", "SR-14968", "Oxycodone"],
                doses=[10.0, 10.0, 5.0],
                frequencies=[2.0, 1.0, 2.0],
                warning=warning,
            ),
            ProtocolPreset(
                preset="sr_combo_morphine",
                compounds=["SR-17018", "SR-14968", "Morphine"],
                doses=[10.0, 10.0, 5.0],
                frequencies=[2.0, 1.0, 2.0],
                warning=warning,
            ),
            ProtocolPreset(
                preset="sr_combo_buprenorphine",
                compounds=["SR-17018", "SR-14968", "Buprenorphine"],
                doses=[10.0, 10.0, 0.5],
                frequencies=[2.0, 1.0, 1.0],
                warning=warning,
            ),
        ]
    }


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


@router.get("/runs/{run_id}/export")
def export_run_bundle(run_id: str, _: Dict = Depends(get_current_user)):
    run_dir = RUN_BASE_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        bundle_path = export_run(run_dir)
    except SystemExit as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(
        path=bundle_path,
        media_type="application/zip",
        filename=bundle_path.name,
    )


@router.post("/simulate", response_model=SimulationResponse)
def simulate(
    payload: SimulationRequest,
    user: Dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    payload = _apply_protocol_preset(payload)
    _validate_protocol(payload)
    tracker = ExperimentTracker(base_dir=str(RUN_BASE_DIR), run_id=payload.run_id)
    config = payload.model_dump()
    input_hash = stable_hash(config)
    model_hash = stable_hash({"engine": "patient_simulation.PopulationSimulation", "model": "population_simulation_v1"})
    job_record = Job(
        user_id=user.get("id"),
        job_type="simulation",
        status="running",
        payload={"request": config, "input_hash": input_hash, "model_hash": model_hash},
    )
    session.add(job_record)
    session.commit()
    session.refresh(job_record)
    _mirror_job_record(job_record)

    tracker.record_config(config)
    try:
        raw_results = _run_population_simulation(payload)
        metrics = _simulation_metrics_from_results(raw_results)
        provenance = _simulation_provenance(input_hash=input_hash, model_hash=model_hash)
        tracker.log_metrics("simulation", metrics.model_dump())
        tracker.log_artifact("simulation_results.json", _jsonable(raw_results))
        tracker.log_artifact("simulation_provenance.json", provenance.model_dump())
        tracker.log_artifact(
            "cpu_training_record.json",
            _cpu_training_record(
                record_type="simulation_result",
                features=config,
                labels={**metrics.model_dump(), "raw_results": _jsonable(raw_results)},
                input_hash=input_hash,
                model_hash=model_hash,
            ),
        )
        tracker.upsert_metadata({"backend": payload.backend, "user": user.get("username")})
        tracker.append_audit_event("simulation_requested", {"patient_count": payload.patient_count})
        tracker._refresh_signature()
        ok, msg = tracker.verify_signature()
        response = SimulationResponse(
            job_record_id=job_record.id,
            run_id=tracker.run_id,
            signature_valid=ok,
            signature_status=msg,
            metrics=metrics,
            config=config,
            provenance=provenance,
        )
        job_record.status = "completed"
        job_record.updated_at = utc_now()
        job_record.payload = {
            **(job_record.payload or {}),
            "run_id": tracker.run_id,
            "response": response.model_dump(),
        }
        session.add(job_record)
        session.commit()
        _mirror_job_record(job_record)
        return response
    except Exception as exc:
        job_record.status = "failed"
        job_record.updated_at = utc_now()
        job_record.payload = {**(job_record.payload or {}), "run_id": tracker.run_id, "error": str(exc)}
        session.add(job_record)
        session.commit()
        _mirror_job_record(job_record)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc


@router.post("/settings/presets", response_model=SettingsResponse)
def save_settings(payload: SettingsPayload, user: Dict = Depends(get_current_user)):
    tracker = ExperimentTracker(base_dir=str(RUN_BASE_DIR), run_id=f"settings-{int(time.time())}")
    tracker.record_config(payload.model_dump())
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


def _simulation_metrics_from_results(results: Dict[str, Any]) -> SimulationMetrics:
    elapsed = max(float(results.get("computation_time", 0.0)), 1e-9)
    n_patients = max(float(results.get("n_patients", 0.0)), 1.0)
    medication_exposure = sum(
        value for key, value in results.items() if key.startswith("med_") and key.endswith("_rate")
    )
    return SimulationMetrics(
        analgesia_score=round(float(results.get("avg_analgesia", 0.0)), 3),
        side_effect_risk=round(float(results.get("avg_side_effects", 0.0)), 3),
        receptor_occupancy=round(float(results.get("avg_g_activation", 0.0)), 3),
        medication_exposure=round(min(1.0, medication_exposure), 3),
        throughput_per_batch=round(n_patients / elapsed, 2),
    )


def _simulation_provenance(input_hash: str, model_hash: str) -> SimulationProvenance:
    target = cpu_training_target()
    return SimulationProvenance(
        engine="patient_simulation.PopulationSimulation",
        model="population_simulation_v1",
        mode="aggregate_patient_simulation",
        decision_grade="false",
        warning="Research simulation only; not validated for clinical or dosing decisions.",
        input_hash=input_hash,
        model_hash=model_hash,
        training_backend="cpu",
        training_profile=target["target_profile"],
    )


def _run_population_simulation(payload: SimulationRequest) -> Dict[str, Any]:
    generation_config = _generation_config_from_payload(payload)
    protocol = ProtocolConfig(
        compounds=payload.compounds,
        doses=payload.doses,
        frequencies=payload.frequencies,
        duration=payload.duration_days,
    )
    simulation = PopulationSimulation(COMPOUND_DB, use_multiprocessing=False)
    return simulation.run_simulation(
        protocol,
        n_patients=payload.patient_count,
        duration_days=payload.duration_days,
        seed=payload.seed,
        generation_config=generation_config,
        batch_size=payload.batch_size,
    )


def _apply_protocol_preset(payload: SimulationRequest) -> SimulationRequest:
    if not payload.preset:
        return payload
    presets = {
        "sr_combo_oxycodone": (["SR-17018", "SR-14968", "Oxycodone"], [10.0, 10.0, 5.0], [2.0, 1.0, 2.0]),
        "sr_combo_morphine": (["SR-17018", "SR-14968", "Morphine"], [10.0, 10.0, 5.0], [2.0, 1.0, 2.0]),
        "sr_combo_buprenorphine": (["SR-17018", "SR-14968", "Buprenorphine"], [10.0, 10.0, 0.5], [2.0, 1.0, 1.0]),
    }
    compounds, doses, frequencies = presets[payload.preset]
    data = payload.model_dump()
    if payload.compounds == ["SR-17018"] and payload.doses == [10.0] and payload.frequencies == [2.0]:
        data.update({"compounds": compounds, "doses": doses, "frequencies": frequencies})
    return SimulationRequest(**data)


def _generation_config_from_payload(payload: SimulationRequest) -> PatientGenerationConfig:
    min_age = int(max(0, payload.age_mean - (2 * payload.age_std)))
    max_age = int(min(110, payload.age_mean + (2 * payload.age_std)))
    if min_age >= max_age:
        min_age = int(max(0, payload.age_mean - 1))
        max_age = int(min(110, payload.age_mean + 1))
    cfg = PatientGenerationConfig(
        population_size=payload.patient_count,
        sex_ratio_male=1.0 - payload.sex_ratio_female,
        age_distribution=AgeDistribution(alpha=2.0, beta=2.0, min_age=min_age, max_age=max_age),
    )
    cfg.pre_existing_medications["configured_baseline_tolerance"] = MedicationProfile(
        name="Configured baseline tolerance",
        prevalence=1.0,
        baseline_tolerance=payload.baseline_tolerance,
    )
    if cfg.pre_existing_medications:
        scale = payload.medication_prevalence / max(
            1e-9,
            sum(profile.prevalence for profile in cfg.pre_existing_medications.values())
            / len(cfg.pre_existing_medications),
        )
        for profile in cfg.pre_existing_medications.values():
            profile.prevalence = min(1.0, max(0.0, profile.prevalence * scale))
    return cfg


def _validate_protocol(payload: SimulationRequest) -> None:
    if not (len(payload.compounds) == len(payload.doses) == len(payload.frequencies)):
        raise HTTPException(status_code=422, detail="compounds, doses, and frequencies must have equal length")
    missing = [name for name in payload.compounds if not COMPOUND_DB.get_compound(name)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown compounds: {', '.join(missing)}")


def _jsonable(payload: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(payload, default=lambda value: float(value) if hasattr(value, "__float__") else str(value)))


def _cpu_training_record(
    record_type: str,
    features: Dict[str, Any],
    labels: Dict[str, Any],
    input_hash: str,
    model_hash: str,
) -> Dict[str, Any]:
    return {
        "record_type": record_type,
        "target": cpu_training_target(),
        "input_hash": input_hash,
        "model_hash": model_hash,
        "features": features,
        "labels": labels,
    }


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


def _mirror_job_record(job_record: Job) -> None:
    mirror_database_record(
        "jobs",
        str(job_record.id),
        {
            "id": job_record.id,
            "job_type": job_record.job_type,
            "status": job_record.status,
            "payload": job_record.payload,
            "created_at": job_record.created_at.isoformat(),
            "updated_at": job_record.updated_at.isoformat(),
        },
    )


__all__ = [
    "router",
]
