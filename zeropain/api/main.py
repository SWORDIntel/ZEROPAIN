import asyncio
import json
import os
from contextlib import asynccontextmanager
from math import exp
from pathlib import Path
from typing import Annotated, Optional

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import Session

from .auth import ensure_default_admin, get_current_user
from .database import database_backend_status, engine, get_session, init_db
from .models import Job, utc_now
from .routes import auth as auth_routes
from .routes import operations as ops_routes
from zeropain.database.qihse_backend import mirror_database_record
from zeropain.docking import DockingJobSpec, run_docking_job
from zeropain.utils.hashing import stable_hash
from zeropain.utils.hardware import cpu_training_target

INTEL_DEVICE = os.getenv("INTEL_DEVICE", "CPU")
RUN_BASE_DIR = Path(os.getenv("RUN_BASE_DIR", "runs"))
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:4173,http://localhost,https://localhost"
    ).split(",")
    if o
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(engine) as session:
        ensure_default_admin(session)
    yield


app = FastAPI(title="ZeroPain API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_routes.router, prefix="/api")
app.include_router(ops_routes.router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DockRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    receptor: str = Field(default="MOR", min_length=1)
    backend: str = Field(default="python_ref", pattern="^(python_ref|mocked)$")
    hardware: str = Field(default="CPU", pattern="^(CPU|GPU|NPU|AUTO)$")
    poses_per_ligand: int = Field(default=5, ge=1, le=20)


class DockResponse(BaseModel):
    job_record_id: Optional[int] = None
    job_id: str
    affinity: float
    ki: float
    backend: str
    device: str
    poses: int
    artifacts: dict[str, str]
    provenance: dict[str, str]


@app.get("/api/health")
async def health(_: Annotated[dict, Depends(get_current_user)], session: Session = Depends(get_session)):
    _ = session  # placeholder for future diagnostics
    return {
        "status": "ok",
        "compute_backend": "cpu",
        "intel_device": INTEL_DEVICE,
        "cpu_training_target": cpu_training_target(),
        "database_backend": database_backend_status().as_dict(),
        "redis": "connected",
    }


@app.post("/api/dock", response_model=DockResponse)
async def dock(
    payload: DockRequest,
    user: Annotated[dict, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    return await _run_docking_payload(payload, session, user)


@app.post("/api/dock/background", response_model=DockResponse)
async def dock_background(
    payload: DockRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[dict, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    result: DockResponse = await _run_docking_payload(payload, session, user)
    background_tasks.add_task(lambda: None)
    return result


@app.get("/api/")
async def index():
    return {"service": "zeropain", "status": "ready"}


async def _run_docking_payload(payload: DockRequest, session: Session, user: dict) -> DockResponse:
    payload_data = payload.model_dump()
    input_hash = stable_hash(payload_data)
    model_hash = stable_hash({"engine": "zeropain.docking.pipeline", "model": payload.backend})
    job_record = Job(
        user_id=user.get("id"),
        job_type="docking",
        status="running",
        payload={"request": payload_data, "input_hash": input_hash, "model_hash": model_hash},
    )
    session.add(job_record)
    session.commit()
    session.refresh(job_record)
    _mirror_job_record(job_record)

    loop = asyncio.get_running_loop()
    job = DockingJobSpec(
        receptor=payload.receptor,
        ligands=[payload.smiles],
        backend=payload.backend,
        hardware=payload.hardware,
        poses_per_ligand=payload.poses_per_ligand,
        run_dir=RUN_BASE_DIR,
    )
    try:
        result = await loop.run_in_executor(None, lambda: run_docking_job(job))
    except Exception as exc:
        job_record.status = "failed"
        job_record.updated_at = utc_now()
        job_record.payload = {**(job_record.payload or {}), "error": str(exc)}
        session.add(job_record)
        session.commit()
        _mirror_job_record(job_record)
        raise

    best_pose = min(result.poses, key=lambda pose: pose.score)
    affinity = round(best_pose.score, 4)
    response = DockResponse(
        job_record_id=job_record.id,
        job_id=result.job_id,
        affinity=affinity,
        ki=round(_affinity_to_ki_nm(affinity), 4),
        backend=result.backend,
        device=result.device,
        poses=len(result.poses),
        artifacts=result.artifacts,
        provenance={
            "engine": "zeropain.docking.pipeline",
            "model": result.backend,
            "mode": "deterministic_reference_backend",
            "decision_grade": "false",
            "input_hash": input_hash,
            "model_hash": model_hash,
            "training_backend": "cpu",
            "training_profile": cpu_training_target()["target_profile"],
        },
    )
    _write_docking_training_record(
        job.job_id,
        payload_data,
        response.model_dump(),
        input_hash,
        model_hash,
    )
    job_record.status = "completed"
    job_record.updated_at = utc_now()
    job_record.payload = {**(job_record.payload or {}), "run_id": result.job_id, "response": response.model_dump()}
    session.add(job_record)
    session.commit()
    _mirror_job_record(job_record)
    return response


def _affinity_to_ki_nm(affinity_kcal_mol: float) -> float:
    """Convert docking free energy estimate to Ki at 298 K."""

    return exp(affinity_kcal_mol / 0.592) * 1e9


def _write_docking_training_record(
    job_id: str,
    request: dict,
    response: dict,
    input_hash: str,
    model_hash: str,
) -> None:
    record = {
        "record_type": "docking_result",
        "target": cpu_training_target(),
        "input_hash": input_hash,
        "model_hash": model_hash,
        "features": request,
        "labels": {
            "affinity": response.get("affinity"),
            "ki": response.get("ki"),
            "backend": response.get("backend"),
            "device": response.get("device"),
            "poses": response.get("poses"),
        },
    }
    out = RUN_BASE_DIR / job_id / "docking" / "cpu_training_record.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")


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
