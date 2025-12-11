# ZeroPain Docking Gym (WIP)

## What it does
- Runs docking jobs with pluggable backends: `python_ref` (always), `mocked` (demo/testing), and placeholders for `c_native` / `openvino_ml`.
- Hardware-aware selection: defaults to CPU; will use GPU/NPU when implemented; writes telemetry to `runs/<id>/docking/telemetry.json`.
- Artifacts: `scores.csv`, `telemetry.json`, `inputs/manifest.json` under `runs/<id>/docking/`.

## CLI (lightweight)
```
python src/docking_cli.py \
  --receptor test-receptor \
  --ligands CCO CCN \
  --backend mocked \
  --hardware CPU \
  --run-dir runs
```

Outputs JSON with job_id, backend/device, and artifact paths.

## Backends
- `mocked`: deterministic pseudo-poses/scores; no heavy deps.
- `python_ref`: simple Python scoring placeholder.
- `c_native` / `openvino_ml`: planned hooks for accelerated or ML scoring.

## Artifacts
- `runs/<id>/docking/inputs/manifest.json` (inputs & settings)
- `runs/<id>/docking/scores.csv` (ligand_id, pose_id, score, backend, device, rank)
- `runs/<id>/docking/telemetry.json` (backend/device/elapsed/ligands/poses)
- MEMSHADOW publishes: `docking.meta`, `docking.scores`, `docking.telemetry` (start/progress/end), `docking.feedback`
- Vector DB ingest (when available): embeddings of pose summaries with metadata for semantic search

## Notes
- Validation is minimal; extend `io.py` / `schemas.py` to enforce chemistry limits and sanitization.
- Hardware routing currently prefers CPU; extend `hardware_routing.py` to detect Arc/NPU and prefer accelerated backends.
- Use `backend=mocked` for demos/tests without RDKit/OpenVINO.

