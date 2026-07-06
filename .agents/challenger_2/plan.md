# Verification and Stress Test Plan

## Objective
Verify the safety, scalability, and boundary limits of the C patient cohort simulation.

## Verifiable Steps

### Step 1: Compilation Verification
- Propose and run the native compilation command:
  `gcc -Wall -Wextra -O3 -march=native -fopenmp src/patient_sim_main.c -o src/patient_sim -lm`
- Verify clean compilation (no warnings or errors).

### Step 2: Boundary Value Testing
- Run the simulation with 0 patients:
  `./src/patient_sim 0`
  Verify that the binary falls back to 100,000 patients or exits cleanly.
- Run the simulation with 1 patient:
  `./src/patient_sim 1`
  Verify execution correctness and that CSV and JSON outputs are created.
- Run the simulation with 10 patients:
  `./src/patient_sim 10`
  Verify correctness, check success/discontinuation mapping.
- Run the simulation with 200,000 patients:
  `./src/patient_sim 200000`
  Benchmark execution time and throughput.

### Step 3: Memory and Resource Leak Analysis
- Execute under Valgrind:
  `valgrind --leak-check=full ./src/patient_sim 10`
- Check for memory leaks, invalid accesses, and other heap management errors.

### Step 4: Logic Bug and Output Verification
- Inspect the output files `dpp26_simulation_results.csv` and `population_statistics.json` to verify consistency of outcomes.
- Check if day-0 discontinuation incorrectly sets `treatment_success = 1` and `discontinuation_day = 90` while cost is $1.50 (1 day).
