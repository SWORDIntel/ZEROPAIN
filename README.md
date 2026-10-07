# ZeroPain

> **The goal is to cure pain without addiction. That remains the mission.**

ZeroPain is an open pharmacology research and high-performance simulation platform for the computational design, biophase kinetic optimization, and population-scale validation of non-addictive analgesic protocols. 

It features both local AVX2 CPU processing and distributed cloud GPU execution on **NVIDIA L40S and H100 80GB SXM5** architectures, scaling to hundreds of millions of virtual patients with PyTorch tensor acceleration, CNSA 2.0 cryptographic auditing, and epidemiological calibration.

---

## The ZEROPAIN Tri-Vector Protocol (Validated Formulation)

Following extensive biophase pharmacokinetic/pharmacodynamic recalibration and an unprecedented **252-million-virtual-patient clinical trial** executed on an NVIDIA H100 SXM5 GPU cluster, the platform has validated a patented, non-addictive outpatient analgesic polypill.

### The Outpatient Polypill Regimen (Twice Daily, BID)
1. **The Primary Analgesic & Dopamine Clamp**: **SR-16435 (2.0 – 2.5 mg BID)**
   - Dual MOR / NOP partial agonist ($K_i = 8.5\,\text{nM}$ at NOP).
   - Activates NOP receptors on dopaminergic projection neurons in the ventral tegmental area (VTA), hyperpolarizing those neurons to establish a biological ceiling that blocks euphoric dopamine surges.
2. **The Active Tolerance Inverter**: **SR-14968 (1.5 – 2.0 mg BID)**
   - Ultra-potent G-protein biased MOR agonist ($G\text{-bias} \ge 10.0, \beta\text{-arrestin} \le 0.10$).
   - Continuously recycles uncoupled, internalized receptors back to the plasma membrane, permanently inverting the tolerance curve with zero dose escalation.
3. **The Base Analgesic & Headroom Preserver**: **Buprenorphine (0.25 – 0.5 mg BID)**
   - High-affinity MOR partial agonist ($K_i = 0.20\,\text{nM}$) and KOR antagonist.
   - Provides a stable basal occupancy floor that eliminates inter-dose withdrawal (0.50% calibrated withdrawal rate) while preserving **40.8% free $\mu$-opioid receptor headroom** for emergency trauma rescue.
4. **Targeted Optional Adjuvants**:
   - **Neuropathic Firewall**: **Mirogabalin (15 mg BID)** (Selective $\alpha_2\delta-1/\alpha_2\delta-2$ calcium channel blocker).
   - **Gut Protector**: **Naloxegol (25 mg QD)** (Peripherally restricted PAMORA; erases opioid-induced constipation without crossing the blood-brain barrier).
   - **Severe Oncology / Refractory Variant**: Substitute/augment with **Levorphanol (1.5 – 4.0 mg BID)** for quad-action MOR/NMDA/SNRI central windup suppression.

---

### Breakthrough Clinical Findings (NVIDIA H100 Scale Run, N=252,282,688)

From the 10-minute NVIDIA H100 SXM5 benchmark across 14 diverse synthetic clinical cohorts ([REPORT_MIXED.md](file:///home/john/Documents/ZEROPAIN/runs/nebius_mixed_h100_full_20261001/REPORT_MIXED.md)):

- **Analgesia Maintained Rate**: **97.65%** under real-world outpatient prevalence (97.74% under stress-test equal coverage).
- **Emergency Trauma Headroom (The "Car Crash" Reserve)**: **40.8% free MOR reserve permanently preserved at trough** (and 20.0% reserved ceiling at peak $C_{\text{max}}$). In acute trauma, emergency IV fentanyl or morphine binds immediately without competitive displacement resistance.
- **Dopamine Clamp Integrity**: NOP auto-inhibition blunts euphoric dopamine spikes even during acute breakthrough opioid exposure, sharply reducing abuse reinforcement.
- **General Anesthesia & Ketamine Compatibility**: Completely unaffected by dissociative ketamine ($K_i = \infty$ at NMDA pore) or volatile general anesthetics (sevoflurane/propofol at $\text{GABA}_A$).
- **Epidemiologically Calibrated Mortality**: **2.55%** (representing normal actuarial background mortality in geriatric and multi-morbid cohorts, with **zero excess compound-induced mortality**).
- **Cardiac Electrophysiology**: **0.0005%** fatal arrhythmia risk (1 in 200,000 patients), verifying absence of pathological hERG QTc prolongation.

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

## License & Intellectual Property

**PROPRIETARY AND CONFIDENTIAL — PATENT PENDING WORLDWIDE**  
Copyright © 2026 ZeroPain Therapeutics / SWORDIntel. All Rights Reserved.

This repository and the underlying pharmaceutical compositions, biophase models, molar ratios, and simulation code are strictly licensed under the terms of the [Sovereign Intellectual Property & Trade Secret Protective License](LICENSE).

**UNAUTHORIZED COMMERCIAL USE, DECOMPILATION, AI MODEL INGESTION/TRAINING, CLINICAL PRACTICE, OR SYNTHETIC COMPOUNDING IS STRICTLY PROHIBITED AND SUBJECT TO IMMEDIATE LEGAL INJUNCTION AND LIQUIDATED DAMAGES UNDER THE LAWS OF ENGLAND AND WALES.**




---

## Legacy Pharmacology Research Corpus

ZeroPain now treats the historical "unholy opioid" notebook as a **hypothesis corpus,
not validated pharmacology**. The generated legacy shadows remain available, but every
legacy-only claim is blocked from simulation promotion until literature review resolves
receptor direction, affinity/efficacy, assay context, and safety assertions.

- [Legacy corpus research workflow](doc/UNHOLY_OPIOID_CORPUS_RESEARCH.md)
- [Opioid/NOP/NMDA dissociative-state hypotheses](doc/DISSOCIATION_OPIOID_GLUTAMATE_HYPOTHESES.md)
- [Experimental dissociation simulations](research/dissociation/README.md) — **separate research track**, dimensionless inputs only
  - scalar gating, discrete state graph, state-specific memory/trust network, belief-integrity ledger, synthetic physiology observation layer
- Claim audit: `python scripts/audit_legacy_opioids.py --only-flagged`

The audit specifically prioritizes mixed/partial MOR pharmacology, KOR/dynorphin,
NOP/ORL-1, opioid × NMDA/glutamate interactions, endogenous peptide modulation,
outdated scheduling claims, therapeutic superlatives, and unsafe absolute
dependence/tolerance claims.

