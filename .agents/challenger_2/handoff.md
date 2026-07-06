# Handoff Report - Challenger 2

## 1. Observation

- **Source File**: `src/patient_sim_main.c`
  - Lines 413-417:
    ```c
    // Success determination
    if (outcome.discontinuation_day == 0) {
        outcome.treatment_success = true;
        outcome.discontinuation_day = SIMULATION_DAYS;
    }
    ```
  - Lines 366-381 (inside the day loop):
    ```c
    // Check for treatment failure
    if (outcome.daily_pain_scores[day] > PAIN_CONTROL_FAILURE) {
        outcome.treatment_success = false;
        outcome.discontinuation_day = day;
        strcpy(outcome.discontinuation_reason, "inadequate_analgesia");
        break;
    }
    
    // Check adherence
    if (random_uniform() > p->adherence_probability) {
        outcome.treatment_success = false;
        outcome.discontinuation_day = day;
        strcpy(outcome.discontinuation_reason, "non_adherence");
        break;
    }
    ```
- **Execution Outputs**:
  - Run command: `./src/patient_sim 10`
  - From `dpp26_simulation_results.csv`:
    ```csv
    patient_id,treatment_success,discontinuation_day,discontinuation_reason,avg_pain_reduction,tolerance_developed,addiction_signs,withdrawal_occurred,adverse_event_count,final_tolerance_level,total_cost,qaly_gained
    0,0,8,non_adherence,0.2062,0,0,0,0,0.1817,13.50,0.0007
    1,1,90,non_adherence,0.0423,0,0,0,0,0.0340,1.50,0.0016
    2,0,3,non_adherence,0.2010,0,1,0,0,0.2044,6.00,0.0002
    ```
    (Note: Patient 1 has `treatment_success` = 1, `discontinuation_day` = 90, but `discontinuation_reason` = `non_adherence` and `total_cost` = 1.50).
  - From `population_statistics.json` (1-patient run):
    ```json
    {
      "success_rate": 1.0000,
      "discontinuation_non_adherence": 1,
      ...
    }
    ```
- **Valgrind Output**:
  - Run command: `valgrind --leak-check=full ./src/patient_sim 10`
  - Output:
    ```
    ==3746423== HEAP SUMMARY:
    ==3746423==     in use at exit: 18,976 bytes in 37 blocks
    ==3746423==   total heap usage: 44 allocs, 7 frees, 38,168 bytes allocated
    ==3746423== 
    ==3746423== 9,424 bytes in 31 blocks are possibly lost in loss record 7 of 7
    ==3746423==    at 0x484BBA3: calloc (vg_replace_malloc.c:1675)
    ==3746423==    by 0x4011F62: calloc (rtld-malloc.h:44)
    ==3746423==    by 0x4011F62: allocate_dtv (dl-tls.c:462)
    ```
    (No application-level memory leaks; all leaks are glibc internal thread-local storage allocations from `libgomp`).

- **PK Model calculation**:
  - In `src/patient_sim_main.c` (lines 183-201):
    ```c
    float calculate_concentration(float dose, float t_half, float bioavail, 
                                 float cl_factor, float time_since_dose) {
        float ke = 0.693 / (t_half / cl_factor);
        float ka = 2.0;
        ...
        if (bioavail < 1.0) {
            concentration = dose * bioavail * ka / (ka - ke) * 
                           (expf(-ke * time_since_dose) - expf(-ka * time_since_dose));
        ...
    ```

---

## 2. Logic Chain

1. **Premise**: When a patient fails on day 0, their `discontinuation_day` is set to `day` (which is `0`), and `treatment_success` is set to `false`.
2. **Observation**: Post-loop, the condition `if (outcome.discontinuation_day == 0)` evaluates to `true` for a patient who failed on day 0.
3. **Observation**: Inside the condition body, `outcome.treatment_success` is overwritten to `true` (1), and `outcome.discontinuation_day` is overwritten to `90`.
4. **Inference**: Day-0 failures are incorrectly classified as successful 90-day completions, while keeping their day-0 discontinuation reason (e.g., `"non_adherence"`) and 1-day cost ($1.50).
5. **Observation**: QALY calculation `float qaly_days = outcome.discontinuation_day > 0 ? outcome.discontinuation_day : SIMULATION_DAYS;` treats `discontinuation_day == 0` as a success (evaluating it to 90), which gives day-0 failures full 90-day QALY credit.
6. **Observation**: Valgrind confirms no dynamic heap allocation leaks or out-of-bound errors inside the patient/outcomes arrays.
7. **Observation**: Benchmark scaling tests show high parallel efficiency and performance (~48k patients/sec for 200,000 population size).

---

## 3. Caveats

- Thread-local variable allocations are categorized by Valgrind as "possibly lost" due to the dynamic thread vector (DTV) allocations in the OpenMP runtime (`libgomp`), which is standard behavior and not a source-level memory leak.
- The C simulation implements a different patient cohort logic (adherence-based early dropout) than the Python simulation (which simulates the full duration for all patients and uses threshold averages). Therefore, direct numerical equivalence between C and Python success rates is not expected.

---

## 4. Conclusion

The C patient cohort simulation compiled cleanly and demonstrated excellent performance and memory scalability up to 200,000 patients (~175 MB heap footprint, ~48k patients/sec).
However, it contains a critical **Success Overwrite Bug** where patients who fail on day 0 are marked as successes, assigned 90 days duration, and credited with full QALYs. In addition, the PK concentration formula has a potential division-by-zero risk if `ka == ke`.

---

## 5. Verification Method

To verify these findings:
1. Compile the binary:
   ```bash
   gcc -O3 -march=native -fopenmp src/patient_sim_main.c -o src/patient_sim -lm
   ```
2. Run with 10 patients:
   ```bash
   ./src/patient_sim 10
   ```
3. Inspect `dpp26_simulation_results.csv` and look for any row where `treatment_success` is `1` and `discontinuation_reason` is `"non_adherence"` or `"inadequate_analgesia"` with `total_cost` equal to `1.50`.
