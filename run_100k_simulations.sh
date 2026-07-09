#!/bin/bash
set -e

echo "Starting 100k Patient Broad Simulations..."

# 1. Standard Cohort
echo "Running Standard Cohort (100k)..."
python3 src/dsmil_adapter.py --simulate \
    --compounds SR-16435 Buprenorphine \
    --doses 2.49 0.5 \
    --frequencies 2 2 \
    --n-patients-sim 100000 \
    --duration-days 90 \
    --output results_standard_100k.json

# 2. Street Fentanyl Cohort
echo "Running Street Fentanyl Cohort (100k)..."
python3 src/dsmil_adapter.py --simulate \
    --compounds SR-16435 Buprenorphine \
    --doses 2.49 0.5 \
    --frequencies 2 2 \
    --n-patients-sim 100000 \
    --duration-days 90 \
    --high-tolerance-skew \
    --output results_fentanyl_100k.json

# 3. Absolute Worst-Case Cohort
echo "Running Absolute Worst-Case Cohort (100k)..."
python3 src/dsmil_adapter.py --simulate \
    --compounds SR-16435 Buprenorphine \
    --doses 2.49 0.5 \
    --frequencies 2 2 \
    --n-patients-sim 100000 \
    --duration-days 90 \
    --high-tolerance-skew \
    --elderly-skew \
    --liver-disease-rate 0.5 \
    --kidney-disease-rate 0.5 \
    --polypharmacy-rate 3.0 \
    --output results_worstcase_100k.json

echo "All 100k simulations completed successfully."
