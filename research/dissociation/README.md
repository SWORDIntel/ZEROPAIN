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
