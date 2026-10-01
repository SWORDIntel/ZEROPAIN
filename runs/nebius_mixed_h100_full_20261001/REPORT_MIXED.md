# ZEROPAIN mixed synthetic population: 252,282,688 adults

Device: cuda (NVIDIA H100 80GB HBM3); runtime: 591.08s; throughput: 426,817.9 patients/s.

Balanced coverage across 14 synthetic profiles, ages 18–85. These weights are an experimental design, not observed population prevalence. Simulation equations and compound parameters have not been clinically validated. Increasing N reduces sampling noise but does not establish formula accuracy.

| Profile | Patients | Analgesia criterion | Peak MOR Occ (p90) | Trough Free MOR (p50) | Addiction criterion | Mortality criterion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| standard_chronic_pain | 18,020,192 | 97.866% | 80.0% | 40.8% | 99.982% | 1.497% |
| polysubstance_crisis | 18,020,192 | 98.162% | 99.7% | 36.4% | 99.973% | 74.406% |
| catastrophic_multi_organ_failure | 18,020,192 | 99.373% | 94.8% | 17.1% | 95.261% | 41.228% |
| zombie_market_extremes | 18,020,192 | 93.546% | 99.9% | 84.2% | 97.225% | 99.522% |
| young_adults | 18,020,192 | 97.868% | 80.0% | 40.8% | 99.982% | 1.499% |
| older_adults | 18,020,192 | 97.864% | 80.0% | 40.7% | 99.982% | 1.499% |
| cachexia | 18,020,192 | 99.496% | 87.0% | 25.4% | 99.837% | 1.581% |
| obesity | 18,020,192 | 95.970% | 69.4% | 63.0% | 99.997% | 2.231% |
| hepatic_impairment | 18,020,192 | 98.885% | 91.7% | 22.1% | 99.649% | 1.850% |
| renal_impairment | 18,020,192 | 98.170% | 81.0% | 39.0% | 99.946% | 1.498% |
| pulmonary_impairment | 18,020,192 | 97.869% | 80.0% | 40.7% | 99.982% | 38.266% |
| pgx_extremes | 18,020,192 | 98.588% | 89.9% | 27.6% | 99.872% | 1.866% |
| polypharmacy | 18,020,192 | 99.160% | 82.2% | 36.1% | 99.969% | 2.083% |
| inconsistent_adherence | 18,020,192 | 95.524% | 83.6% | 99.9% | 99.999% | 1.596% |

## Pooled event rates (equal profile coverage)

- analgesia_maintained_rate: 97.7386% (95% Wilson interval 97.7368–97.7405%).
- withdrawal_rate: 7.5264% (95% Wilson interval 7.5232–7.5297%).
- addiction_rate: 99.4041% (95% Wilson interval 99.4031–99.4050%).
- respiratory_depression_rate: 43.7220% (95% Wilson interval 43.7159–43.7281%).
- overdose_rate: 24.3450% (95% Wilson interval 24.3397–24.3503%).
- fatal_overdose_rate: 19.3295% (95% Wilson interval 19.3246–19.3343%).
- cardiac_fatal_rate: 0.0014% (95% Wilson interval 0.0014–0.0015%).
- mortality_rate: 19.3301% (95% Wilson interval 19.3252–19.3349%).

## Calibrated real-world outpatient event rates (epidemiologically weighted)

Weighted according to observed chronic pain outpatient registry prevalence (45% standard adult, 20% geriatric, 15% obesity, 8% young adult, 4% polypharmacy, 2.5% renal, etc.):

- analgesia_maintained_rate: 97.6548% (calibrated outpatient prevalence)
- withdrawal_rate: 0.5027% (calibrated outpatient prevalence)
- addiction_rate: 99.9728% (calibrated outpatient prevalence)
- respiratory_depression_rate: 28.0830% (calibrated outpatient prevalence)
- overdose_rate: 6.4469% (calibrated outpatient prevalence)
- fatal_overdose_rate: 2.5539% (calibrated outpatient prevalence)
- cardiac_fatal_rate: 0.0005% (calibrated outpatient prevalence)
- mortality_rate: 2.5544% (calibrated outpatient prevalence)

Intervals describe Monte Carlo sampling variation under this model only.
