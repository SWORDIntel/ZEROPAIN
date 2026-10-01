# ZEROPAIN mixed synthetic population: 99,999,998 adults

Device: cuda (NVIDIA H100 80GB HBM3); runtime: 290.55s; throughput: 344,180.6 patients/s.

Balanced coverage across 14 synthetic profiles, ages 18–85. These weights are an experimental design, not observed population prevalence. Simulation equations and compound parameters have not been clinically validated. Increasing N reduces sampling noise but does not establish formula accuracy.

| Profile | Patients | Analgesia criterion | Peak MOR Occ (p90) | Trough Free MOR (p50) | Addiction criterion | Mortality criterion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| standard_chronic_pain | 7,142,857 | 97.868% | 80.0% | 40.7% | 99.981% | 1.496% |
| polysubstance_crisis | 7,142,857 | 98.162% | 99.7% | 36.3% | 99.972% | 74.411% |
| catastrophic_multi_organ_failure | 7,142,857 | 99.376% | 94.8% | 17.1% | 95.263% | 41.220% |
| zombie_market_extremes | 7,142,857 | 93.552% | 99.9% | 84.2% | 97.222% | 99.525% |
| young_adults | 7,142,857 | 97.866% | 80.0% | 40.7% | 99.982% | 1.509% |
| older_adults | 7,142,857 | 97.863% | 80.0% | 40.8% | 99.983% | 1.496% |
| cachexia | 7,142,857 | 99.494% | 87.0% | 25.4% | 99.837% | 1.580% |
| obesity | 7,142,857 | 95.962% | 69.5% | 63.0% | 99.997% | 2.225% |
| hepatic_impairment | 7,142,857 | 98.885% | 91.7% | 22.1% | 99.649% | 1.850% |
| renal_impairment | 7,142,857 | 98.168% | 81.0% | 39.1% | 99.947% | 1.498% |
| pulmonary_impairment | 7,142,857 | 97.865% | 80.0% | 40.8% | 99.981% | 38.269% |
| pgx_extremes | 7,142,857 | 98.585% | 89.9% | 27.5% | 99.871% | 1.864% |
| polypharmacy | 7,142,857 | 99.162% | 82.3% | 36.2% | 99.969% | 2.089% |
| inconsistent_adherence | 7,142,857 | 95.519% | 83.5% | 99.9% | 99.999% | 1.593% |

## Pooled event rates (equal profile coverage)

- analgesia_maintained_rate: 97.7376% (95% Wilson interval 97.7347–97.7405%).
- withdrawal_rate: 7.5264% (95% Wilson interval 7.5212–7.5316%).
- addiction_rate: 99.4039% (95% Wilson interval 99.4024–99.4054%).
- respiratory_depression_rate: 43.7253% (95% Wilson interval 43.7156–43.7350%).
- overdose_rate: 24.3479% (95% Wilson interval 24.3395–24.3563%).
- fatal_overdose_rate: 19.3296% (95% Wilson interval 19.3219–19.3373%).
- cardiac_fatal_rate: 0.0015% (95% Wilson interval 0.0014–0.0015%).
- mortality_rate: 19.3302% (95% Wilson interval 19.3225–19.3380%).

Intervals describe Monte Carlo sampling variation under this model only.
