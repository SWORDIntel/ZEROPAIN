# SR-17018, SR-15968, SR-14968, and OPID Initiative: Focused MLOps & Modular Therapeutics Stack

## Purpose and Scope
- **SR-17018 (tolerance-sparing):** Optimize compounds/protocols for high analgesia with flat tolerance slope and suppressed β-arrestin recruitment.
- **SR-15968 (sedation-minimizing):** Maintain analgesic effect while keeping sedation/respiratory depression below cohort-specific ceilings.
- **SR-14968 (respiratory-sparing):** Deliver sustained analgesia with κ antagonism and μ bias to limit respiratory depression and dysphoria while holding tolerance flat.
- **OPID non-addictive analgesic:** Candidate class aiming for μ-opioid relief without reinforcing reward signaling (no euphoria/withdrawal) and without tolerance accumulation.
- **Constraint envelope:** No tolerance or addiction uplift, predictable analgesia, tamper-evident audit trail, and reproducible runs across CPU/Arc GPU/OpenVINO.

## End-to-End MLOps Pipeline (aligned to Zeropain stack)
1) **Data ingress & validation**
   - Sources: receptor-binding assays, PK/PD curves, adverse event registries, cohort simulations (`patient_simulation_100k.py`).
   - Contracts: `compound_id`, receptor affinity vectors (MOR/DOR/KOR/NPFF), G-protein vs β-arrestin ratios, PK half-life, sedation/respiratory scores, comorbidities.
   - Validators: schema + range checks, unit normalization, sparsity guards; hard-fail any missing receptor or PK fields.
2) **Feature store + lineage**
   - Persist curated tensors (affinity, PK/PD, safety scores, cohort strata) with version tags per SR-ID.
   - Attach run metadata (backend, seeds, hardware hints) and SHA-384 signatures from `experiment_tracking` to every feature snapshot.
3) **Training/optimization stages**
   - **SR-17018:** reward analgesia retention vs. tolerance slope (`Δanalgesia / days`), penalize β-arrestin coupling and withdrawal risk probability.
   - **SR-15968:** dual-head model predicting analgesia and sedation; enforce ceilings via constrained optimization; respiratory depression risk >0.05 auto-fails.
   - **SR-14968:** emphasize analgesic AUC and respiratory safety; reward κ antagonism impact and μ-bias G-protein signaling; block if tolerance slope exceeds 0.01/day or dysphoria markers rise.
   - **OPID candidate:** reinforcement loop over simulated cohorts with reward = analgesia – dependence risk – respiratory penalty; enforce monotonicity on tolerance slope.
   - Backends: Ray/Dask or local; resume from checkpoints; deterministic seeds per shard.
4) **Evaluation & gating**
   - Metrics: analgesic AUC, tolerance slope, dependence/withdrawal AUROC, sedation/respiratory depression rate, QT prolongation rate, G-protein bias index, PK variability.
   - Safety gates: block deploy if tolerance slope >0.01/day, withdrawal probability >0.02, sedation percentile > cohort cap, or integrity checks fail.
5) **Deployment & monitoring**
   - Promote models through staging → prod via signed artifacts; serve via FastAPI/uvicorn behind Caddy mTLS.
   - Observability: metrics → Prometheus; traces → OTEL; tamper-evident run logs and signature verification on load.
   - Continuous drift checks on tolerance slope, dependence probability, and analgesia retention across demographics.

## Fixed Module APIs (inter-module contracts)
- **Compound Service (REST/gRPC)**
  - `POST /compounds`: register/update compound with affinities, PK, bias metrics, target SR-ID tags.
  - `GET /compounds/{id}`: return immutable snapshot + signature; include receptor vector, PK/PD descriptors, safety ceilings.
- **Simulation Service**
  - `POST /simulate`: payload `{compound_id, cohort_profile, dose_plan, simulation_steps}` → returns analgesia curve, tolerance slope, AE estimates, audit signature.
- **Optimization/Policy Service**
  - `POST /optimize`: payload `{sr_id, objectives, constraints, backend, seeds}` → returns protocol candidates + checkpoints; accepts SR-17018/15968/14968/OPID objectives.
- **Metrics Service**
  - `POST /metrics`: append run metrics (`analgesia_auc`, `tolerance_slope`, `dependence_risk`, `sedation_rate`, `respiratory_prob`) to `metrics.jsonl` and push to Prometheus.
- **Common behaviors**: signed responses (SHA-384), idempotent retries, schema-versioned payloads, enforced TLS/mTLS, and audit IDs propagated via headers.

## Cohort & Metric Profiles
- **Analgesia**: AUC vs. pain baseline, % responder rate ≥50% reduction, duration above therapeutic window.
- **Tolerance**: slope per day, % cohorts with slope >0.01/day, receptor desensitization index.
- **Dependence/Withdrawal**: AUROC/PR, withdrawal probability, craving index, μ vs κ bias delta.
- **Sedation/Respiratory**: sedation score percentile, respiratory depression probability, EtCO₂ deviation.
- **Safety**: QTc shift, hepatic/renal clearance flags, DDIs per comorbidity set.
- **Operational**: run reproducibility (hash match), checkpoint resume success, shard failure rate, backend latency.

## Configuration & Adjustability Hooks
- **Objective weights** per SR-ID configurable via CLI/TUI (`--objectives tolerance=0 sedation=0 dependence=0` for no-tolerance/no-addiction runs) or YAML bundle.
- **Checkpoints**: resume paths under `runs/<run-id>/checkpoints`; shard-level retries with deterministic seeds.
- **Hardware hints**: `--backend {local,ray,dask}`; `INTEL_DEVICE` env for CPU/Arc GPU/OpenVINO selection.
- **Policy tuning**: swap reward functions without code changes via config map (JSON/YAML) consumed by the Optimization service.

## Governance & Validation
- **Quality gates**: fail pipeline if signatures mismatch, metrics regress, or SR-specific ceilings are exceeded.
- **CVE/Lint**: run `ruff`/`bandit` plus dependency scan before promotion; block deploy on high/critical CVEs.
- **Chain of custody**: audit log per run (user/time/backend/seeds) stored with signatures; verification enforced by dashboards before display.

## Suggested Next Steps
- Add Pydantic models for the above payloads under `src/api/models/` to codify schemas.
- Wire Prometheus/OpenTelemetry exporters in `pipeline/distributed_runner.py` for run-level observability.
- Extend `experiment_tracking` to emit SR-ID tags and bias metrics for downstream dashboards.
