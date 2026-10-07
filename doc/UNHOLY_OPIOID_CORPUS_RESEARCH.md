# Legacy "Unholy Opioid" Corpus — Research Integration

> Status: **historical hypothesis corpus / unverified**
>
> This material is useful because it contains unusual receptor combinations and forgotten
> compounds. It is **not** a trusted pharmacology source and must not be copied directly
> into clinical guidance, dosing recommendations, or the validated ZeroPain simulation
> registry.

## Why this exists

ZeroPain already contains generated shadows of a large historical opioid/pharmacology
notebook in:

- `parsed_compounds.py`
- `parsed_activities.py`
- portions of `src/opioid_analysis_tools.py`

Those files preserve a surprisingly broad set of opioid, NOP/ORL-1, NMDA, sigma,
cholinergic, histaminergic, CCK, enkephalin and mixed-mechanism compounds. The source
notes were informal and include errors, outdated scheduling claims, potency folklore,
strong therapeutic assertions, and receptor assignments that require modern review.

The correct use is therefore:

```text
legacy claim
    -> extract target/mechanism
    -> flag high-risk or stale assertion
    -> verify against primary/current literature
    -> encode receptor efficacy + affinity separately
    -> only then permit promotion into validated simulation
```

## Mandatory provenance rule

Every record derived solely from the historical notebook starts as:

```text
evidence_status = legacy_unverified
simulation_eligible = false
```

ZeroPain must not infer that a claim is true simply because an old generated
`CompoundProfile` contains it.

Run:

```bash
python scripts/audit_legacy_opioids.py --only-flagged
```

The audit emits a JSON review queue rather than modifying the compound registry.

## Highest-value research axes

### 1. Mixed / partial opioid receptor efficacy

Priority compounds and families include:

- **Buprenorphine-like architecture** — high-affinity MOR partial agonism combined
  with KOR antagonism/inverse agonism and NOP activity.
- **Dezocine** — mixed/partial opioid pharmacology with additional monoaminergic
  activity; assay-dependent receptor behavior deserves careful separation.
- **Picenadol / levopicenadol**
- **SoRI-9409**
- **Proxorphan / cyclorphan / mixed benzomorphans**
- **Nalbuphine / butorphanol / pentazocine**

The key model change is to avoid a single `intrinsic_activity` field when a ligand has
different efficacy at MOR, DOR, KOR and NOP. Affinity and efficacy are independent
dimensions.

### 2. KOR / dynorphin and dissociation

The corpus contains many selective or KOR-heavy ligands:

- Enadoline
- U-50488
- U-69,593
- ICI-199,441
- BRL-52537
- bremazocine
- salvinorin A and analogues
- tifluadom/tifluradom-class entries

This family is particularly important because controlled human enadoline exposure has
produced depersonalization, perceptual distortion and psychotomimetic effects. KOR
agonism should therefore be treated as a **candidate pro-dissociative mechanism**, not
as a generic "anti-addiction" virtue.

Reference:
https://pubmed.ncbi.nlm.nih.gov/11594439/

### 3. Opioid antagonism and dissociation

A 2023 systematic review/meta-analysis found a signal for opioid antagonists
(naltrexone, naloxone and nalmefene) reducing dissociative symptoms, but the evidence
base was tiny and heterogeneous: five comparative studies, 154 participants, pooled
effect `d = 1.46`, with likely publication bias.

This is enough to justify a research axis, not enough to declare an established
treatment.

Reference:
https://pubmed.ncbi.nlm.nih.gov/37860852/

### 4. NOP / ORL-1

The corpus contains both agonists and antagonists:

- J-113,397
- SB-612,111
- MCOPPB
- NNC 63-0532
- Ro64-6198

NOP should be modeled independently rather than collapsed into MOR. Candidate endpoints
include reward/salience modulation, stress response, memory effects and executive-state
stability.

### 5. Opioid × NMDA / glutamate polypharmacology

Priority entries include:

- ketobemidone
- levorphanol / dextrorphan / methorphan-family compounds
- nortilidine stereoisomers
- dextromethorphan
- ibogaine / noribogaine
- alazocine
- Hodgkinsine
- orphenadrine and other non-opioid NMDA-active comparators

Ketamine provides a causal model for pharmacologically induced dissociation through
NMDA receptor antagonism, cortical disinhibition and altered thalamocortical
connectivity.

Reference:
https://pubmed.ncbi.nlm.nih.gov/41453872/

### 6. Endogenous peptide amplification

The historical notes include:

- RB-101
- RB-120
- RB-3007
- met-enkephalin
- leu-enkephalin
- biphalin
- opiorphin

These are interesting because preserving endogenous peptide signaling is spatially and
temporally different from administering a high-efficacy exogenous MOR agonist. Direction
of effect on dissociation is **not assumed**.

### 7. CCK and tolerance interaction

- proglumide
- devazepide
- lorglumide

These belong in a tolerance/sensitization research track rather than being mixed into
the primary opioid receptor model without evidence.

## Immediate correction queue

The following legacy claim classes require priority review:

1. **Ketobemidone receptor direction** — the historical text labels it a MOR
   antagonist. Modern pharmacology describes ketobemidone as an opioid agonist with
   NMDA-antagonist properties.
2. **"No addiction/dependence regardless of dose"** — reject absolute safety claims
   unless supported by unusually strong evidence.
3. **"Cure" language** — addiction/disease cure claims are never promoted directly.
4. **KOR agonist = anti-addiction = beneficial** — anti-reinforcement and
   anti-dissociation are not equivalent; KOR agonism can itself be dysphoric and
   dissociogenic.
5. **Beta-arrestin simplification** — "low beta-arrestin recruitment therefore no
   tolerance/dependence/respiratory risk" is not an acceptable modern inference.
6. **Legal / unscheduled / RC labels** — considered stale metadata by default.
7. **Potency multipliers** — must be traced to assay, route, species and endpoint.
8. **Single efficacy value across receptors** — invalid for mixed agonist/antagonist
   compounds.

## Proposed evidence schema

A verified research record should eventually carry:

```text
compound_id
canonical_name
synonyms
source_claim
source_type
evidence_grade
verification_date

MOR: Ki, efficacy, assay
DOR: Ki, efficacy, assay
KOR: Ki, efficacy, assay
NOP: Ki, efficacy, assay

NMDA: mode + potency + assay
sigma1/sigma2
NET/SERT/DAT
nAChR
HCN1
other_targets

PK:
  half_life
  active_metabolites
  route-specific_bioavailability
  protein_binding
  metabolic_pathways

phenotypes:
  analgesia
  respiratory_depression
  dysphoria
  euphoria
  dissociation
  tolerance
  dependence
  convulsant_signal

citations[]
review_notes
simulation_eligible
```

## Promotion gate

A legacy compound may enter a validated simulation only when:

1. receptor direction (agonist / partial agonist / antagonist / inverse agonist) is
   resolved per target;
2. affinity and efficacy are supported by a traceable source;
3. route/species/assay context is recorded;
4. contradictory sources are represented rather than silently averaged;
5. high-risk safety assertions are independently reviewed;
6. scheduling/legal status is not treated as pharmacology;
7. any clinical conclusion is explicitly separated from computational hypothesis.

## What not to preserve as operational guidance

The historical notebook also contained procurement, potentiation and administration
ideas around extremely potent opioids. Those are not useful inputs to ZeroPain's
scientific model and should remain excluded from executable workflows.

The value of this corpus is its **forgotten receptor combinations**, not instructions
for unsafe exposure.
