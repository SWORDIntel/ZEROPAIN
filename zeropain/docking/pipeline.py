from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Dict, Callable, Optional

from .types import DockingJobSpec, DockingResult
from .hardware_routing import select_backend, detect_hardware_profile
from .io import validate_inputs, prepare_run_dir, persist_inputs
from .backends import python_ref
from .backends import mocked
from .memshadow_bridge import publish_docking_run, publish_telemetry
from .vector_ingest import ingest_docking_vectors


BACKEND_IMPL = {
    "python_ref": python_ref.run,
    "mocked": mocked.run,
}


def run_docking_job(job: DockingJobSpec, on_progress: Optional[Callable[[Dict], None]] = None) -> DockingResult:
    validate_inputs(job)
    hw_profile = detect_hardware_profile()
    backend, device, routing_meta = select_backend(job, hw_profile)
    run_dir = prepare_run_dir(job)
    persist_inputs(job, run_dir)

    impl = BACKEND_IMPL.get(backend, python_ref.run)
    t0 = time.time()

    def emit_progress(phase: str, telemetry_payload: Dict):
        try:
            publish_telemetry(job.job_id, phase=phase, telemetry=telemetry_payload)
        except Exception:
            pass
        if on_progress:
            on_progress(telemetry_payload)

    emit_progress(
        phase="start",
        telemetry_payload={
            "backend": backend,
            "device": device,
            "routing": routing_meta,
            "ligands": len(job.ligands),
            "poses": 0,
            "elapsed_sec": 0.0,
        },
    )

    poses = impl(job, device=device)
    elapsed = time.time() - t0

    scores_csv = run_dir / "scores.csv"
    with open(scores_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ligand_id", "pose_id", "score", "backend", "device", "rank"])
        for p in poses:
            writer.writerow([p.ligand_id, p.pose_id, p.score, p.backend, p.device, p.rank])

    telemetry = {
        "backend": backend,
        "device": device,
        "ligands": len(job.ligands),
        "poses": len(poses),
        "elapsed_sec": elapsed,
        "routing": routing_meta,
    }
    with open(run_dir / "telemetry.json", "w") as f:
        json.dump(telemetry, f, indent=2)

    artifacts = {
        "scores_csv": str(scores_csv),
        "telemetry": str(run_dir / "telemetry.json"),
        "inputs_manifest": str(run_dir / "inputs" / "manifest.json"),
    }

    result = DockingResult(
        job_id=job.job_id,
        status="success",
        backend=backend,
        device=device,
        poses=poses,
        artifacts=artifacts,
        telemetry=telemetry,
    )

    # Publish to MEMSHADOW if available; best effort
    try:
        publish_docking_run(job.job_id, run_dir.parent)
    except Exception:
        pass
    try:
        emit_progress(
            phase="end",
            telemetry_payload=telemetry,
        )
    except Exception:
        pass
    try:
        ingest_docking_vectors(job.job_id, poses, telemetry, artifacts)
    except Exception:
        pass

    return result

