#!/usr/bin/env bash
set -euo pipefail
task_dir="$(mktemp -d)"
tar -xzf "${ASSET_CODE}" -C "${task_dir}"
cd "${task_dir}"
if [[ "${1:-}" == "--smoke" ]]; then
    python run_dose_grid.py --smoke --device cpu --output-dir "${task_dir}/smoke"
else
    python run_dose_grid.py --device cuda --n-per-profile 100000 \
        --output-dir "${HARNESS_OUTPUT_ROOT}/${HARNESS_RUN_ID}"
fi
