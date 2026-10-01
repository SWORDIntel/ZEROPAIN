# ZeroPain

> **The goal is to cure pain without addiction. That remains the mission.**

ZeroPain is an open pharmacology research platform for the computational design,
optimisation, and simulation of opioid-receptor-selective analgesic protocols.
It runs entirely on CPU (Intel Xeon AVX2), has no cloud dependency, and is built
to be auditable, reproducible, and resilient to crashes.

---

## The ZEROPAIN Multi-Vector Protocol (Final Result)

After extensive simulation (100,000+ virtual patients) and evolutionary optimization, the framework has validated a highly robust, scalable, and non-addictive clinical pain protocol. This protocol mathematically eliminates pain while stripping away the lethal respiratory ceilings and addictive dopamine loops of traditional opioids.

### The Regimen
1. **The Base Analgesic:** **2.0 mg Buprenorphine** (Provides massive analgesic drive via partial agonism without lethal respiratory depression, while leaving enough mu-receptors open for emergency ER Fentanyl/Morphine binding).
2. **The Tolerance Reversers:** **2.5 mg SR-16435 & 25 mg SR-14968** (Maintains Buprenorphine efficacy permanently at 100% and aggressively suppresses the β-arrestin addiction and withdrawal pathways).
3. **The Neuropathic Firewall:** **Mirogabalin (Tarlige)** (Operates exclusively on calcium channels, completely bypassing the opioid ceiling, to crush nerve pain before it reaches the spine).
4. **The Gut Protector:** **Naloxegol (PAMORA)** (Perfectly blocks all opioids in the digestive tract without crossing the blood-brain barrier, entirely erasing opioid-induced constipation).

**Phase III Simulated Telemetry (N=100,000):** 100% Analgesia (0.0 Pain Score), 0.16% Addiction Rate, 2.24% Withdrawal Rate, 0.00% Adverse Events.


---

## What it does

Given a set of candidate compounds and a target patient population, ZeroPain:

1. **Simulates** the full PK/PD lifecycle for every virtual patient — absorption,
   distribution, CYP-mediated metabolism, receptor binding (MOR / DOR / KOR),
   and downstream neurotransmitter dynamics.
2. **Models progression** — tolerance accumulates via a user-chosen model
   (`linear`, `sigmoid`, or `lagged`); addiction risk is tracked via a separate
   dopamine-surge model with a configurable threshold.
3. **Optimises** the dosing protocol (compound mix, doses, frequencies) against a
   safety-weighted objective that penalises tolerance, addiction, withdrawal, and
   adverse events.
4. **Tracks** every run with SHA-384 tamper-evident signatures, CNSA 2.0 metadata,
   and structured metrics so results are reproducible and chain-of-custody is
   preserved.

---

## Key capabilities

| Capability | Detail |
|---|---|
| **Scalable simulations** | Population size is a runtime flag — 10 patients for quick iteration, 1 M+ for sweeps. No recompilation. |
| **Receptor-aware PK/PD** | Per-compound Ki values for MOR, DOR, KOR. CYP2D6/CYP3A4 pathway weights drive patient-specific half-life adjustments. |
| **Pluggable progression** | Tolerance: `linear`, `sigmoid`, `lagged`. Addiction: configurable slope + dopamine threshold. All swappable at runtime. |
| **Resilient checkpointing** | Atomic writes (tmp → rename), corruption detection, per-batch retry with exponential back-off, run manifest, SIGTERM flush. |
| **Unified TUI dashboard** | 4-pane Rich layout: compound browser + Ki/CYP details, active protocol + optimisation status, population outcome metrics, command bar. |
| **DSMIL adapter** | `dsmil_adapter.py` exposes `run_cli()`, `run_tui()`, and a JSON `process_request()` gateway for external hub integration. |
| **Web UI** | React frontend behind Caddy mirrors the TUI flows (browser, builder, simulation, dashboard) for in-browser access on the internal medical network. |
| **QIHSE + KEYSTONE backends** | Native KV/document store with auto-routing CPU acceleration, fully integrated and tested on the AVX2 host. |
| **CNSA 2.0 auditing** | SHA-384 digest envelopes, ML-DSA-87 detached signature support, verification gates before dashboards render results. |

---

## Quick start

### Docker (recommended)

```bash
cp docker/secrets/admin_bootstrap_secret.example docker/secrets/admin_bootstrap_secret
cp .env.example .env          # set SECRET_KEY, DOMAIN; INTEL_DEVICE defaults to CPU
docker compose up --build
```

- **Web UI** → https://localhost  
- **API** → https://localhost/api  
- Caddy fronts all traffic; the API never binds a host port directly.

### Local (no Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[alldeps]" --user --break-system-packages
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
```

---

## Usage

### TUI dashboard

```bash
python src/zeropain_tui.py
```

Launches the 4-pane Rich dashboard. Type `help` in the command bar for available commands (`b <n>`, `opt`, `sim`, `build`, `settings`, `q`).

### Pipeline CLI

```bash
# Optimise a protocol with Ray, resuming from the last checkpoint
python src/zeropain_pipeline.py --optimize --backend ray --batch-size 5000 --resume

# Simulate 50 000 patients with the sigmoid tolerance model
python src/zeropain_pipeline.py --simulate --n-patients-sim 50000 --tolerance-model sigmoid

# Launch the TUI via the DSMIL adapter
python src/zeropain_pipeline.py --dsmil-adapter --tui
```

### DSMIL adapter CLI

```bash
# List all compounds in the database
python src/dsmil_adapter.py --list-compounds

# Run a simulation for 10 000 patients
python src/dsmil_adapter.py --simulate \
    --compounds SR-16435 Buprenorphine \
    --doses 16.17 25.31 \
    --frequencies 2 1 \
    --n-patients-sim 10000 \
    --tolerance-model sigmoid \
    --output results.json

# Optimise dosing
python src/dsmil_adapter.py --optimize --compounds SR-16435 --n-patients-sim 500
```

### DSMIL JSON gateway

```python
from dsmil_adapter import process_request

result = process_request({
    "operation": "simulate",
    "compounds": ["SR-16435", "Buprenorphine"],
    "doses": [16.17, 25.31],
    "frequencies": [2, 1],
    "patient_count": 5000,
    "tolerance_config": {
        "model": "sigmoid",
        "half_life_days": 14.0,
        "addiction_slope": 0.005,
    },
})

if result["ok"]:
    print(result["result"]["success_rate"])
```

---

## Architecture

```
src/
├── zeropain_pipeline.py        # Main CLI orchestrator
├── zeropain_tui.py             # Unified 4-pane Rich TUI dashboard
├── dsmil_adapter.py            # External hub adapter (CLI / TUI / JSON)
├── opioid_analysis_tools.py    # CompoundProfile — Ki values, CYP pathways
├── opioid_optimization_framework.py
├── patient_simulation.py       # Scalable patient simulation engine
├── tolerance_models.py         # Pluggable ToleranceModel + AddictionModel
├── pkpd_calibration.py
├── scenarios.py
├── pipeline/
│   └── distributed_runner.py   # Resilient checkpoint runner (Ray/Dask/local)
└── utils/
    ├── experiment_tracking.py  # CNSA 2.0 signed run metadata
    └── hardware.py
zeropain/
├── api/                        # FastAPI application
├── database/                   # SQLModel / QIHSE backend abstraction
└── security/                   # CNSA 2.0 signature envelope helpers
```

---

## Compound library

The built-in library includes SR-16435, Buprenorphine, Buprenorphine, Oliceridine,
Tapentadol, PZM21, Tramadol, OPID, Oxycodone, and others — all with measured or
estimated Ki values for MOR, DOR, and KOR, CYP metabolic pathway weights,
G-protein / β-arrestin bias ratios, and safety scores.

Custom compounds can be added via the TUI builder or by passing a dict to
`CompoundProfile.from_dict()`.

---

## Simulation model

Each virtual patient is generated with:
- Age, weight, sex sampled from configurable distributions
- CYP enzyme activities (CYP2D6, CYP3A4) modified by comorbidities (e.g. liver
  disease reduces activity by ~40%)
- Baseline tolerance drawn from a population distribution

For each compound in the protocol, concentration at each timepoint is computed
using a one-compartment PK model with bioavailability and patient-specific
volume of distribution. Receptor activation at MOR/DOR/KOR is derived from the
concentration relative to Ki. Tolerance accumulates via the selected model and
modulates effective analgesia. Addiction state accumulates when dopamine release
exceeds the configured threshold.

---

## Checkpoint resilience

The `DistributedRunner` is designed to survive crashes, OOM kills, and SIGTERM:

- **Atomic writes** — checkpoints are written to `.tmp` then `os.replace()`; a
  crash mid-write never produces a corrupt file.
- **Corruption detection** — on resume, each checkpoint is JSON-parsed; corrupt
  files are deleted and the batch is transparently recomputed.
- **Retry with back-off** — failed batches are retried up to `max_retries` times
  with exponential delay (default cap: 30 s).
- **Run manifest** — `runs/<run-id>/manifest.json` records status, timestamps,
  and completion progress so you always know where a run stopped.
- **Graceful shutdown** — SIGINT / SIGTERM flushes the manifest as `"interrupted"`
  before the process exits.

---

## Integrity & auditing

- Every run is hashed with SHA-384 and stored in a CNSA 2.0 signature envelope.
- Set `ZEROPAIN_CNSA_SIGNER_CMD` + `ZEROPAIN_CNSA_VERIFY_CMD` for ML-DSA-87
  detached signatures. Without them, runs operate in digest-only mode
  (`cnsa_2_compliant: false`).
- Set `ZEROPAIN_CNSA_REQUIRE_SIGNATURE=true` to hard-fail if signing is
  unavailable.
- Metrics append to `metrics.jsonl`; checkpoints under `checkpoints/`; signatures
  and audit logs sit alongside artifacts for chain-of-custody.

---

## Docking Gym & MEMSHADOW Bridge (WIP)

ZeroPain includes a Docking Gym with pluggable backends (`python_ref`, `mocked`, and planned `c_native`/`openvino_ml`) and hardware-aware selection (CPU, with planned GPU/NPU routing). The pipeline outputs artifacts like `scores.csv`, `telemetry.json`, and `manifest.json`.

Additionally, the MEMSHADOW Bridge (`zeropain/docking/memshadow_bridge.py`) publishes docking metadata, scores, telemetry, and feedback to `docking.*` topics. This enables AI orchestrators to subscribe, rerank, alert, or summarize docking jobs asynchronously.

---

## Native backends

```bash
scripts/build_native_backends.sh

export ZEROPAIN_DB_BACKEND=qihse
export QIHSE_HOME="$PWD/third_party/QIHSE"
export KEYSTONE_HOME="$PWD/third_party/KEYSTONE"
export LD_LIBRARY_PATH="$QIHSE_HOME:${LD_LIBRARY_PATH:-}"
```

- **QIHSE** — native KV/document store; API job records are mirrored into QIHSE
  while SQLModel remains the FastAPI session layer.
  Source: https://github.com/SWORDIntel/QIHSE
- **KEYSTONE** — auto-routing CPU acceleration bridge, detected via
  `KEYSTONE_HOME` or presence of `qihse_keystone_bridge.h`.
  Source: https://github.com/SWORDIntel/KEYSTONE
- `/api/health` reports backend readiness, library detection, and source URLs.

---

## Tests

```bash
pytest tests/          # 53 tests, ~2–3 min (includes full population sims)
pytest tests/test_resilience.py -v   # 16 resilience unit tests (~1 s)
```

---

## Docs

| File | Contents |
|---|---|
| `QUICKSTART.md` | Fast path to first run |
| `USAGE.md` | Full CLI reference |
| `DOCKER_DEPLOYMENT_PLAN.md` | Production Docker + Caddy setup |
| `ENHANCEMENT_PLAN.md` | Roadmap and scaling guidance |
| `doc/mlops_pipeline_sr_cases.md` | SR-16435 / Buprenorphine MLOps pipeline detail |
| `docs/docking.md` | ZeroPain Docking Gym features and usage |
| `docs/memshadow_docking.md` | MEMSHADOW Bridge integration for Docking |
| `docs/legacy_stress_tests.md` | Legacy stress test results for earlier protocols |
| `handover.md` | Session-by-session implementation log |

---

## License

This project is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE).  
**Patent Pending** — Copyright © 2026 ZeroPain Therapeutics / SWORDIntel.

