# Longitudinal Observational Data Schema

This schema is for **consented observational data analysis**. It is not a protocol for
administering drugs, changing medication, or deliberately provoking dissociative states.

The analysis code accepts ordinary repeated observations even when there are **no drug
or receptor annotations at all**. In that case mechanism-labelled models are skipped.

## Required identifiers

| Column | Meaning |
|---|---|
| `subject_id` | Stable de-identified participant identifier. |
| `session_index` | Monotonic within-subject session number. |

Do not put names, addresses, phone numbers, medical-record identifiers or other direct
identifiers in this analysis CSV.

## Outcomes

At least one outcome family must contain data.

### Observed switching

Either:

```text
observer_switch_rate
```

or:

```text
observer_switch_count
switch_observation_checks
```

A "check" should be defined consistently within a dataset. The code does not decide
whether an observed behavioural change is truly a dissociative switch.

### Information continuity

Either:

```text
paired_recall_success
```

or:

```text
recall_successes
recall_trials
```

The task itself must be specified externally. This repository does not treat generic
memory failure as diagnostic of DID.

### Shared-plan / coordination measure

Either:

```text
morning_plan_agreement
```

or:

```text
plan_agreement_successes
plan_trials
```

"Morning" is historical terminology from the motivating observation. A real study can
use any consistently defined coordination checkpoint.

### Optional sensor summaries

```text
wearable_arousal_index
eeg_connectivity_index
```

These are **generic numeric slots** in the importer. Their names match the synthetic
benchmark for compatibility. They are not validated DID biomarkers and the importer
does not infer physiological meaning from them.

## Non-pharmacological context

Optional columns:

```text
stress_load
sleep_wake_irregularity
social_conflict_load
time_trend
```

`time_trend` is derived from session order when absent.

Scales should be documented in dataset metadata. The comparison model treats these as
ordinary covariates, not diagnoses.

## Optional mechanism annotations

The following columns are optional research annotations:

```text
meth
nmda_antagonism
mor_partial_agonism
kor_antagonism
wake_anchor_disruption
```

They are **not dose fields**. This analysis path expects dimensionless or externally
standardized covariates. Do not place dose-conversion logic in this repository.

If these columns are missing, the importer reports that fact and does not run
mechanism-labelled models.

## Missing data

Recognized missing tokens:

```text
blank
NA
NaN
N/A
null
none
.
```

Outcome missingness is retained. Predictor rows missing required covariates for a model
are excluded from that model's fit rather than silently filled with zero.

## Temporal validation

The default comparison uses a **blocked within-subject time split**:

```text
earlier sessions -> fit
final sessions   -> held-out test
```

It does not randomly shuffle sessions across train/test.

## Example

The repository includes:

```text
research/dissociation/examples/observational_template.csv
```

The template intentionally contains no mechanism/drug columns.
