#!/usr/bin/env bash
set -euo pipefail
task_dir="$(mktemp -d)"
tar -xzf "${ASSET_CODE}" -C "${task_dir}"
cd "${task_dir}"
if [[ "${1:-}" == "--smoke" ]]; then
    python run_mixed_population.py --smoke --device cpu --compounds SR-16435 SR-14968 Buprenorphine --doses 2.0 1.5 0.25 --frequencies 2.0 2.0 2.0 --output-dir "${task_dir}/smoke"
else
    python run_mixed_population.py --seconds 600 --max-patients 1000000000 --max-batch 500000 --compounds SR-16435 SR-14968 Buprenorphine --doses 2.0 1.5 0.25 --frequencies 2.0 2.0 2.0 --output-dir "${HARNESS_OUTPUT_ROOT}/${HARNESS_RUN_ID}"
fi


