# Adversarial Review of C Patient Cohort Simulation

## Challenge Summary

**Overall risk assessment**: HIGH

The C patient cohort simulation exhibits significant logic bugs, boundary vulnerabilities, and scalability/concurrency constraints. Most notably, a critical logic bug in the success determination path incorrectly classifies all first-day (day 0) treatment failures (such as early non-adherence or early pain-control failure) as 100% successful treatments with 90 days of duration and full QALY credit.

---

## Challenges

### [Critical] Challenge 1: Day-0 Discontinuation Success Overwrite Bug
- **Assumption challenged**: The simulation assumes that `discontinuation_day == 0` uniquely represents patients who completed the entire 90-day simulation without early discontinuation.
- **Attack scenario**: When a patient fails/discontinues on the very first day (`day == 0`), their `discontinuation_day` is set to `0`. Post-loop, the program checks `if (outcome.discontinuation_day == 0)` and incorrectly overwrites `treatment_success` to `true` (1), and resets `discontinuation_day` to `SIMULATION_DAYS` (90), giving them full QALY credit.
- **Blast radius**: Heavily distorts clinical outcomes, inflating the success rate and QALY gains while underestimating the discontinuation rates. A patient who discontinues on day 0 will cost $1.50 but count as a 90-day success.
- **Mitigation**: Initialize `discontinuation_day = -1` or maintain a separate boolean flag (e.g., `completed_treatment`) to indicate success, rather than overloading `0` to mean both "failed on day 0" and "succeeded for 90 days".

### [High] Challenge 2: QALY Calculation Loophole for Day-0 Failures
- **Assumption challenged**: The expression `float qaly_days = outcome.discontinuation_day > 0 ? outcome.discontinuation_day : SIMULATION_DAYS;` assumes that any patient with `discontinuation_day == 0` completed the full simulation.
- **Attack scenario**: For any patient who genuinely discontinued on day 0, `discontinuation_day` is `0`, which makes `outcome.discontinuation_day > 0` evaluate to `false`. They are assigned `qaly_days = 90`, receiving full QALY credit for 90 days despite failing on day 0.
- **Blast radius**: Artificially inflates the average QALYs gained for the simulated population.
- **Mitigation**: Track the actual number of days completed using a separate variable or check `outcome.treatment_success` to determine `qaly_days`.

### [Medium] Challenge 3: PK Model Division-by-Zero (ka == ke) Vulnerability
- **Assumption challenged**: The PK clearance factor and compound half-life will never result in the elimination rate constant `ke` equaling the absorption rate constant `ka = 2.0`.
- **Attack scenario**: If a new compound with a short half-life (e.g., `t_half = 0.5`) is simulated, or the clearance factor bounds are widened, the elimination constant `ke` can equal `2.0`. When `ke == ka`, the expression `ka / (ka - ke)` causes a division-by-zero, resulting in `NaN` concentration.
- **Blast radius**: Complete simulation failure or corruption of calculations (NaN propagation) for short half-life compounds.
- **Mitigation**: Add a small epsilon check to prevent division by zero, or use L'Hôpital's rule limit when `ka` is extremely close to `ke`.

### [Medium] Challenge 4: OpenMP Fixed Batch Size Scalability Limit
- **Assumption challenged**: The fixed batch size of 256 is efficient for all population sizes.
- **Attack scenario**: In `simulate_population_parallel`, the OpenMP schedule is set to `dynamic, BATCH_SIZE` (where `BATCH_SIZE` is 256). If the user runs the simulation with fewer than 256 patients (e.g., 10 patients), the entire population is processed by a single chunk on a single thread, bypassing parallel execution entirely.
- **Blast radius**: Complete loss of parallel speedup for small-to-medium cohorts, leading to poor CPU utilization on multi-core systems.
- **Mitigation**: Scale the batch size dynamically based on the population count and the number of available threads (e.g., `max(1, n_patients / (num_threads * 4))`).

### [Low] Challenge 5: Weak Random Seeding and Non-reproducibility
- **Assumption challenged**: `time(NULL) ^ omp_get_thread_num()` provides sufficient entropy and uniqueness for thread seeding.
- **Attack scenario**: If the program is run multiple times within the same second, the seeds across runs will be identical, producing identical random trajectories and patient characteristics. Additionally, threads initializing at the same time will have highly correlated seeds (differing only by thread ID).
- **Blast radius**: Inability to run independent parallel Monte Carlo trials in rapid succession.
- **Mitigation**: Seed using a high-resolution timer (e.g., `clock_gettime` or `omp_get_wtime()`) or read from `/dev/urandom`.

---

## Stress Test Results

- **Scenario: 0 Patients** → Fallback to 100,000 patients due to `atoi` parsing checks (`parsed > 0`) → Program runs 100,000 patients successfully → **PASS** (Safe fallback, though unable to run 0 cohort size).
- **Scenario: 1 Patient** → Runs cleanly on a single thread. Output files successfully written → **PASS** (Functional).
- **Scenario: 10 Patients** → Runs cleanly. Reveals logic bug where patients failing on day 0 are classified as successes → **FAIL** (Incorrect outcomes classification).
- **Scenario: 200,000 Patients** → Runs successfully. Memory usage (~175 MB) and throughput (~48k patients/sec) scale linearly → **PASS** (High performance).

---

## Unchallenged Areas

- **Pluggable progression models integration** — The C simulation uses a hardcoded receptor and PK/PD model inside `patient_sim_main.c` rather than loading pluggable models from python's `tolerance_models.py` directly. This is treated as a known architecture limitation.
