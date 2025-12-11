from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Tuple, List

from .types import DockingJobSpec


class ValidationError(Exception):
    pass


def validate_inputs(job: DockingJobSpec) -> None:
    if not job.ligands:
        raise ValidationError("No ligands provided")
    if len(job.ligands) > job.max_ligands:
        raise ValidationError(f"Too many ligands ({len(job.ligands)} > {job.max_ligands})")
    if not job.receptor:
        raise ValidationError("Receptor not specified")


def prepare_run_dir(job: DockingJobSpec) -> Path:
    run_dir = Path(job.run_dir) / job.job_id / "docking"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs").mkdir(exist_ok=True)
    return run_dir


def persist_inputs(job: DockingJobSpec, run_dir: Path) -> None:
    manifest = {
        "receptor": job.receptor,
        "ligands": job.ligands,
        "grid": job.grid,
        "backend": job.backend,
        "hardware": job.hardware,
        "poses_per_ligand": job.poses_per_ligand,
        "max_ligands": job.max_ligands,
    }
    with open(run_dir / "inputs" / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

