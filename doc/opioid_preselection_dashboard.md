# Opioid Compound Pre-Selection Dashboard

## Purpose
A dedicated, analysis-ready lineup of priority opioid compounds with harmonized metrics for addiction risk, patient/treatment success, tolerance buildup, and analgesic duration. Charts are tailored to receptor-specific behavior (MOR, DOR, KOR, NPFF) and G-protein vs. β-arrestin signaling to capture complex pathway interactions.

## Compound Lineup (analysis defaults)
The table is the canonical pre-selection roster; values are seeds/targets for simulations and dashboards.

| Compound        | Receptor Strategy                               | Analgesic Duration (h) | Addiction Risk (0-1, lower is safer) | Tolerance Slope (%/day) | Patient Success (% achieving ≥50% relief) | β-arrestin Ratio (target) | Notes |
|-----------------|--------------------------------------------------|------------------------|---------------------------------------|-------------------------|-------------------------------------------|---------------------------|-------|
| SR-17018        | MOR-biased, minimal β-arrestin                  | 8-12                   | 0.12                                  | 0.2                      | 78                                        | 0.02                      | Reverses tolerance in preclinical data; anchor for no-addiction runs. |
| SR-14968        | μ-biased with κ antagonism for respiratory safety| 10-16                  | 0.10                                  | 0.18                     | 80                                        | 0.05                      | Designed to flatten tolerance and suppress dysphoria/respiratory depression. |
| Buprenorphine   | Partial MOR agonist, κ antagonism               | 24-36                  | 0.08                                  | 0.1                      | 72                                        | 0.18                      | Ceiling effect reduces respiratory depression; maintenance-friendly. |
| Oliceridine     | MOR biased agonist                              | 2-4                    | 0.24                                  | 0.6                      | 65                                        | 0.33                      | Short-acting; monitor cumulative exposure and respiratory risk. |
| Tapentadol      | Weak MOR + NRI synergy                          | 4-6                    | 0.28                                  | 0.4                      | 60                                        | 0.42                      | Dual mechanism; lower μ load offsets tolerance but watch noradrenergic AEs. |
| PZM21           | MOR biased, low β-arrestin                      | 3-6                    | 0.16                                  | 0.2                      | 70                                        | 0.08                      | Computationally designed; good bias but bioavailability uncertainty. |
| Tramadol        | Prodrug MOR + SNRI                              | 6-8                    | 0.35                                  | 0.3                      | 58                                        | 0.50                      | Metabolite-driven efficacy; variability handled via cohort stratification. |
| OPID candidate  | MOR partial, κ-sparing, NPFF modulator          | 10-14                  | 0.10                                  | 0.15                     | 76                                        | 0.10                      | Designed for no-euphoria/no-withdrawal; NPFF modulation tempers reward. |

## Metric Definitions (dashboard schema)
- **Addiction Risk:** probability of reinforcement/withdrawal from cohort simulation; combine receptor bias, NPFF modulation, and reward-circuit surrogate signals.
- **Patient Success (Treatment Success):** % of simulated or real-world patients achieving ≥50% pain reduction without exceeding sedation/respiratory ceilings.
- **Tolerance Slope:** % decline in analgesic effect per day over the first 14 days; integrates receptor desensitization and β-arrestin engagement.
- **Analgesic Duration:** hours above therapeutic threshold per dose; computed from PK/PD curves with receptor engagement overlap (MOR/DOR/KOR/NPFF).
- **Receptor Bias Metrics:** G-protein vs β-arrestin ratios per receptor subtype; flagged if κ agonism increases dysphoria or if DOR overactivation elevates seizure risk.

## Chart Pack (recommended views)
- **Stacked bars:** addiction risk vs. patient success for each compound, colored by receptor bias.
- **Waterfall:** analgesic duration contribution by receptor (MOR/DOR/KOR/NPFF) to highlight cross-talk.
- **Line/area charts:** tolerance slope over 14/30/90 days with confidence bands; annotate β-arrestin excursions.
- **Sankey:** receptor engagement → signaling pathway (G-protein/β-arrestin) → clinical outcomes (analgesia, tolerance, AE).
- **Radar plots:** per-compound safety envelope (addiction risk, tolerance slope, sedation, respiratory probability, QT/QTc shift).
- **Cohort stratification bars:** success vs. comorbidities (COPD, hepatic impairment) and prior opioid exposure.

## Data Shapes for Dashboards
Use JSONL or Parquet; keep schema consistent with `metrics.jsonl` emitter.

```json
{
  "compound_id": "sr-17018",
  "run_id": "2024-08-15-r1",
  "analgesic_duration_h": 10.5,
  "addiction_risk": 0.12,
  "tolerance_slope_pct_per_day": 0.2,
  "patient_success_rate": 0.78,
  "receptor_bias": {"mor": 0.9, "dor": 0.1, "kor": 0.05, "npff": 0.15},
  "beta_arrestin_ratio": 0.02,
  "sedation_rate": 0.05,
  "respiratory_depression_prob": 0.01
}
```

## Integration Points
- **Pipeline defaults:** load this roster into the compound builder/browser as the pre-selected analysis set; tag runs with `preselection=true`.
- **Metrics service:** append the above schema to `metrics.jsonl` and expose to Prometheus for dashboard queries.
- **Simulation knobs:** enable receptor cross-talk toggles (κ antagonism, NPFF modulation) and re-run tolerance slopes when toggled.
- **Governance:** block promotion if addiction risk >0.2 or tolerance slope >0.3%/day for any pre-selection compound.

## Operational Notes
- Keep signatures (SHA-384) on the roster file and metrics exports; validate in dashboards before rendering charts.
- For Xen/OpenVINO targets, prefer CPU/iGPU friendly chart rendering; precompute aggregates when running in Ray/Dask.
- Document any clinician overrides (dose caps, receptor exclusions) with audit timestamps to preserve chain-of-custody.
