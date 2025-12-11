from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict
import uuid
import time


@dataclass
class DockingJobSpec:
    receptor: str  # path or identifier
    ligands: List[str]  # paths or SMILES strings
    grid: Optional[Dict] = None  # {center: {x,y,z}, size: {x,y,z}}
    backend: Optional[str] = None  # python_ref|c_native|openvino_ml|mocked
    hardware: Optional[str] = None  # CPU|GPU|NPU|AUTO
    poses_per_ligand: int = 5
    max_ligands: int = 500
    timeout_sec: int = 300
    job_id: str = field(default_factory=lambda: f"dock-{int(time.time())}-{uuid.uuid4().hex[:8]}")
    run_dir: Path = field(default_factory=lambda: Path("runs"))


@dataclass
class DockingPose:
    ligand_id: str
    pose_id: int
    score: float
    backend: str
    device: str
    rank: int


@dataclass
class DockingResult:
    job_id: str
    status: str
    backend: str
    device: str
    poses: List[DockingPose] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    telemetry: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

