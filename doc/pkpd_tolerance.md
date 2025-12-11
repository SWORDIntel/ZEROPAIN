# PK/PD Calibration, Tolerance, and Scenarios (ZeroPain)

## PK/PD Calibration (NumPy/SciPy)
- Supports 1-/2-compartment models with log-normal priors per parameter.
- Covariate effects: linear/multiplicative (`eta = X * beta`), interactions optional.
- Adaptive dosing hooks with built-in policies: `fixed`, `exposure_target`, `toxicity_constrained`.
- Artifacts: `pkpd_calibration.json` (params, AUC/Cmax, diagnostics). Provide config via `--pkpd-config` and optional observations via `--pkpd-observations`.

Example config (YAML/JSON):
```yaml
pkpd:
  model: "two_compartment"
  priors:
    CL: { mu: 2.0, sigma: 0.4 }
    Vc: { mu: 3.5, sigma: 0.3 }
  covariance:
    use_off_diagonal: true
  covariates:
    cl:
      betas: { weight: 0.01, renal_impairment: -0.2 }
      interactions:
        weight*sex: 0.05
```

CLI:
```
python src/zeropain_pipeline.py --pkpd-config pkpd_config.yaml --pkpd-observations obs.json --optimize --compounds SR-17018
```

## Tolerance & Withdrawal
- Pluggable models (`tolerance_models.py`): linear, sigmoid (ceiling), lagged/hysteresis.
- Config keys:
```yaml
tolerance:
  model: sigmoid
  max_factor: 3.0
  half_life_days: 14
  withdrawal:
    onset_delay_days: 2
    severity_scale: 1.0
```
- Simulation path attaches a lightweight tolerance projection (`tolerance_projection`) to results when `--tolerance-config` is provided.

## Scenarios & Cohorts
- Templates: `perioperative`, `chronic`, `breakthrough` (see `scenarios.py`).
- Cohort spec parser (`--cohort`):
  - Example: `n=200,age=60±10,renal=0.3,hepatic=0.1,seed=42`
- Scenario run:
```
python src/zeropain_pipeline.py --simulate --compounds Morphine --scenario perioperative --cohort "n=200,age=60±10,renal=0.2"
```
- Cohort generator yields `PatientGenerationConfig` with stratified comorbidities and seeded sampling.

## Artifacts & Metadata
- Calibration: `pkpd_calibration.json`
- Simulation: includes `tolerance_projection` when tolerance config provided; metadata records scenario/cohort.

## Tests
- `tests/test_modeling.py` covers PK/PD calibration sanity, tolerance monotonicity, and cohort generator outputs.

