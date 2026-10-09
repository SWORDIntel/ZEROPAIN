# Experimental Dissociation / State-Gating Research

> **SEPARATE RESEARCH TRACK**
>
> This directory is intentionally outside the main ZeroPain analgesic simulation package.
> Nothing here is a validated pain protocol, DID treatment, clinical dosing model, or
> recommendation for human exposure.

## Why this is separate

ZeroPain's primary mission is computational analgesic pharmacology.

This folder asks a different question:

> Can a synthetic state-transition model reproduce or falsify hypotheses about
> dissociative-state instability under methamphetamine-associated perturbation, altered
> NMDA-dependent integration, and opioid-system modulation?

The code therefore uses **dimensionless perturbation strengths**, not concentrations or
human doses.

No value such as `meth=0.75` means "75% of a dose". It is only a normalized model input.

## First model

`model.py` represents a synthetic population with latent variables for:

- baseline executive control;
- cortical/information integration;
- internal coordination;
- switching vulnerability;
- salience load.

The model independently perturbs:

- methamphetamine-associated salience/control disruption;
- NMDA antagonism / integration disruption;
- MOR partial-agonist hypothesis;
- KOR agonism;
- KOR antagonism;
- NOP agonism;
- NOP antagonism;
- disruption of a repeated waking coordination anchor.

This separation is deliberate. It allows tests such as:

```text
meth direct effect only
vs
wake-anchor disruption only
vs
meth + wake-anchor disruption
```

rather than assuming that all observed destabilization is caused by sleep loss.

## Outputs

The first implementation reports:

- mean switches;
- switching probability;
- estimated executive-state persistence;
- executive stability;
- cortical integration;
- internal coordination;
- information consistency;
- salience load.

These are synthetic latent outcomes, not diagnostic measures.

## Run the experiment matrix

From the repository root:

```bash
python -m research.dissociation.experiments \
  --subjects 10000 \
  --steps 240 \
  --output runs/dissociation_state_matrix.json \
  --csv runs/dissociation_state_matrix.csv
```

The default matrix compares:

- baseline;
- meth-only perturbation;
- wake-anchor disruption;
- meth + wake-anchor disruption;
- NMDA antagonism;
- meth + NMDA antagonism;
- meth + MOR partial-agonist hypothesis;
- meth + KOR agonism;
- meth + KOR antagonism;
- meth + NOP agonism;
- meth + NOP antagonism;
- a mixed meth/NMDA/MOR/KOR condition.

## Sensitivity analysis

The opioid and NOP coefficient signs are **assumptions**, not established DID
pharmacology. The model therefore includes a sensitivity sweep:

```bash
python -m research.dissociation.sensitivity \
  --subjects 2500 \
  --steps 160 \
  --output runs/dissociation_sensitivity.json
```

It deliberately varies MOR partial-agonist, KOR-antagonist and NOP-agonist coefficients,
including sign reversals, and records whether the proposed effect survives.

A hypothesis that only works under one convenient coefficient choice should be treated
as weak.

## Current assumptions that must be attacked

The default model currently assumes, for purposes of testing:

1. meth-like perturbation increases salience and lowers executive stability;
2. NMDA antagonism lowers cortical integration;
3. KOR agonism is destabilizing;
4. KOR antagonism may be stabilizing;
5. MOR partial agonism may reduce control variance;
6. NOP direction is uncertain;
7. waking coordination disruption can independently reduce cross-state coordination.

Items 3-6 are precisely why the sensitivity analysis exists.

## Research boundary

The model must remain unsuitable for translating to:

- opioid dosing;
- stimulant dosing;
- self-experimentation;
- procurement;
- synthesis;
- potentiation.

Future work should add **better observation models and parameter inference**, not human
dose conversion.

## Next simulation layers

Useful next additions:

1. hidden-state / HMM observer model for imperfect alter/state identification;
2. explicit co-conscious or blended-state occupancy instead of single-state switching;
3. cross-state memory graph with information propagation and withholding;
4. wake-event scheduler separate from sleep duration;
5. EEG/HRV synthetic observation channels;
6. Bayesian fitting to longitudinal observations;
7. receptor efficacy vectors (MOR/DOR/KOR/NOP) linked to the verified legacy corpus;
8. NMDA/E-I and thalamocortical submodel rather than a single integration scalar;
9. parameter recovery tests to establish whether the model is identifiable;
10. null models that reproduce switching without opioid involvement.


## Factorial interaction analysis

To test whether combinations behave non-additively:

```bash
python -m research.dissociation.factorial \
  --subjects 1500 \
  --steps 120 \
  --high 0.65 \
  --output runs/dissociation_factorial.json
```

This runs a binary factorial design across the selected perturbations and reports:

- marginal main effects;
- pairwise difference-in-differences interactions;
- ranked interactions on switching probability and all other synthetic endpoints.

That is the first tool for questions such as:

```text
Is meth + NMDA disruption worse than the sum of each alone?
Does KOR antagonism specifically modify the meth effect?
Does MOR partial agonism only shift baseline, or does it interact with meth?
Does wake-anchor disruption amplify meth independently of NMDA integration?
```

Interaction terms are model outputs, not evidence of biological synergy until the model
is fitted to real observations.


## Discrete identity-state graph

The second layer explicitly represents multiple states rather than reducing the system
to one switching hazard:

```bash
python -m research.dissociation.run_state_graph \
  --states 4 \
  --steps 480 \
  --sync-interval 96 \
  --output runs/dissociation_state_graph.json
```

Each synthetic state has:

- a current energy/fatigue level;
- a state-specific executive-access bias;
- time spent in executive control;
- event-memory accessibility.

The system models:

- executive hand-off as the current state fatigues;
- recovery of non-executive states;
- meth-associated increase in switch pressure and fatigue;
- NMDA-associated reduction in information permeability;
- MOR/KOR/NOP hypothesis coefficients;
- gradual cross-state information diffusion;
- a periodic waking/synchronization event;
- failure of that event independently from the direct meth perturbation.

Outputs include state occupancy entropy, low-energy hand-offs, memory divergence,
synchronization completion and unique states taking executive control.

This is still a toy state graph, **not a claim that DID literally implements this
algorithm**. Its purpose is to turn observations such as "another state can take over
when one is exhausted" and "missed internal meetings preceded information divergence"
into variables that can be tested and falsified.


## State-specific memory/trust network

The third layer moves beyond a single coordination scalar and gives each synthetic
state its own information access plus pairwise trust relationships:

```bash
python -m research.dissociation.run_state_network \
  --states 4 \
  --steps 480 \
  --max-coconscious 3 \
  --sync-interval 96 \
  --trace \
  --output runs/dissociation_state_network.json
```

It adds:

- **co-conscious/blended occupancy**: more than one state can be concurrently accessible;
- **pairwise trust matrix**: information-sharing propensity differs by state pair;
- **state-specific event memory**: each state can know different portions of the event stream;
- **withholding events**: emerge probabilistically when pairwise trust falls below a threshold;
- **explicit timeline events**: stress, external events, waking synchronization and manual sync;
- **fatigue-driven handoff**: current executive state loses energy while inactive states recover;
- **memory divergence**: directly measured across states rather than represented by one scalar;
- **trace output**: executive state, co-conscious set, mean trust, memory consistency and
  withholding events at every step.

The waking event remains separate from sleep duration. A missed waking synchronization
can therefore reduce information convergence without asserting that generic insomnia is
the causal mechanism.

The model does **not** declare a state deceptive or adversarial by identity. Withholding
is generated from the current network state (principally low trust), so the same
synthetic state can behave cooperatively in one run and withhold information in another.

### Layer progression

```text
scalar gating model
    -> discrete executive-state graph
    -> state-specific memory/trust network
```

This gives us increasingly expressive models while retaining simpler null models for
comparison. A more complex model only earns its keep if it predicts observations better
than the lower layers.


## Belief/claim integrity ledger

The fourth layer adds explicit **fact content** so information integrity can be measured
rather than inferred from accessibility alone:

```bash
python -m research.dissociation.run_belief_network \
  --states 4 \
  --steps 480 \
  --sync-interval 96 \
  --trace \
  --output runs/dissociation_belief_network.json
```

Each external fact has a simulator-only ground truth. Synthetic states can:

- observe it correctly or incorrectly;
- not observe it at all;
- share it with another state;
- withhold it when pairwise trust is low;
- emit a false report when trust falls much further;
- reconcile beliefs at a successful synchronization event.

This allows three quantities that were previously conflated to be separated:

```text
cross-state consistency
truth accuracy
false consensus
```

A system can therefore become **highly consistent and still wrong**, which matters when
a synchronization event propagates a majority belief rather than privileged ground
truth.

### Cooperation → fragmentation → adversarial regime

The model also exposes a deliberately simple regime classifier:

```text
COOPERATIVE
  high trust + high consistency

FRAGMENTED
  intermediate trust / inconsistent information

ADVERSARIAL
  very low trust or sustained false-report rate
```

These labels are simulation taxonomy, not diagnostic categories.

Crucially, no synthetic state is assigned a permanent "liar" or "hostile" identity.
Withholding and false reporting arise from the current pairwise trust network. The
same synthetic state can therefore cooperate in one run and become adversarial in
another.

The default model also sets:

```text
direct_meth_misreport_weight = 0
```

so methamphetamine does **not** automatically cause deception by fiat. If a fitted
model eventually requires a direct effect, it must outperform the indirect pathway:

```text
meth/NMDA perturbation
    -> encoding/information divergence
    -> contradictions
    -> trust erosion
    -> withholding
    -> false reporting
```

That distinction is central to making the observation falsifiable rather than merely
encoding it into the answer.


## Synthetic physiology observation layer

The fifth layer is an **observation model**, not another causal model. It converts the
latent state trace into synthetic standardized physiological features:

- autonomic-rate-like feature;
- autonomic-variability-like feature;
- synthetic EEG delta/theta/alpha/beta/gamma features.

Run:

```bash
python -m research.dissociation.run_observation_model \
  --states 4 \
  --steps 480 \
  --output runs/dissociation_observation_model.json
```

The features are arbitrary z-like units, not bpm, Hz power, or clinical EEG values.

It is designed to test four specific observations:

1. **state-specific clusters** can be stable enough to classify;
2. **co-conscious/blended states** appear as weighted mixtures of state signatures;
3. **switches can produce short transients** superimposed on the new state;
4. common perturbations/noise can reduce classification confidence without erasing
   the underlying state structure.

The model reports:

- nearest-signature classification accuracy on pure-state steps;
- between-state signature separation;
- within-state variance;
- blend reconstruction error;
- mean switch-transient residual;
- nonswitch residual.

This creates a clean analysis target for future EEG/HRV work: a real dataset can be
asked whether a mixture model or switch-transient model explains observations better
than a simple mood/arousal-only model.


## Belief-network phase sweep

The default model intentionally does **not** force methamphetamine to cause false
reporting. To find where the cooperative → fragmented → adversarial transition actually
appears, sweep the starting trust level:

```bash
python -m research.dissociation.belief_phase_sweep \
  --trust-levels 0.20 0.30 0.40 0.50 0.60 0.70 0.80 \
  --steps 240 \
  --seeds 5 \
  --output runs/dissociation_belief_phase_sweep.json
```

For each trust level and perturbation profile it reports:

- final pairwise trust;
- truth accuracy;
- withholding rate;
- false-report rate;
- probability of any false report;
- fraction of time classified as adversarial;
- probability of ending in the adversarial regime.

Profiles include baseline, meth, meth+NMDA, wake disruption, meth+wake disruption and
meth+NMDA+wake disruption.

The output also estimates the highest starting trust at which false reporting or an
adversarial regime still appears.

### Direct-effect falsification control

By default:

```text
direct_meth_misreport_weight = 0
```

A sensitivity run can explicitly add a direct pathway:

```bash
python -m research.dissociation.belief_phase_sweep \
  --direct-meth-misreport-weight 0.20
```

That is not the preferred model. It is a falsification/control condition: if the
indirect trust/divergence model cannot reproduce observations but a direct term can,
that becomes evidence that the current mechanism is incomplete.


## Parameter recovery and model comparison

The next layer tests whether the research stack is **identifiable**, rather than merely
capable of producing attractive simulations.

### Scalar mechanism recovery

```bash
python -m research.dissociation.parameter_recovery \
  --subjects 500 \
  --steps 60 \
  --parameters \
    meth_salience_weight \
    nmda_integration_weight \
    mor_partial_control_weight \
    kor_antagonist_control_weight \
    wake_coordination_weight \
  --output runs/dissociation_parameter_recovery.json
```

The benchmark:

1. generates synthetic observations from known hidden coefficients;
2. generates target data and candidate simulations from **different random seeds**;
3. fits only a set of training perturbation conditions;
4. recovers selected parameters with deterministic coordinate-grid refinement;
5. reports absolute/relative parameter errors;
6. evaluates the recovered model on **held-out combination conditions** such as
   meth+NMDA and meth+wake disruption.

If a coefficient cannot be recovered from synthetic data generated by the same model,
there is no credible basis for expecting it to be identifiable from noisier real data.

### Held-out physiology model comparison

```bash
python -m research.dissociation.model_comparison \
  --states 4 \
  --steps 720 \
  --output runs/dissociation_model_comparison.json
```

Four nested observation models are compared:

```text
null mean-only
    ↓
executive-state identity
    ↓
co-conscious weighted mixture
    ↓
mixture + compact state-derivative transient basis
    ↓
mixture + high-dimensional pair-specific transient basis
```

Each model is fitted on training timepoints and evaluated on held-out timepoints.

Reported metrics:

- train/test RMSE;
- train/test R²;
- BIC;
- number of fitted parameters.

This provides two separate complexity checks:

- **held-out prediction** asks whether the extra structure generalizes;
- **BIC** asks whether improved in-sample fit is worth the extra parameters.

The richest model is not presumed correct. If a simpler state-only or even null model
predicts equally well, the extra mixture/transient machinery has failed to earn its
complexity.

### Current research rule

A proposed biological mechanism should survive all three layers:

```text
sensitivity analysis
    +
synthetic parameter recovery
    +
held-out model comparison
```

before it is treated as worth fitting to real longitudinal observations.


## Jacobian/SVD identifiability

Parameter recovery can succeed even when two coefficients are nearly interchangeable.
The local identifiability analysis directly measures that problem:

```bash
python -m research.dissociation.identifiability \
  --subjects 500 \
  --steps 60 \
  --replicates 3 \
  --output runs/dissociation_identifiability.json
```

It finite-differences each selected mechanism coefficient across all fitting conditions
and observable metrics, producing a normalized Jacobian.

The tool reports:

- singular values;
- numerical rank;
- condition number;
- per-parameter sensitivity norm;
- pairwise cosine similarity between parameter-effect vectors;
- parameter pairs whose effect vectors are nearly parallel.

A coefficient may be highly sensitive but still **not identifiable** if another
coefficient produces almost the same observable pattern.

## Repeated-seed model-selection stability

One synthetic dataset is insufficient to select an observation model. Run the same
comparison over independent state/observation seeds:

```bash
python -m research.dissociation.model_selection_stability \
  --seeds 8 \
  --steps 480 \
  --output runs/dissociation_model_selection_stability.json
```

For baseline, meth, NMDA and meth+NMDA scenarios it records:

- the held-out RMSE winner for every seed;
- the BIC winner for every seed;
- median and mean held-out RMSE by model;
- median held-out R²;
- median BIC;
- winner counts.

The candidate stack now includes both:

```text
mixture + compact state-derivative transient
mixture + high-dimensional pair-specific transient
```

The pair-specific model is deliberately retained as an overfitting control. If it wins
training fit but repeatedly loses held-out prediction/BIC, that is useful evidence
against paying for that complexity.


## Experimental-design optimisation

The first design optimiser answers: **which dimensionless model conditions are worth
simulating/observing, and which ones are redundant?**

```bash
python -m research.dissociation.experimental_design \
  --subjects 400 --steps 50 --replicates 2 \
  --max-condition 6 --min-information-fraction 0.35 \
  --validation-seeds 211 311 \
  --recovery-check --recovery-grid-points 7 --recovery-passes 3 \
  --max-recovery-inflation 1.5 \
  --output runs/dissociation_experimental_design.json
```

The fixed candidate library includes baseline, single-factor meth/NMDA/MOR-partial/
KOR-antagonist/wake conditions, and selected combinations. **These are unitless model
perturbations, not proposed human drug challenges.**

Algorithm:

1. Compute one finite-difference Jacobian across the **entire** condition library.
   Preserve the same metric normalization when examining every subset.
2. Score the full reference design for rank, singular values, condition number and
   regularised log-det information.
3. Use rank-first greedy forward selection to meet full rank, conditioning and
   minimum singular-value retention requirements.
4. Remove redundant conditions with a feasibility-preserving backward deletion pass.
5. Run leave-one-out ablation on the **full candidate library** to quantify each
   condition's information loss.
6. Optionally compare parameter recovery on the selected vs full candidate library,
   using **identical fitting hyperparameters, independent seeds and held-out tests**.
   If the reduced design degrades recovery too far, add high-information conditions
   and re-run recovery. This is a second-stage surrogate search, not global optimisation.
7. Validate the **final** chosen subset with independent random seeds.

Result JSON records all candidate input vectors, selected conditions, every
add/remove decision, rank/condition numbers, full-pool ablations and independent-seed
validation. If the library is rank deficient or the budget makes the constraints
impossible, the tool **reports infeasibility**; it does not fabricate a successful
design.

**Important limitations:** greedy selection is not guaranteed to find a mathematically
minimal set; Jacobian rank is only **local** identifiability at the chosen simulated
parameters; preserving rank/conditioning does not prove biological validity.
Independent-seed validation reduces—but does not eliminate—simulation selection bias.
The optional recovery check specifically handles this case. Reduced-design recovery
may be materially worse even when the Jacobian's rank and condition number look good;
the matched full-design control exposes that failure.

Use `--budget 4` to test whether a strict condition count suffices. Too-small
budgets are expected to fail explicitly, not trigger silent relaxation.

The project remains a computational research harness. The optimiser must never be
reinterpreted as a protocol for administering methamphetamine, opioids or NMDA agents
to people.


## Observable-only identification benchmark

The previous Jacobian/condition-selection benchmarks had a significant modelling
advantage: they directly read hidden simulator metrics for integration, internal
coordination and executive control. Real observers cannot read those latents.

The new `observable_model.py` puts a **measurement boundary** between the latent
scalar state-gating simulator and the parameter fitter. The measurement adapter
generates deliberately imperfect *synthetic readouts*:

- **observer_switch_rate** — switches detected by an imperfect observer, including
  misses and false-positive reports;
- **paired_recall_success** — noisy finite-trial cross-state information-continuity test;
- **morning_plan_agreement** — finite-trial reported agreement on a shared plan;
- **wearable_arousal_index** — synthetic autonomic-like summary with measurement noise;
- **eeg_connectivity_index** — synthetic EEG-like connectivity proxy with measurement
  noise; **not derived from a real EEG signal and not clinically validated**.

The observer can miss observations. Unobserved entries are `NaN`, not zero or an
imputed success. All readouts intentionally mix multiple latent mechanisms rather
than revealing the true internal scalar values.

`observable_design.py` compares four measurement panels using the same nineteen
**dimensionless simulation conditions**:

```bash
python -m research.dissociation.observable_design \
  --subjects 180 --steps 30 --replicates 2 \
  --panels switch_only observer_only observer_wearable multimodal \
  --missing 0.10 --validation-seeds 711 \
  --output runs/dissociation_observable_design.json
```

The benchmark reports each panel's full-library Jacobian rank, rank-preserving
condition subset (when feasible), condition number, independent-seed validation,
and blind parameter recovery using only noisy observed channels. Full-vs-reduced
recovery uses the same sampling and fitter settings; held-out observations include
a synthetic measurement-noise floor for context. Measurement randomness is **keyed
by named condition**, so the same scenario receives the same synthetic noise and
missingness regardless of subset membership or iteration order.

**Formal rank is not recovery quality.** The JSON separately flags whether blind,
noisy mean parameter recovery error is <=20% and held-out loss is <=1.5x an oracle
noise floor. These are **arbitrary computational screening thresholds**, not
clinical effect-size criteria. A panel can retain full Jacobian rank and still
fail these recovery checks; such a panel must not be described as reliable.

**Important methodological distinction:** the finite-difference Jacobian uses the
*expected measurement process* with common simulation seeds, not randomly resampled
noisy observations. Otherwise noise alone can create a misleading, apparently
full-rank Jacobian. Actual recovery separately faces finite observation trials,
measurement noise, independent simulation seeds and missing entries.

Do **not** interpret a successful synthetic rank test as evidence that any opioid,
NMDA or catecholamine mechanism actually controls DID switching. The wearable/EEG
channels here are intentionally fabricated proxy readouts, not established biomarkers.
The next step requires real, consented longitudinal observational data and testing
an alternative model without these hypothesised receptor mechanisms. There is no
basis for using these candidate conditions as human drug-challenge protocols.


## Longitudinal competing-null benchmark

Formal identifiability is not enough. A receptor-labelled model must beat simpler
explanations on held-out longitudinal observations, and the benchmark must also
recognize when those simpler explanations are actually true.

`longitudinal_nulls.py` generates synthetic repeated-session panels under three
different truth families:

```text
receptor truth
    existing dimensionless meth / NMDA / MOR-partial / KOR-antagonist / wake model

context truth
    generic stress + sleep/wake irregularity + social-conflict load + history only

mixed truth
    convex mixture of the two generators
```

The competing models are:

- mean-only;
- autoregressive/history-only;
- context-only;
- context + history;
- mechanism labels only;
- context + mechanism;
- full context + history + mechanism.

All models receive the same subject fixed effects and are scored on each subject's
**held-out final sessions**, not random row holdout.

```bash
python -m research.dissociation.longitudinal_nulls \
  --subjects 6 --sessions 24 \
  --micro-population 90 --steps 28 \
  --missing 0.10 \
  --output runs/dissociation_longitudinal_nulls.json
```

### Required falsification checks

The benchmark intentionally makes non-pharmacological context mildly correlated with
some mechanism labels, so receptor covariates do not get an unrealistically easy
classification problem.

It also permutes mechanism labels **within subject** while preserving stress, wake,
history, outcomes and temporal ordering. Under receptor-generated truth the mechanism
advantage should weaken after permutation. Under context-generated truth, receptor
labels should not be required at all.

A benchmark where the receptor model wins both receptor-truth and context-truth
datasets is considered **biased**, not successful.

### Current scope

This is still synthetic session-level longitudinal data. It is not a human exposure
schedule. The mechanism fields are dimensionless model labels, and the wearable/EEG
outcomes remain synthetic proxies.

The purpose of this layer is model falsification:

```text
Can generic context + history explain the same observations?
If yes -> receptor mechanism not identified.
If no  -> receptor-labelled model earns further testing, not acceptance.
```

The next bridge to real data is a consented observational CSV schema with no required
drug exposure fields, followed by the same blocked-time null-model comparison.


## Consented observational CSV bridge

`observational_csv.py` runs the same blocked-time comparison against a user-supplied
CSV without requiring any receptor/drug annotations.

Schema:

- [OBSERVATIONAL_DATA_SCHEMA.md](OBSERVATIONAL_DATA_SCHEMA.md)
- [observer-only CSV template](examples/observational_template.csv)

Example:

```bash
python -m research.dissociation.observational_csv observations.csv \
  --test-fraction 0.25 \
  --output runs/dissociation_observational_csv.json
```

The importer:

- accepts direct rates or raw counts/trials;
- derives within-subject lagged observations;
- derives a normalized time trend when one is absent;
- preserves missing outcomes rather than turning them into zeros;
- drops predictor-incomplete rows only for models requiring those predictors;
- rejects duplicate subject/session records;
- uses each subject's final sessions as held-out test data;
- reports which context and mechanism annotations actually exist.

If mechanism annotations are absent, models that require them are **not run**. This
prevents "no exposure data" from being silently interpreted as "zero receptor effect."

The default template intentionally contains **no mechanism columns**.


### Repeated-seed null-model stability

`longitudinal_null_stability.py` repeats the receptor/context/mixed truth benchmark
over independent synthetic datasets:

```bash
python -m research.dissociation.longitudinal_null_stability \
  --seeds 5 --subjects 5 --sessions 18 \
  --output runs/dissociation_longitudinal_null_stability.json
```

It records:

- mechanism-family and context-family win counts;
- median mechanism gain over the best non-mechanism null;
- minimum/median penalty after within-subject mechanism-label permutation;
- context-truth spurious mechanism gain.

The executable exits non-zero when its **synthetic benchmark-health** checks fail.
Those gates only test whether the benchmark can recover the truth family it generated
itself. They are not biological significance thresholds.


### Observational mechanism-label permutation audit

When a real observational CSV contains optional mechanism annotations,
`observational_permutation.py` asks whether those annotations improve held-out
prediction beyond what would be expected when their temporal alignment is broken.

```bash
python -m research.dissociation.observational_permutation observations.csv \
  --permutations 500 \
  --output runs/dissociation_observational_permutation.json
```

The default randomization uses a **joint circular shift within each subject**. All
mechanism annotation columns move together, preserving their within-session
relationships and each subject's marginal annotation distribution while breaking the
original alignment with outcomes.

The report compares the observed mechanism-model gain with the randomization
distribution and returns an empirical upper-tail probability.

This remains an association diagnostic. It does not remove time-varying confounding,
measurement error, reverse causation or selection effects and therefore must not be
reported as proof of receptor causality.


## ECC-like silent result verification

The research runners can now carry a small **verification syndrome** alongside the
normal audit log, analogous to ECC check bits.

Cheap mode:

```bash
ZEROPAIN_VERIFY=1 \
ZEROPAIN_VERIFY_LOG=runs/verification.jsonl \
python -m research.dissociation.run_belief_network
```

Nothing extra is printed when checks pass. The normal result JSON is unchanged.
One compact JSONL audit record is appended.

Strict mode:

```bash
export ZEROPAIN_VERIFY=1
export ZEROPAIN_VERIFY_STRICT=1
```

A non-zero syndrome raises immediately *after* the failed audit record is written.

Full replay mode:

```bash
export ZEROPAIN_VERIFY_REPLAY=1
```

For runners with a replay hook, the computation is run a second time from the recorded
configuration/seed and canonical result hashes are compared. This is deliberately
separate because it can roughly double runtime.

Current syndrome bits:

| Bit | Meaning |
|---:|---|
| `0x01` | canonical serialization failed |
| `0x02` | NaN/Inf or another non-finite result |
| `0x04` | semantically bounded probability/accuracy/consistency/trust value escaped `[0,1]` |
| `0x08` | model-specific cross-field invariant failed |
| `0x10` | deterministic replay mismatch |
| `0x20` | independent checker/implementation disagreement |
| `0x40` | written JSON does not round-trip to the in-memory result digest |

Examples of model-specific relations already checked include completed sync events not
exceeding expected sync events, false-report/withholding counts not exceeding
communication opportunities, recovered coefficients staying inside their declared
search bounds, and model winners actually existing in the scored model table.

Scrub old results:

```bash
python -m zeropain.verification_scrub \
  --log runs/verification.jsonl
```

The scrubber is quiet on success and exits non-zero if a referenced result disappeared,
became unreadable or no longer hashes to the value originally verified.

**What this proves:** corruption, impossible values, broken internal relations,
nondeterministic replay and—when supplied—disagreement with an independent
implementation.

**What it does not prove:** that two identical implementations share no bug, or that a
scientific mechanism is true. For important calculations, the strongest check bit is
still `0x20`: compute the same quantity by a genuinely independent path and compare.
