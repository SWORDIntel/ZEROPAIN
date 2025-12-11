#!/usr/bin/env python3
"""Simple CLI for ZeroPain docking pipeline."""

import argparse
import json
from pathlib import Path

from zeropain.docking import DockingJobSpec, run_docking_job


def main():
    parser = argparse.ArgumentParser(description="ZeroPain docking runner")
    parser.add_argument("--receptor", required=True, help="Receptor path or ID")
    parser.add_argument("--ligands", nargs="+", required=True, help="Ligand identifiers (paths or SMILES)")
    parser.add_argument("--backend", choices=["python_ref", "mocked", "c_native", "openvino_ml"], default=None)
    parser.add_argument("--hardware", choices=["CPU", "GPU", "NPU", "AUTO"], default=None)
    parser.add_argument("--poses-per-ligand", type=int, default=5)
    parser.add_argument("--max-ligands", type=int, default=500)
    parser.add_argument("--run-dir", default="runs")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    spec = DockingJobSpec(
        receptor=args.receptor,
        ligands=args.ligands,
        backend=args.backend,
        hardware=args.hardware,
        poses_per_ligand=args.poses_per_ligand,
        max_ligands=args.max_ligands,
        timeout_sec=args.timeout,
        run_dir=Path(args.run_dir),
    )
    result = run_docking_job(spec)
    print(json.dumps({
        "job_id": result.job_id,
        "status": result.status,
        "backend": result.backend,
        "device": result.device,
        "artifacts": result.artifacts,
        "telemetry": result.telemetry,
    }, indent=2))


if __name__ == "__main__":
    main()

