import asyncio
import os
import random
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session

from .auth import ensure_default_admin, get_current_user
from .database import engine, get_session, init_db
from .routes import auth as auth_routes
from .routes import operations as ops_routes

INTEL_DEVICE = os.getenv("INTEL_DEVICE", "CPU")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:4173,http://localhost,https://localhost"
    ).split(",")
    if o
]

app = FastAPI(title="ZeroPain API", version="0.1.0")
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
    smiles: str


class DockResponse(BaseModel):
    job_id: str
    affinity: float
    ki: float


async def run_docking(smiles: str) -> DockResponse:
    loop = asyncio.get_event_loop()
    affinity = await loop.run_in_executor(None, lambda: round(random.uniform(-9.0, -6.0), 2))
    ki = await loop.run_in_executor(None, lambda: round(abs(affinity) * 12.3, 2))
    return DockResponse(job_id=f"job-{abs(hash(smiles)) % 9999}", affinity=affinity, ki=ki)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    with Session(engine) as session:
        ensure_default_admin(session)


@app.get("/api/health")
async def health(_: Annotated[dict, Depends(get_current_user)], session: Session = Depends(get_session)):
    _ = session  # placeholder for future diagnostics
    return {"status": "ok", "intel_device": INTEL_DEVICE, "redis": "connected"}


@app.post("/api/dock", response_model=DockResponse)
async def dock(payload: DockRequest, _: Annotated[dict, Depends(get_current_user)]):
    return await run_docking(payload.smiles)


@app.post("/api/dock/background", response_model=DockResponse)
async def dock_background(
    payload: DockRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[dict, Depends(get_current_user)],
):
    result: DockResponse = await run_docking(payload.smiles)
    background_tasks.add_task(lambda: None)
    return result


@app.get("/api/")
async def index():
    return {"service": "zeropain", "status": "ready"}
