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
2. fits only a set of training perturbation conditions;
3. recovers selected parameters with deterministic coordinate-grid refinement;
4. reports absolute/relative parameter errors;
5. evaluates the recovered model on **held-out combination conditions** such as
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
mixture + switch-transition transient basis
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
