# Nebius mixed-population simulation roadmap

## Completed

- [x] Define 14 synthetic adult profiles covering the original four cohorts, age, body composition, organ impairment, genetics, polypharmacy, and adherence.
- [x] Run a five-minute L40S scale trial with a guarded cloud budget, retrieve results, and tear down compute. The run simulated 52,612,672 virtual patients in 291.8 seconds.
- [x] Reconcile and download 16-pair dose-response grid run (`ef10aab...`, 22,400,000 patients on L40S) into `runs/nebius_dose_grid_l40s_20261001`.
- [x] Recalibrate PK/PD biophase calculations (incorporating plasma protein binding $f_u$, physiological volume of distribution $V_d$, and molar unit conversions) to reflect clinical human pill dosing.
- [x] Lock in Tri-Vector Architecture documentation (`doc/clinical_dosages.md` and `doc/protocol_justification.md`): SR-14968 tolerance inversion, SR-16435 NOP anti-abuse clamping, outpatient 30.9% accident headroom with Buprenorphine 0.5 mg BID, and Levorphanol quad-action oncology protocol.
- [x] Stage, execute, and retrieve results for 5-minute recalibrated NVIDIA L40S simulation (`aijob-e00q5g3y0gz3herj1d`, 38,612,672 virtual patients in 279.0s). Confirmed 97.74% pooled analgesia maintenance and 40.7%–40.8% trough free MOR headroom across standard chronic cohorts. Budget settled at $0.23.
- [x] Commit and push full codebase, calibrated biophase PK/PD engine, clinical dosing documentation, and empirical verification reports to remote repository (`origin/master`).

## Next Execution Milestone

- [ ] Prepare and launch 10-minute NVIDIA H100 SXM5 scale test run (600s, 500k batch chunking) on Nebius to evaluate throughput and stability under locked-in outpatient triplet (SR-16435 2.5 mg + SR-14968 20.0 mg + Buprenorphine 0.5 mg BID).

## Remaining before clinical interpretation

- [ ] Calibrate population weights and outcome distributions to observed clinical registry data. Equal profile coverage is for model stress testing, not an estimate of real-world prevalence.

The completed run establishes computational scale and exposes model behavior. Its clinical event rates remain unvalidated simulation outputs.
