# Distributed Scaling Plan for ZEROPAIN

## Goals
- Exploit DSMIL-layer hardware (NPU, Arc iGPU, AMX/AVX-512, custom accelerators) for larger compound analysis and simulations.
- Enable multi-node orchestration (Ray/Dask) for batch and streaming workloads.
- Provide resumable, auditable runs with experiment tracking and artifact retention.
- Keep the Rich/web UI responsive via async job control and remote monitoring.

### Implementation Snapshot (current drop)
- Added `DistributedRunner` (local/Ray/Dask fallback) with JSON checkpoints and resume by batch.
- Added `ExperimentTracker` for run metadata, metrics (`metrics.jsonl`), and artifacts under `runs/<run-id>/`.
- Pipeline now accepts `--backend`, `--checkpoint-dir`, `--run-id`, `--no-resume`, and `--batch-size`; simulation shards checkpoint per batch.

## Architecture Overview
1. **Distributed runner**: Wrap existing pipeline stages in Ray/Dask tasks, sharding patients/compounds into deterministic batches. Persist intermediate parquet/JSONL checkpoints and allow `--resume` from the latest successful stage.
2. **Accelerator-aware scheduling**:
   - **NPU (OpenVINO)**: INT8/INT4 inference for small/medium models; reserve for real-time scoring.
   - **Arc iGPU (XMX)**: Vision/ViT and image-heavy workloads; FP16/INT8 via ONNX/OpenVINO.
   - **CPU AMX/AVX-512**: Transformer blocks, classical ML, preprocessing; enable BF16 where precision matters.
   - **Custom ASIC/FPGA**: Expose optional plugin to register device capabilities and preferred operators.
3. **Experiment tracker**: SQLite/Parquet-backed registry storing run config hash, git commit, hardware profile, metrics, and artifact pointers (local or S3/MinIO). CLI flags `--run-id`, `--resume-run`, `--checkpoint-dir`.
4. **Artifact layout**:
   - `runs/<run-id>/config.json` — validated inputs.
   - `runs/<run-id>/checkpoints/<stage>-<batch>.parquet` — resumable outputs.
   - `runs/<run-id>/metrics.jsonl` — incremental metrics.
   - `runs/<run-id>/logs/` — structured logs for audit.
5. **Security & compliance**: mTLS between workers, tamper-evident logs, no unsafe deserialization; adopt AES-256-GCM for at-rest encryption when secrets are present.

## UI and Workflow Enhancements
- **Async job queue**: Submit long-running jobs to Ray Jobs/RQ; UI polls status, streams logs, and supports cancel/retry.
- **Workflow templates**: Predefined presets (e.g., "100k simulation on Arc + AMX", "sensitivity sweep with NPU gating"). Allow saving/loading parameter sets.
- **Remote dashboard**: Minimal web view for monitoring runs, metrics, and hardware utilization; compatible with Xen domU deployments.
- **Cluster profile loader**: Detect available accelerators and suggest backend choices (e.g., OpenVINO on NPU, IPEX on AMX, oneCCL for multi-node sync).

## Deployment Notes (Xen 10 / Debian Sid)
- **Ray/Dask cluster**: Launch head/worker nodes in domU guests; expose scheduler via Caddy with mTLS. Prefer ZFS-backed ZVOLs for worker storage; pin Arc/NPU via PCI passthrough if needed.
- **Containers**: Provide Docker Compose profiles for head/worker, with resource limits and health checks. Keep Caddy in front with strict TLS and security headers.
- **Networking**: Use WireGuard overlays for node-to-node traffic; ensure Mullvad rotation honors Ray/Dask node discovery.

## Testing & Validation
- Unit tests for runner and tracker (checkpoint/retry paths, config hashing).
- Integration smoke: distributed pipeline over two workers with synthetic data; verify deterministic shards and resume correctness.
- Performance baselines: measure throughput per accelerator type (NPU/iGPU/AMX) on representative models; set alert thresholds in CI.

## Next Steps
1. Implement `src/pipeline/distributed_runner.py` with Ray/Dask execution and checkpoint hooks.
2. Add `src/utils/experiment_tracking.py` and wire into pipeline entrypoints/CLI.
3. Introduce UI job queue integration and workflow templates with remote monitoring endpoints.
4. Ship deployment manifests (Ray/Dask + Caddy + mTLS) and quickstart docs.
