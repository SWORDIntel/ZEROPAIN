#!/usr/bin/env python3
"""
ZeroPain FastAPI Backend
RESTful API for molecular therapeutics platform

IMPORTANT: CPU-Bound Operations and Event Loop
--------------------------------------------
This API handles CPU-intensive operations (molecular docking, multiprocessing)
that must not block the asyncio event loop. Pattern to use:

    async def background_task():
        # For CPU-bound work, use run_in_executor to keep API responsive
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # Uses default ThreadPoolExecutor
            cpu_intensive_function,
            *args
        )

Without this pattern, the event loop blocks and all API/WebSocket connections freeze.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import asyncio
import json
from datetime import datetime
import uuid

# Import ZeroPain modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zeropain.molecular.docking import AutoDockVina, DockingResult
from zeropain.molecular.structure import from_smiles, MolecularStructure
from zeropain.molecular.intel_ai import IntelAIMolecularPredictor, ADMETPredict
from zeropain.molecular.binding_analysis import BindingAnalyzer

# Initialize FastAPI app
app = FastAPI(
    title="ZeroPain Therapeutics API",
    description="Professional Molecular Therapeutics Platform - REST API",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
docking_engine = AutoDockVina()
ai_predictor = IntelAIMolecularPredictor()
binding_analyzer = BindingAnalyzer()

# In-memory job storage (use Redis in production)
active_jobs = {}
completed_jobs = {}


# ============================================================================
# Pydantic Models
# ============================================================================

class CompoundInput(BaseModel):
    name: str = Field(..., description="Compound name")
    smiles: str = Field(..., description="SMILES string")

class DockingRequest(BaseModel):
    compound_name: str
    smiles: str
    receptor: str = Field(default="MOR", description="MOR, DOR, or KOR")
    exhaustiveness: int = Field(default=8, ge=1, le=32)
    num_modes: int = Field(default=9, ge=1, le=20)

class BatchDockingRequest(BaseModel):
    compounds: List[CompoundInput]
    receptor: str = "MOR"
    exhaustiveness: int = 8

class ADMETRequest(BaseModel):
    smiles: str

class OptimizationRequest(BaseModel):
    compounds: List[str]
    n_patients: int = Field(default=1000, ge=100, le=10000)
    max_iterations: int = Field(default=100, ge=10, le=500)

class SimulationRequest(BaseModel):
    protocol: Dict
    n_patients: int = Field(default=10000, ge=100, le=500000)
    duration_days: int = Field(default=90, ge=1, le=365)

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, running, completed, failed
    progress: float
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


# ============================================================================
# Health & System Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "ZeroPain Therapeutics API",
        "version": "4.0.0",
        "status": "operational",
        "docs": "/api/docs",
        "endpoints": {
            "molecular": "/api/molecular",
            "docking": "/api/docking",
            "optimization": "/api/optimization",
            "simulation": "/api/simulation",
            "analysis": "/api/analysis"
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "docking_engine": "ready",
            "ai_predictor": "ready",
            "database": "ready"
        }
    }

@app.get("/api/system/info")
async def system_info():
    """Get system capabilities"""
    import multiprocessing as mp
    import psutil

    return {
        "cpu_cores": mp.cpu_count(),
        "ram_total_gb": psutil.virtual_memory().total / (1024**3),
        "ram_available_gb": psutil.virtual_memory().available / (1024**3),
        "intel_optimizations": ai_predictor.use_openvino,
        "compute_device": ai_predictor.device if ai_predictor.use_openvino else "CPU"
    }


# ============================================================================
# Molecular Structure Endpoints
# ============================================================================

@app.post("/api/molecular/analyze")
async def analyze_molecule(request: CompoundInput):
    """Analyze molecular structure from SMILES"""
    try:
        struct = from_smiles(request.smiles, request.name, generate_3d=True)

        if struct is None:
            raise HTTPException(status_code=400, detail="Invalid SMILES string")

        return struct.to_dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/molecular/admet")
async def predict_admet(request: ADMETRequest):
    """Predict ADMET properties"""
    try:
        struct = from_smiles(request.smiles, generate_3d=False)
        if struct is None:
            raise HTTPException(status_code=400, detail="Invalid SMILES")

        descriptors = struct.to_dict()
        admet = ai_predictor.predict_admet(descriptors)

        return {
            "absorption": admet.absorption,
            "bioavailability": admet.bioavailability,
            "half_life": admet.half_life,
            "volume_distribution": admet.distribution_vd,
            "clearance": admet.metabolism_clearance,
            "bbb_permeability": admet.bbb_permeability,
            "pgp_substrate": admet.pgp_substrate,
            "cyp_inhibition": admet.cyp_inhibition,
            "toxicity": {
                "herg_inhibition": admet.herg_inhibition,
                "hepatotoxicity": admet.hepatotoxicity,
                "carcinogenicity": admet.carcinogenicity,
                "ld50": admet.ld50
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Molecular Docking Endpoints
# ============================================================================

@app.post("/api/docking/single")
async def dock_compound(request: DockingRequest, background_tasks: BackgroundTasks):
    """Dock single compound to receptor"""
    try:
        # Run docking in executor to avoid blocking event loop (can take ~5 min)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: docking_engine.dock(
                request.smiles,
                request.compound_name,
                request.receptor,
                request.exhaustiveness,
                request.num_modes
            )
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Docking failed")

        # Analyze interactions
        interactions = binding_analyzer.analyze_binding_pose(
            result.binding_pose,
            request.receptor
        )

        return {
            "docking": result.to_dict(),
            "interactions": {
                "total": interactions.total_interactions(),
                "hydrogen_bonds": len(interactions.hydrogen_bonds),
                "hydrophobic": len(interactions.hydrophobic_contacts),
                "pi_stacking": len(interactions.pi_stacking),
                "energy_breakdown": interactions.binding_energy_breakdown
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/docking/batch")
async def batch_dock(request: BatchDockingRequest):
    """Batch docking of multiple compounds"""
    job_id = str(uuid.uuid4())

    active_jobs[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "total": len(request.compounds),
        "completed": 0,
        "results": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Start background task with proper async execution
    async def run_batch_docking():
        try:
            active_jobs[job_id]["status"] = "running"
            active_jobs[job_id]["updated_at"] = datetime.now().isoformat()

            compounds_list = [(c.name, c.smiles) for c in request.compounds]

            # Run CPU-bound docking in thread pool to avoid blocking event loop
            # This keeps the API responsive during long-running docking operations
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                lambda: docking_engine.batch_dock(
                    compounds_list,
                    receptor=request.receptor,
                    n_jobs=-1
                )
            )

            # Store results
            active_jobs[job_id]["results"] = [r.to_dict() for r in results]
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["progress"] = 1.0
            active_jobs[job_id]["completed"] = len(results)
            active_jobs[job_id]["updated_at"] = datetime.now().isoformat()

            # Move to completed
            completed_jobs[job_id] = active_jobs.pop(job_id)

        except Exception as e:
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)
            active_jobs[job_id]["updated_at"] = datetime.now().isoformat()

    # Run in background (now properly yields control)
    asyncio.create_task(run_batch_docking())

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Batch docking initiated for {len(request.compounds)} compounds",
        "status_url": f"/api/jobs/{job_id}"
    }


# ============================================================================
# Job Management Endpoints
# ============================================================================

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id in active_jobs:
        return active_jobs[job_id]
    elif job_id in completed_jobs:
        return completed_jobs[job_id]
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return {
        "active": list(active_jobs.keys()),
        "completed": list(completed_jobs.keys()),
        "total_active": len(active_jobs),
        "total_completed": len(completed_jobs)
    }


# ============================================================================
# Compound Database Endpoints
# ============================================================================

@app.get("/api/compounds")
async def list_compounds():
    """List all compounds in database"""
    # Would query database in production
    return {
        "compounds": [
            {"name": "Morphine", "smiles": "CN1CC[C@]23[C@H]4Oc5c(O)ccc(C[C@@H]1[C@@H]2C=C[C@@H]4O)c35"},
            {"name": "Oxycodone", "smiles": "COC1=C(C=C2C[C@H]3N(CC[C@@]24C=C[C@@H](O)C1O4)C)O"},
            {"name": "Fentanyl", "smiles": "CCC(=O)N(c1ccccc1)C1CCN(CCc2ccccc2)CC1"}
        ],
        "total": 12
    }

@app.get("/api/compounds/search")
async def search_compounds(query: str, ki_min: Optional[float] = None, ki_max: Optional[float] = None):
    """Search compounds by name or Ki range"""
    # Would query database with filters
    return {
        "query": query,
        "results": [],
        "total": 0
    }


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates"""
    await websocket.accept()

    try:
        while True:
            if job_id in active_jobs:
                status = active_jobs[job_id]
            elif job_id in completed_jobs:
                status = completed_jobs[job_id]
                await websocket.send_json(status)
                break  # Job completed, close connection
            else:
                await websocket.send_json({"error": "Job not found"})
                break

            await websocket.send_json(status)
            await asyncio.sleep(1)  # Update every second

    except WebSocketDisconnect:
        pass


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("ZeroPain Therapeutics API Server")
    print("=" * 70)
    print("\nStarting FastAPI server...")
    print("API Documentation: http://localhost:8000/api/docs")
    print("Interactive API: http://localhost:8000/api/redoc")
    print("\nPress CTRL+C to stop\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
