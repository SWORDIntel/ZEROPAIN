## 2026-07-06T11:27:43Z

<USER_REQUEST>
You are the Worker Core Implementation (teamwork_preview_worker).
Your working directory is `/fast/Main Workspace/ZEROPAIN/.agents/worker_core_impl_gen2`.
You must run in the main repository directory: `/fast/Main Workspace/ZEROPAIN`.
Your task is to apply fixes and enhancements based on the Quality Review and Challenger reports:

1. Python Integration & Wiring Gaps:
   - In `src/zeropain_pipeline.py` (under `ZeroPainPipeline.run_simulation`), pass `tolerance_config=tolerance_config` to `simulation.run_simulation(...)`.
   - In `src/dsmil_adapter.py` (under `process_request`), extract `tolerance_config = payload.get('tolerance_config', {})`. Validate that it is a dictionary (fallback to `{}` if not, to avoid TypeError/AttributeError crashes) and pass it to `sim.run_simulation(..., tolerance_config=tolerance_config)`.
   - In `src/zeropain_tui.py` (under `simulation_menu`), package the user-selected TUI parameters (`self.tolerance_model_type`, `self.tolerance_slope`, `self.addiction_model_type`, `self.addiction_slope`) into a config dictionary and pass it as `tolerance_config` to `simulation.run_simulation(...)`.

2. Stress Test Safeguards (Python Math):
   - In `src/patient_simulation.py` (inside `simulate_patient` where half-life is computed): validate and clamp `pathway_sum = sum(pathway_ratio * patient_cyp_activity)` to ensure it is not zero or negative. Clamp it to a minimum of `1e-3` to prevent division-by-zero or negative half-life. Ensure `adjusted_t_half` has a minimum value (e.g. `0.1` hours).
   - In `src/opioid_analysis_tools.py` (inside `calculate_receptor_occupancy`): if `ki` is 0.0 or extremely close to 0, clamp it to a minimum of `1e-5` to prevent `0/0` NaN occupancy.

3. C Correctness Flaws & Parallel Tuning (`src/patient_sim_main.c` / `src/patient_sim.h`):
   - **Sentinel for Discontinuation**: Initialize `outcome.discontinuation_day = -1;` (instead of `0` in `{0}`) inside `simulate_patient_treatment`.
   - **Success Overwrite**: Update the final success determination block to check:
     ```c
     if (outcome.discontinuation_day == -1) {
         outcome.treatment_success = true;
         outcome.discontinuation_day = SIMULATION_DAYS;
     }
     ```
   - **QALY Calculation Loophole**: Correct the QALY days calculation using:
     ```c
     float qaly_days = (outcome.discontinuation_day == -1) ? SIMULATION_DAYS : outcome.discontinuation_day;
     ```
   - **Average Pain Score Deflation**: Inside `simulate_patient_treatment`, when a break happens (due to inadequate analgesia, non-adherence, or trial failure), fill all remaining days in the `daily_pain_scores` array (from `day + 1` to `SIMULATION_DAYS`) with the patient's `p->baseline_pain_score` so that early dropouts correctly reflect their return to baseline pain.
   - **PK Division-by-Zero**: Inside `calculate_concentration` in `src/patient_sim_main.c`, check for `fabsf(ka - ke) < 1e-4f`. If it is close, compute concentration using the limiting form:
     ```c
     concentration = dose * bioavail * ka * time_since_dose * expf(-ka * time_since_dose);
     ```
     Otherwise, compute concentration using the standard formula.
   - **OpenMP Parallelization Bottleneck**: Change the OpenMP chunk size from the static macro `BATCH_SIZE` to a runtime expression dynamically calculated:
     ```c
     int chunk_size = n_patients / (max_threads * 4);
     if (chunk_size < 1) chunk_size = 1;
     if (chunk_size > 256) chunk_size = 256;
     ```
     And use `#pragma omp parallel for schedule(dynamic, chunk_size)` in the parallel loops in `src/patient_sim_main.c`.

4. Verification:
   - Run `pytest` to execute all unit tests and verify they pass cleanly.
   - Compile and execute the C simulation binary with different patient counts (e.g. `./src/patient_sim 5000`) and verify correctness of statistics.
   - Run the native KEYSTONE tests: `third_party/KEYSTONE/bin/test_core_native` and `third_party/KEYSTONE/bin/test_auto_backend`.
   - Document all changes and verification outputs in `handoff.md` and report back.

MANDATORY INTEGRITY WARNING — include this verbatim:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.
</USER_REQUEST>
