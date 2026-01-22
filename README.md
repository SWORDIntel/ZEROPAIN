# ZeroPain Therapeutics Framework

ZeroPain is a distributed pharmacology lab that optimizes multi-compound opioid protocols with rich patient simulations, auditable experiment tracking, and dual UIs (Rich terminal + 1:1 web experience). It targets Intel NPU/OpenVINO, Arc GPU, and CPU backends, runs cleanly in Docker by default, and keeps every run tamper-evident.

PROJECT ON HIATUS WHILST I DEAL WITH OTHER SHIT,but be assured the realistic goal of "curing pain" is still one i hold


## Highlights
- **Distributed, resumable pipeline** with Ray/Dask/local backends, checkpointed batches, and accelerator-aware scheduling.
- **IA3-grade auditing**: every run is signed (SHA-384), logged with who/when/where metadata, and verified when loaded in dashboards.
- **Dual UI surfaces**: Rich TUI plus a 1:1 web interface (via `zeropain-web`) so the same workflows are available in-browser through Caddy on the internal medical network.
- **Patient + medication fine-tuning**: age/weight/sex distributions, comorbidities, pre-existing medications, baseline tolerance, and medication exposure metrics.
- **Compound builder & library**: edit templates or create custom compounds with receptor affinities, pharmacological activities, and PK/PD knobs; external sources can hydrate missing entries.
- **Visualization-ready**: dependency bootstrapper auto-installs Rich and charting libs; refresh/animation controls stay CPU-friendly and TEMPEST Class C themed.

## Architecture & Services
- **Pipeline + CLI** (`src/zeropain_pipeline.py`): orchestrates optimization, simulation, and analysis with `--backend`, `--batch-size`, `--resume`, and accelerator hints for OpenVINO/Arc/CPU.
- **Experiment Tracker** (`src/utils/experiment_tracking.py`): stores run metadata, metrics, artifacts, and SHA-384 signatures in `runs/<run-id>/`; dashboards verify signatures before viewing.
- **Distributed Runner** (`src/pipeline/distributed_runner.py`): shards work, persists checkpoints, retries failed shards, and falls back to local execution if Ray/Dask are unavailable.
- **Rich TUI** (`src/zeropain_tui.py`): bannered terminal UI covering compound browsing, builder, optimization, simulation, settings, and run dashboards.
- **Web UI (1:1 with TUI)** (`web/frontend`): mirrors the TUI flows (compound browser/builder, simulation, run dashboard, settings) behind Caddy for HTTPS by default.

## Focused SR Initiatives & MLOps
- **SR-17018, SR-15968, SR-14968, OPID**: See `doc/mlops_pipeline_sr_cases.md` for a dedicated, no-tolerance/no-addiction pipeline with SR-tagged objectives, safety gates, and fixed inter-module APIs (compound, simulation, optimization, metrics).
- **Opioid pre-selection dashboard**: `doc/opioid_preselection_dashboard.md` lists the canonical compounds (SR-17018, SR-14968, Buprenorphine, Oliceridine, Tapentadol, PZM21, Tramadol, OPID) with addiction/tolerance/analgesia metrics and charting patterns for receptor-aware analysis.
- **Metrics-first**: analgesia AUC, tolerance slope, dependence/withdrawal AUROC, sedation/respiratory ceilings, QT/QTc safety, and reproducibility checkpoints are tracked end-to-end with signatures.
- **Modular comms**: REST/gRPC contracts standardize module interaction so the TUI, CLI, and web stack can orchestrate runs interchangeably across CPU/Arc/OpenVINO backends.

## Quick Start (Docker-first)
Docker Compose is the canonical path and runs API + web + dependencies with TLS-friendly Caddy fronting the web UI.

```bash
# Clone & prepare secrets
cp docker/secrets/admin_bootstrap_secret.example docker/secrets/admin_bootstrap_secret
cp .env.example .env  # adjust INTEL_DEVICE, SECRET_KEY, DOMAIN, etc.

# Launch the full stack
docker compose up --build
```

- Web UI: https://localhost (or your `DOMAIN`), mirroring the Rich TUI.
- API: https://localhost/api (served internally on the medical network and proxied by Caddy).

**Network segmentation:** the stack uses an internal `medical` Docker network for API/web/database/Redis traffic. Caddy is joined to both `edge` (exposed ports) and `medical` (internal) so only Caddy can reach the app services; the API container no longer binds a host port directly.
- Data: Postgres + Redis volumes, run artifacts under `runs/` (bind-mounted by Dockerfile).

## Local Development (fallback)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```
The dependency bootstrapper loads Rich/visualization packages on-demand. Run `python src/zeropain_tui.py` for the terminal UI or `python -m src.zeropain_pipeline --help` for CLI options.

## Running Workflows
- **Rich TUI**: `python src/zeropain_tui.py` → navigate compound browser, builder, optimization, and simulations. Settings panel controls backend (local/Ray/Dask), resume flag, batch size, run ID, checkpoint directory, animation/refresh cadence.
- **Web UI**: available via Docker stack; presents the same flows (compound browse/compare/build, protocol optimization, patient simulation, run dashboard, settings with animation/poll controls) with identical semantics as the TUI.
- **Pipeline CLI examples**:
  - `python -m src.zeropain_pipeline --mode optimize --backend ray --batch-size 5000 --resume`
  - `python -m src.zeropain_pipeline --mode simulate --patients 100000 --checkpoint-dir runs/latest/checkpoints`
  - `python src/opioid_analysis_tools.py --input runs/<run-id>/artifacts`

## Experiment Tracking, Audit, and Integrity
- Runs emit metadata (user, timestamps, backend, hardware hints), configs, metrics, and artifacts into `runs/<run-id>/`.
- Each run is hashed (SHA-384) and signed; dashboards and loaders verify signatures before displaying results.
- Metrics append to `metrics.jsonl`; checkpoints live under `checkpoints/`; signatures and audit logs sit alongside artifacts for chain-of-custody.

## Population, Medication, and Pharmacology Controls
- Configure age, weight, sex ratio, comorbidities, and medication prevalence with baseline tolerance modeling.
- Pharmacological activities and receptor affinities are editable per compound; the builder supports custom values when a compound is missing from the library.
- Simulations report receptor engagement, neurotransmitter release, and medication exposure metrics; OpenVINO/Arc hints are applied when available.

## Visualization & Performance
- Rich tables and charts are available in both UIs; animations can be enabled/disabled, and refresh cadence is tunable to avoid CPU spikes.
- Distributed runs checkpoint per batch; resuming skips completed shards and retries failures with deterministic seeds.

## Support & Docs
- Quickstarts: `QUICKSTART.md`, `USAGE.md`, `DOCKER_DEPLOYMENT_PLAN.md`, `ENHANCEMENT_PLAN.md` for scaling guidance.
- Issues/ideas: file in this repository. Caddy/WireGuard/mtls ready for Xen 10 hosts with Docker + Portainer.
