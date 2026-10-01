# Exploratory ZEROPAIN dose response

Device: NVIDIA L40S; 22,400,000 virtual patients across 16 dose pairs and 14 profiles; runtime 227.1s.

Doses are model inputs in mg per administration, twice daily. They are not recommended human doses. The PK/PD equations and response thresholds remain uncalibrated; receptor concentration units require correction before clinical interpretation. Equal profile weighting is an experimental design.

Headroom screen: standard-profile p90 peak MOR occupancy <=80% and p50 last-day trough free MOR fraction >=20%. These are exploratory cutoffs.

| SR-16435 | Buprenorphine | N | Standard pain p50 | Standard analgesia criterion | Standard peak MOR occupancy p90 | Standard trough free MOR p50 | Headroom screen | Pooled mortality criterion |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 0.00 | 0.00 | 1,400,000 | 5.79 | 0.000% | 0.0% | 100.0% | yes | 18.52% |
| 0.00 | 0.25 | 1,400,000 | 4.76 | 0.000% | 95.3% | 11.5% | no | 32.81% |
| 0.00 | 0.50 | 1,400,000 | 4.72 | 0.000% | 97.6% | 6.1% | no | 34.69% |
| 0.00 | 1.00 | 1,400,000 | 4.69 | 0.000% | 98.7% | 3.1% | no | 35.40% |
| 1.25 | 0.00 | 1,400,000 | 0.00 | 96.011% | 89.4% | 27.1% | no | 18.52% |
| 1.25 | 0.25 | 1,400,000 | 3.45 | 0.003% | 96.6% | 8.7% | no | 27.70% |
| 1.25 | 0.50 | 1,400,000 | 4.01 | 0.000% | 98.0% | 5.2% | no | 31.08% |
| 1.25 | 1.00 | 1,400,000 | 4.32 | 0.000% | 98.9% | 2.9% | no | 33.78% |
| 2.50 | 0.00 | 1,400,000 | 0.00 | 96.323% | 94.4% | 15.7% | no | 18.49% |
| 2.50 | 0.25 | 1,400,000 | 2.54 | 0.077% | 97.4% | 7.0% | no | 25.01% |
| 2.50 | 0.50 | 1,400,000 | 3.43 | 0.001% | 98.3% | 4.5% | no | 28.77% |
| 2.50 | 1.00 | 1,400,000 | 3.98 | 0.000% | 98.9% | 2.7% | no | 31.87% |
| 5.00 | 0.00 | 1,400,000 | 0.00 | 96.448% | 97.1% | 8.5% | no | 18.43% |
| 5.00 | 0.25 | 1,400,000 | 1.47 | 1.585% | 98.2% | 5.1% | no | 22.17% |
| 5.00 | 0.50 | 1,400,000 | 2.53 | 0.025% | 98.6% | 3.6% | no | 25.70% |
| 5.00 | 1.00 | 1,400,000 | 3.40 | 0.000% | 99.1% | 2.3% | no | 29.26% |

The occupancy measure includes all MOR-binding compounds in the model. High-risk street-exposure profiles can saturate receptors independently of the two administered components. Patient-level outcomes are not persisted.
