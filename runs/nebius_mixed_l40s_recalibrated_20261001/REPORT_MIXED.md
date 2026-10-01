# ZEROPAIN mixed synthetic population: 38,612,672 adults

Device: cuda (NVIDIA L40S); runtime: 279.01s; throughput: 138,389.6 patients/s.

Balanced coverage across 14 synthetic profiles, ages 18–85. These weights are an experimental design, not observed population prevalence. Simulation equations and compound parameters have not been clinically validated. Increasing N reduces sampling noise but does not establish formula accuracy.

| Profile | Patients | Analgesia criterion | Peak MOR Occ (p90) | Trough Free MOR (p50) | Addiction criterion | Mortality criterion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| standard_chronic_pain | 2,758,048 | 97.860% | 80.0% | 40.7% | 99.981% | 1.499% |
| polysubstance_crisis | 2,758,048 | 98.165% | 99.7% | 36.4% | 99.971% | 74.413% |
| catastrophic_multi_organ_failure | 2,758,048 | 99.383% | 94.8% | 17.0% | 95.269% | 41.217% |
| zombie_market_extremes | 2,758,048 | 93.566% | 99.9% | 84.2% | 97.216% | 99.524% |
| young_adults | 2,758,048 | 97.866% | 80.0% | 40.7% | 99.983% | 1.514% |
| older_adults | 2,758,048 | 97.850% | 80.0% | 40.8% | 99.983% | 1.491% |
| cachexia | 2,758,048 | 99.503% | 87.0% | 25.4% | 99.836% | 1.579% |
| obesity | 2,758,048 | 95.969% | 69.5% | 63.0% | 99.996% | 2.225% |
| hepatic_impairment | 2,758,048 | 98.888% | 91.7% | 22.2% | 99.647% | 1.839% |
| renal_impairment | 2,758,048 | 98.168% | 81.1% | 39.0% | 99.947% | 1.502% |
| pulmonary_impairment | 2,758,048 | 97.870% | 80.0% | 40.8% | 99.981% | 38.258% |
| pgx_extremes | 2,758,048 | 98.587% | 89.9% | 27.6% | 99.873% | 1.860% |
| polypharmacy | 2,758,048 | 99.170% | 82.2% | 36.2% | 99.968% | 2.084% |
| inconsistent_adherence | 2,758,048 | 95.522% | 83.6% | 99.9% | 99.999% | 1.601% |

## Pooled event rates (equal profile coverage)

- analgesia_maintained_rate: 97.7406% (95% Wilson interval 97.7359–97.7453%).
- withdrawal_rate: 7.5256% (95% Wilson interval 7.5173–7.5339%).
- addiction_rate: 99.4037% (95% Wilson interval 99.4013–99.4061%).
- respiratory_depression_rate: 43.7168% (95% Wilson interval 43.7011–43.7324%).
- overdose_rate: 24.3448% (95% Wilson interval 24.3313–24.3584%).
- fatal_overdose_rate: 19.3283% (95% Wilson interval 19.3158–19.3407%).
- cardiac_fatal_rate: 0.0015% (95% Wilson interval 0.0014–0.0016%).
- mortality_rate: 19.3289% (95% Wilson interval 19.3165–19.3414%).

Intervals describe Monte Carlo sampling variation under this model only.
