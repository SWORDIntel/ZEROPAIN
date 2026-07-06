# Handoff Report - Progression Verification & PK/PD Pathways Stress Testing

## 1. Observation
We conducted systematic, empirical review and verification testing on the newly introduced Python progression models, PK/PD pathways, and DSMIL adapter. The following exact code locations, configurations, and behaviors were observed:

### A. DSMIL Adapter Payload Loss
* File: `src/dsmil_adapter.py`
* Observation: The CLI/TUI adapter parses a payload containing `tolerance_config` but does not pass it forward to `PopulationSimulation.run_simulation`.
* Lines 104-111 of `src/dsmil_adapter.py` show:
```python
    sim = PopulationSimulation(db)
    results = sim.run_simulation(
        protocol=protocol,
        n_patients=n_patients,
        duration_days=duration_days,
        seed=seed,
        generation_config=gen_cfg
    )
```
No `tolerance_config` is passed to `run_simulation`, even though `PopulationSimulation.run_simulation` accepts it as an optional parameter.

### B. Progression Slope Sensitivity
* Command: `pytest tests/test_progression_challenger.py -v -s`
* Results:
  - **Tolerance Slope Impact**: Under `LinearTolerance`, a low tolerance slope (`slope = 0.001`) yielded a **0.0%** tolerance rate, whereas a high tolerance slope (`slope = 0.1`) yielded a **100.0%** tolerance rate in a 30-day Oxycodone simulation.
  - **Addiction Slope Impact**: Under `LinearAddiction`, a low addiction slope (`slope = 0.0001`) yielded a **7.0%** addiction rate, whereas a high addiction slope (`slope = 0.5`) yielded a **100.0%** addiction rate in a 10-day Oxycodone simulation.
  - Verification: Changes in progression slopes produce correct, expected differences in outcomes.

### C. Metabolic Parameters and Clearance Rates
* Command: `pytest tests/test_progression_challenger.py -v -s`
* Results:
  - **Metabolism Impact**: A patient with hepatic impairment (`metabolism_rate = 0.4`, comorbidities: `["liver_disease"]`) had higher accumulated average side effects (**0.837**) than a normal patient with `metabolism_rate = 1.5` (**0.750**) when given identical protocol doses (15.0mg Oxycodone, 3x daily).
  - Verification: Lower metabolic clearance rates result in higher side effects.

### D. Invalid Configurations Handling
* File: `src/patient_simulation.py` (lines 408-414), `src/tolerance_models.py` (lines 94-114)
* Observation:
  - Passing a non-dictionary (e.g. string) to `tolerance_config` results in a crash (`AttributeError` or `TypeError`) during simulation.
  - Specifying an invalid model name (e.g., `"invalid_model_name"`) silently falls back to `SigmoidTolerance` (line 104 of `src/tolerance_models.py`).
  - Negative bounds (e.g. half-life, rise_tau, decay_tau) are handled gracefully by capping with a minimum of `1e-3` in `SigmoidTolerance` and `LaggedTolerance`.

---

## 2. Logic Chain
1. **DSMIL Adapter Gap**:
   - *Observation A* shows that the `dsmil_adapter` parses a structured JSON request but fails to pass `tolerance_config`.
   - *Test result (`test_dsmil_adapter_ignores_tolerance_config`)* verifies this: a payload with a low slope and a payload with a high slope produced identical tolerance rates (**0.000** for both), confirming that the adapter ignores the user's progression slopes completely.
2. **Progression Models Core Dynamics**:
   - *Observation B* shows that when tolerance and addiction slopes are updated, the corresponding rate indicators vary monotonically. This proves that the equations in `src/tolerance_models.py` function correctly under simulation.
3. **Metabolic Variability**:
   - *Observation C* shows that patient metabolic parameters (like CYP activity rate adjustments and comorbidity-driven rate multipliers) successfully modulate clearance rates, causing accumulation of the active compound and increasing the average side effect metrics.
4. **Crash on Bad Config**:
   - *Observation D* shows that if `tolerance_config` contains non-dictionary data, the code executes `.get()` on it and crashes immediately.

---

## 3. Caveats
- Tests were performed with 50 to 100 virtual patients. In large-scale production simulations (100k+ patients), minor numerical changes or stochastic edge cases could manifest.
- The addiction threshold model (`LinearAddiction`) uses dopamine surge above threshold. If the drug's properties do not exceed the threshold, the addiction progression will remain zero regardless of the slope.

---

## 4. Conclusion
- **The progression models and patient metabolic parameters are functionally correct and highly sensitive to slope changes.** They correctly reflect progression and clearance differences.
- **Critical Bug Found**: The DSMIL adapter (`src/dsmil_adapter.py`) neglects to forward `tolerance_config` to `run_simulation`. Any integration calling the simulation via the DSMIL adapter JSON payload will fail to use custom progression slope configurations.
- **Robustness Vulnerability**: The simulation crashes (rather than failing gracefully with a validation error) when an invalid type is passed as the tolerance configuration.

---

## 5. Verification Method
To independently run the tests and verify these findings, run:
```bash
pytest tests/test_progression_challenger.py -v -s
```

### Invalidation Conditions:
If the test `test_dsmil_adapter_ignores_tolerance_config` fails, it implies `dsmil_adapter.py` has been updated to forward `tolerance_config` to `run_simulation`.

---

## 6. Challenge Report (Adversarial Review)

**Overall risk assessment**: HIGH (due to silent configuration loss in the DSMIL adapter and crash-on-invalid-input vulnerabilities).

### Challenges

#### [High] Challenge 1: Silent Configuration Loss in DSMIL Adapter
- **Assumption challenged**: The DSMIL adapter properly supports the full patient simulation capabilities, including customizable progression profiles.
- **Attack scenario**: A user uploads a payload containing custom progression slopes (e.g. a higher addiction or tolerance slope) to simulate risk-prone patient cohorts. The system runs the simulation, but silently uses the default parameters, returning skewed/underestimated risk metrics to the clinician or researcher.
- **Blast radius**: Clinical validation of high-risk protocols is invalidated, leading to incorrect assessment of tolerance/addiction risks.
- **Mitigation**: Update `process_request` in `src/dsmil_adapter.py` to extract `tolerance_config = payload.get('tolerance_config', {})` and pass it to `sim.run_simulation(...)`.

#### [Medium] Challenge 2: Crash on Invalid Configuration Format
- **Assumption challenged**: Config inputs are validated and handled gracefully.
- **Attack scenario**: Passing a list, string, or corrupted JSON field in the `tolerance_config` API payload causes a raw Python exception (`AttributeError`) instead of returning a clear validation message.
- **Blast radius**: Downtime or unhandled internal server errors in the API simulation endpoint.
- **Mitigation**: Implement input schema validation (e.g. using Pydantic or type checking) on the `tolerance_config` dictionary before passing it to `simulate_patient`.
