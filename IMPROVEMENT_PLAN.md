# ZeroPain Capability Improvement Plan

Commit baseline: 95a30c11c4749d85611064ec2f33e3d51a003973

## Priorities (0-90 days)
1) **Simulation fidelity & PK/PD knobs**
- Expand compound templates with receptor affinities, metabolic pathways, and patient-specific PK/PD tunables (weight/age/sex/comorbidities).
- Add tolerance/addiction progression models with adjustable slopes and ceilings.
- Enrich dose-response curves with OpenVINO-accelerated inference for faster sweeps.

2) **Analytics depth & metrics**
- Standardize analgesia AUC, tolerance slope, dependence/withdrawal AUROC, sedation/respiratory ceilings, QT/QTc safety, and reproducibility checkpoints.
- Emit signed metrics artifacts (SHA-384) and align with DSMIL audit expectations.

3) **Resilience & checkpointing**
- Add resumable batch execution (checkpoint per shard), retry policy, and deterministic seeds.
- Store checkpoints and run metadata under `runs/<run-id>/` with signatures.

4) **OpenVINO/Arc acceleration**
- Detect Intel NPU/Arc GPU; route heavy inference (optimization/simulation steps) through OpenVINO with CPU fallback.
- Surface config flags for device hints, precision modes, and telemetry.

5) **Interface integration**
- Expose CLI/TUI entrypoints via DSMIL pharma adapter for hub-driven runs.
- Provide web/TUI parity for compound browser, builder, optimization, and simulation dashboards.

6) **Data validation & safety**
- Enforce schema validation for compound inputs and patient cohorts.
- Add guardrails to cap unsafe dose ranges and flag missing pharmacovigilance signals.

## Alignment with DSMIL objectives
- Runs are tamper-evident (signed artifacts), compatible with DSMIL audit flows.
- Accelerator-aware scheduling integrates with DSMIL hardware layer for OpenVINO/Arc.
- UI parity through DSMIL Webkit chain for operator-facing workflows.

## Next actions
- Land DSMIL adapter and config toggles; wire OpenVINO path; add smoke tests.
- Backfill metrics/signature emission and checkpointed execution in ZeroPain pipelines.

