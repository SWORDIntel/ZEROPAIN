#!/usr/bin/env bash
# ==============================================================================
# ZEROPAIN 10,000,000 Patient Virtual Clinical Trial Runner
# ==============================================================================
# Orchestrates 4 mega-cohorts (2.5M each = 10,000,000 patients total):
#   - Cohort 1: Standard Adult Chronic Pain (N = 2,500,000)
#   - Cohort 2: Street Fentanyl + Tranq (Xylazine) + Nitazene Crisis (N = 2,500,000)
#   - Cohort 3: Catastrophic Multi-Organ Failure + Polypharmacy (N = 2,500,000)
#   - Cohort 4: The Ultimate 'Zombie Market' & Genetic Extremes (N = 2,500,000)
#
# Usage:
#   ./run_10m_simulations.sh [--test-mode] [--device cuda|cpu|auto] [--output-dir DIR]
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

TEST_MODE=""
DEVICE="auto"
OUTPUT_DIR="runs/10m_trial_$(date +%Y%m%d_%H%M%S)"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-mode)
            TEST_MODE="--test-mode"
            shift
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

echo "================================================================================"
echo "          LAUNCHING ZEROPAIN 10 MILLION PATIENT CLINICAL TRIAL                  "
echo "================================================================================"
echo "  Timestamp   : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "  Working Dir : ${SCRIPT_DIR}"
echo "  Device      : ${DEVICE}"
echo "  Output Dir  : ${OUTPUT_DIR}"
if [[ -n "${TEST_MODE}" ]]; then
    echo "  Mode        : TEST MODE (N = 1,000 per cohort, 4,000 total)"
else
    echo "  Mode        : FULL 10M RUN (N = 2,500,000 per cohort, 10,000,000 total)"
fi
echo "================================================================================"
echo ""

mkdir -p "${OUTPUT_DIR}"

CMD=(
    python3 run_10m_simulations.py
    --device "${DEVICE}"
    --output-dir "${OUTPUT_DIR}"
)

if [[ -n "${TEST_MODE}" ]]; then
    CMD+=("${TEST_MODE}")
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    CMD+=("${EXTRA_ARGS[@]}")
fi

echo "[*] Executing: ${CMD[*]}"
"${CMD[@]}"

echo ""
echo "================================================================================"
echo "  TRIAL COMPLETE"
echo "  Results JSON : ${OUTPUT_DIR}/results_10m.json"
echo "  Report MD    : ${OUTPUT_DIR}/REPORT_10M.md"
echo "================================================================================"
