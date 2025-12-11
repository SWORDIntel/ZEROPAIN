# MEMSHADOW Bridge for ZeroPain Docking (WIP)

## What is published
- `docking.meta`: job spec (receptor, ligands, backend/device, routing decision, telemetry).
- `docking.scores`: pose scores (ligand_id, pose_id, score, backend, device, rank).
- `docking.telemetry`: latency, ligands/poses, routing {accelerator, est_latency_ms, power_impact_w}.
- `docking.feedback`: appended when feedback entries are sent.

## Where it lives
- Bridge: `zeropain/docking/memshadow_bridge.py`
- Pipeline calls `publish_docking_run(...)` after each job (best-effort).

## Topics (example)
- `docking.<job_id>.meta`
- `docking.<job_id>.scores`
- `docking.<job_id>.feedback` (when feedback is posted)

## Signing
- `sign` flag is accepted but currently stubbed; wire to MEMSHADOW signing if available.

## Consumption
- AI/Orchestrator can subscribe to `docking.*` topics to rerank, alert, or summarize.

## Notes
- If MEMSHADOW client is unavailable, publishing is no-op (stub).
- Artifacts sourced from `runs/<job_id>/docking/`.

