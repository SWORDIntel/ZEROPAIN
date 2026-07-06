# ZeroPain Therapeutics Framework

ZeroPain is a distributed pharmacology lab that optimizes multi-compound opioid protocols with rich patient simulations, auditable experiment tracking, and dual UIs (Rich terminal + 1:1 web experience). It is now CPU-first on the available Intel Xeon AVX2 host, with OpenVINO/NPU/Arc paths treated as optional future accelerators, and keeps every run tamper-evident.

**PROJECT ON HIATUS WHILST I DEAL WITH OTHER SHIT,but be assured the realistic goal of "curing pain" is still one i hold**


## Highlights
- **Distributed, resumable pipeline** with Ray/Dask/local CPU backends, checkpointed batches, and CPU training records for downstream model fitting.
- **CNSA 2.0-oriented auditing**: every run is signed with a SHA-384 digest envelope, CNSA 2.0 metadata, who/when/where provenance, and verification gates before dashboards load results.
- **Dual UI surfaces**: Rich TUI (unified 4-pane dashboard) plus a 1:1 web interface (`zeropain-web`) so the same workflows are available in-browser through Caddy on the internal medical network.
- **Scalable patient simulations**: population size is fully dynamic (from 10 to 1M+), driven by `--n-patients` at runtime — no recompilation required.
- **Advanced PK/PD modelling**: per-compound MOR/DOR/KOR receptor affinities (Ki values), CYP2D6/CYP3A4 metabolic pathways, and patient-specific adjusted half-lives based on age, sex, and comorbidities.
- **Pluggable progression models**: swap tolerance (`linear`, `sigmoid`, `lagged`) and addiction models with configurable slopes at runtime via config or TUI settings panel.
- **DSMIL adapter**: a unified `dsmil_adapter.py` exposes `run_cli()`, `run_tui()`, and a JSON `process_request()` gateway for hub-driven pharmaceutical integration.
- **Compound builder & library**: edit templates or create custom compounds with full receptor affinities, metabolic pathways, and PK/PD knobs.
- **QIHSE + KEYSTONE native backends**: integrated native KV/document store with auto-routing, fully tested on the AVX2 host.

## Architecture & Services
- **Pipeline + CLI** (`src/zeropain_pipeline.py`): orchestrates optimization, simulation, and analysis with `--backend`, `--batch-size`, `--resume`, `--dsmil-adapter`, and CPU-first execution.
- **DSMIL Adapter** (`src/dsmil_adapter.py`): unified entrypoint for external pharmaceutical hub integration — exposes `run_cli()`, `run_tui()`, and JSON `process_request()` for hub-driven runs.
- **Experiment Tracker** (`src/utils/experiment_tracking.py`): stores run metadata, metrics, artifacts, and CNSA 2.0 signature envelopes in `runs/<run-id>/`; dashboards verify signatures before viewing.
- **Database backend** (`zeropain/database/backends.py`): defaults to SQLModel/Postgres or SQLite, and can be pointed at QIHSE with KEYSTONE bridge detection for the native database path.
- **Distributed Runner** (`src/pipeline/distributed_runner.py`): shards work, persists numpy-safe JSON checkpoints, retries failed shards, and falls back to local execution if Ray/Dask are unavailable.
- **Rich TUI** (`src/zeropain_tui.py`): unified 4-pane dashboard (compound browser, protocol/optimization status, population metrics, footer command bar) replacing the previous sequential menu system.
- **Web UI (1:1 with TUI)** (`web/frontend`): mirrors the TUI flows (compound browser/builder, simulation, run dashboard, settings) behind Caddy for HTTPS by default.

## Focused SR Initiatives & MLOps
- **SR-17018 + SR-14968 + opioid lead hypothesis, OPID**: See `doc/mlops_pipeline_sr_cases.md` for a dedicated, no-tolerance/no-addiction pipeline with SR-tagged objectives, safety gates, virtual dose/frequency sweeps, and fixed inter-module APIs (compound, simulation, optimization, metrics).
- **Opioid pre-selection dashboard**: `doc/opioid_preselection_dashboard.md` lists the canonical compounds (SR-17018, SR-14968, Buprenorphine, Oliceridine, Tapentadol, PZM21, Tramadol, OPID) with addiction/tolerance/analgesia metrics and charting patterns for receptor-aware analysis.
- **Metrics-first**: analgesia AUC, tolerance slope, dependence/withdrawal AUROC, sedation/respiratory ceilings, QT/QTc safety, and reproducibility checkpoints are tracked end-to-end with signatures.
- **Modular comms**: REST/gRPC contracts standardize module interaction so the TUI, CLI, and web stack can orchestrate runs interchangeably across local/Ray/Dask CPU backends.

## Quick Start (Docker-first)
Docker Compose is the canonical path and runs API + web + dependencies with TLS-friendly Caddy fronting the web UI.

```bash
# Clone & prepare secrets
cp docker/secrets/admin_bootstrap_secret.example docker/secrets/admin_bootstrap_secret
cp .env.example .env  # adjust SECRET_KEY, DOMAIN, etc.; INTEL_DEVICE defaults to CPU

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
- **Rich TUI (Unified Dashboard)**: `python src/zeropain_tui.py` → 4-pane live dashboard with compound browser, protocol/optimization panel, simulation metrics, and a footer command bar. Type `help` for available commands.
- **Via DSMIL adapter**: `python src/zeropain_pipeline.py --dsmil-adapter --tui` or use `python src/dsmil_adapter.py --simulate --compounds SR-17018 SR-14968 --n-patients-sim 5000`
- **Web UI**: available via Docker stack; presents the same flows with identical semantics.
- **Pipeline CLI examples**:
  - `python src/zeropain_pipeline.py --optimize --backend ray --batch-size 5000 --resume`
  - `python src/zeropain_pipeline.py --simulate --n-patients-sim 50000 --tolerance-model sigmoid`
  - `python src/zeropain_pipeline.py --simulate --n-patients-sim 1000000 --backend dask` *(fully scalable)*
  - `python src/dsmil_adapter.py --list-compounds`
  - `python src/dsmil_adapter.py --simulate --compounds SR-17018 --n-patients-sim 10000 --tolerance-model linear --addiction-slope 0.005`

## Experiment Tracking, Audit, and Integrity
- Runs emit metadata (user, timestamps, backend, hardware hints), configs, metrics, and artifacts into `runs/<run-id>/`.
- Each run is hashed with SHA-384 and stored in a CNSA 2.0 signature envelope targeting ML-DSA-87 detached signatures.
- Without `ZEROPAIN_CNSA_SIGNER_CMD` and `ZEROPAIN_CNSA_VERIFY_CMD`, verification runs in explicit digest-only compatibility mode and marks `cnsa_2_compliant: false`.
- Set `ZEROPAIN_CNSA_REQUIRE_SIGNATURE=true` to fail run signing if the external CNSA signer cannot produce a detached signature.
- Metrics append to `metrics.jsonl`; checkpoints live under `checkpoints/`; signatures and audit logs sit alongside artifacts for chain-of-custody.

## Database Backend Selection
- Default: `ZEROPAIN_DB_BACKEND=sqlmodel` uses the existing SQLModel engine with `DATABASE_URL`.
- QIHSE: `ZEROPAIN_DB_BACKEND=qihse` requires QIHSE Python bindings plus `libqihse.so`; install with `pip install "zeropain[qihse]"` or build from `https://github.com/SWORDIntel/QIHSE`. In this mode, API job records are mirrored into QIHSE KV/document storage while SQLModel remains the FastAPI compatibility session layer.
- KEYSTONE acceleration is detected through `KEYSTONE_HOME` or `QIHSE_HOME` when `qihse_keystone_bridge.h` or `qihse_keystone_bridge.c` is present from `https://github.com/SWORDIntel/KEYSTONE`.
- `/api/health` reports the selected backend, QIHSE Python/native library readiness, KEYSTONE bridge detection, and source repository URLs.

Build the local native backends on the Intel AVX2 CPU host:

```bash
scripts/build_native_backends.sh
export ZEROPAIN_DB_BACKEND=qihse
export QIHSE_HOME="$PWD/third_party/QIHSE"
export KEYSTONE_HOME="$PWD/third_party/KEYSTONE"
export LD_LIBRARY_PATH="$QIHSE_HOME:${LD_LIBRARY_PATH:-}"
```

## Population, Medication, and Pharmacology Controls
- Configure age, weight, sex ratio, comorbidities, and medication prevalence with baseline tolerance modeling.
- **Per-compound receptor affinities**: Ki values for MOR, DOR, and KOR are set per compound; patient clearance is computed via CYP2D6/CYP3A4 pathway weights modulated by comorbidities (e.g. liver disease reduces CYP efficiency by 40%).
- **Pluggable progression models**: choose tolerance model (`linear`, `sigmoid`, `lagged`) and addiction model at runtime; configure slopes and ceilings via TUI settings or `--tolerance-model` / `--addiction-slope` CLI flags.
- **Scalable populations**: `--n-patients-sim` accepts any integer — 10 for quick tests, 1M+ for production sweeps — no recompilation needed.
- Simulations report receptor engagement per pathway (MOR/DOR/KOR), neurotransmitter release, medication exposure metrics, and CPU training records keyed by input/model hashes.

## Visualization & Performance
- Rich tables and charts are available in both UIs; animations can be enabled/disabled, and refresh cadence is tunable to avoid CPU spikes.
- Distributed runs checkpoint per batch; resuming skips completed shards and retries failures with deterministic seeds.

## Support & Docs
- Quickstarts: `QUICKSTART.md`, `USAGE.md`, `DOCKER_DEPLOYMENT_PLAN.md`, `ENHANCEMENT_PLAN.md` for scaling guidance.
- Issues/ideas: file in this repository. Caddy/WireGuard/mtls ready for Xen 10 hosts with Docker + Portainer.
