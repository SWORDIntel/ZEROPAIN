# HumanSim research stack

HumanSim is a separate multiscale virtual-human research track.

It is **not** the legacy ZeroPain one-compartment patient simulator and it is not a
clinical dosing engine. The aim is to replace dimensionless top-down mechanism knobs
with a sequence of biologically interpretable layers that can each be calibrated,
falsified and independently verified.

## Architecture

Planned dependency direction:

```text
source-backed phenotype / physiology
        ↓
perfusion-limited PBPK
        ↓
free brain exposure
        ↓
receptor occupancy
        ↓
target efficacy / coupling
        ↓
receptor internalisation + recovery
        ↓
intracellular/signalling models
        ↓
neural-population dynamics
        ↓
autonomic / circadian / endocrine state
        ↓
cognitive/state-transition model
        ↓
observable behaviour + physiology
```

The dependency arrow is intentional. Higher layers should not directly reach through
the lower layers and set receptor activity or brain concentration by hand.

## Milestone 1 — implemented

Current executable chain:

```text
Physiology
   │
   ├── central compartment
   ├── brain
   ├── liver
   ├── kidney
   └── peripheral tissue
          ↓
perfusion-limited exchange + hepatic/renal clearance
          ↓
free brain concentration
          ↓
Hill/Langmuir target occupancy
          ↓
effect gain + polarity
          ↓
surface receptor availability
          ↓
downstream coupling availability
```

Run the synthetic fixture:

```bash
python -m research.human_sim.run_pbpk_receptor \
  --duration-h 12 \
  --dt-h 0.05 \
  --initial-central-units 1.0 \
  --output runs/human_sim_pbpk_receptor.json
```

The amount is deliberately in **arbitrary units**. There is no mg/kg conversion,
administration preset or human dose recommendation.

Add `--trace` to include the full time series.

## Numerics

For each tissue:

```text
dA_t/dt = Q_t (C_c - C_t/Kp_t)
```

is represented as bidirectional first-order exchange:

```text
k_c→t = Q_t / V_c
k_t→c = Q_t / (V_t Kp_t)
```

Each central↔tissue pair is advanced with the exact two-state analytical solution
for that timestep. This gives:

- non-negative compartment amounts;
- exchange-level exact mass conservation;
- explicit accumulation of eliminated amount;
- a measurable whole-system mass-balance residual.

The current sequential operator split is intentionally simple. A future numerical
comparison should test symmetric splitting / matrix-exponential integration before
claiming high-fidelity short-timescale kinetics.

## Receptor layer

Binding and effect are separate:

```text
occupancy = C^n / (Kd^n + C^n)

effective signal
    = occupancy
    × target effect gain
    × surface receptor fraction
    × downstream coupling fraction
```

This prevents "same occupancy = same effect" from being built into the architecture.

The generic adaptation state contains:

- surface receptor fraction;
- coupling fraction;
- activity-dependent internalisation/desensitisation;
- recycling/resensitisation.

This gives the model biological memory: the same concentration at two different times
can produce different effects because the receptor/signalling state has changed.

## Verification

The milestone runner uses ZeroPain's ECC-like verifier.

With:

```bash
export ZEROPAIN_VERIFY=1
export ZEROPAIN_VERIFY_STRICT=1
export ZEROPAIN_VERIFY_REPLAY=1
```

it checks:

- finite outputs;
- probability/occupancy-like bounds;
- PBPK mass-balance residual;
- receptor occupancy/signal bounds;
- surface/coupling bounds;
- written-file round trip;
- deterministic full-chain replay.

`syndrome=0` means those computational checks passed. It does not mean the
physiology or pharmacology is calibrated correctly.

## Critical current limitation

`synthetic_reference_physiology()` and `synthetic_target_panel()` are SOFTWARE
FIXTURES.

Their values are explicitly marked:

```text
SYNTHETIC_REFERENCE_DO_NOT_USE_CLINICALLY
```

They are not asserted to be literature-derived human organ volumes, flows,
partition coefficients, clearances, receptor affinities or efficacies.

This is deliberate: architecture first, then sourced calibration.

## Next milestones

### Milestone 2 — source-backed virtual physiology — IN PROGRESS

HumanSim now supports importing **correlated virtual individuals** from an
`httk::httkpop_generate()` CSV instead of inventing independent Gaussian organ
variation.

Generate a source-backed population externally in R:

```r
library(httk)
set.seed(42)

pop <- httkpop_generate(
  method = "direct resampling",
  nsamp = 1000,
  agelim_years = c(18, 79)
)

write.csv(pop, "httkpop.csv", row.names = FALSE)
```

Then run:

```bash
python -m research.human_sim.run_population httkpop.csv \
  --output runs/human_sim_population.json
```

The adapter currently keeps brain, liver and kidney explicit and lumps the remaining
body mass/flow into a peripheral compartment. That is a **documented model-reduction
transform**, not a lossless reproduction of httk.

The output records:
- source ID and citation registry;
- SHA-256 of the imported population file;
- individual count;
- exact transform descriptions;
- empirical physiology means/SDs;
- empirical 5th/50th/95th percentile model outcomes.

This preserves covariance between body size, tissue masses and flows because complete
individual rows are imported together.

### Important architecture correction

Tissue/plasma partition coefficients, unbound fractions and clearance are **not human
physiology constants**. They now live in `CompoundDisposition`.

```text
Physiology
  organ volume
  organ blood flow
  central volume

CompoundDisposition
  tissue:plasma partition coefficients
  plasma/brain unbound fraction
  hepatic clearance
  renal clearance
```

The same virtual person can therefore be reused across many compound profiles without
changing their anatomy.

Every calibrated parameter should carry:

```text
value/distribution
units
population
source
source date
assay/measurement context
uncertainty
evidence status
```

No unsourced default should silently become a "human" constant.

### Population source provenance

Current registry entries include:
- `httk_population` — Ring et al. 2017 virtual-population methodology;
- `httk_tissue` — httk physiology/tissue tables and their compiled references;
- `pksim_population` — Open Systems Pharmacology human population database/export;
- `schmitt_partitioning` — compound-specific tissue partition modelling.

The committed `examples/httkpop_synthetic_fixture.csv` exists **only for CI** and is
not a real httk export.

The density conversions used by the current reduced httk adapter are explicit
approximation constants and remain a calibration TODO. A later adapter should ingest
direct organ volumes where the upstream population export provides them.

### Milestone 3 — multi-ligand receptor competition — IMPLEMENTED

HumanSim now supports same-site competitive occupancy across simultaneous ligands:

```text
w_i = (C_i / Kd_i)^n
occupancy_i = w_i / (1 + Σw)
unbound receptor = 1 / (1 + Σw)
```

Signal is then computed separately from binding:

```text
Σ occupancy_i × efficacy_i × polarity_i
    × surface receptor fraction
    × coupling fraction
```

Therefore:
- an antagonist can occupy receptor without producing agonist signal;
- a partial agonist can bind similarly while producing less signal;
- multiple ligands compete for the same receptor pool;
- target adaptation acts on the resulting signal history.

Current limitation: each ligand's PBPK is simulated independently, then combined at
the receptor layer. This models **PK independence + PD competition**, not metabolic,
transporter or protein-binding drug-drug interactions.

Synthetic demonstration:

```bash
python -m research.human_sim.run_multiligand \
  --output runs/human_sim_multiligand.json
```

The demonstration uses arbitrary units and a synthetic agonist/antagonist pair.

### Milestone 4 — signalling

Add target-specific signalling models only where source data justify them:

- G-protein coupling;
- arrestin/internalisation pathways;
- second-messenger state;
- slow homeostatic adaptation.

### Milestone 5 — reduced neural populations

Do **not** jump directly to millions of detailed neurons.

Start with approximately 6–12 calibrated population nodes and only increase
resolution when held-out observations require it.

Candidate layers include PFC/executive control, salience, striatal gating,
thalamocortical integration and locus-coeruleus/autonomic coupling.

### Milestone 6 — virtual-human ensemble

A human simulation should return a distribution:

```text
P(outcome | phenotype, physiology, exposure history, model uncertainty)
```

not one deterministic "average person".

Population generation should preserve parameter correlations rather than sampling
every biological variable independently.

## Research rule

Complexity earns its place only when it improves:

1. held-out prediction;
2. parameter recovery;
3. independent-seed stability;
4. observable-only identifiability;
5. competing-null performance.

If a simpler model performs equally well, keep the simpler model.
