# Easy Wins for ZEROPAIN Polish

A handful of quick, low-risk improvements to harden the current distributed pipeline, experiment tracking, and TUI without large refactors.

## 1) Ship curated population presets
* Add reusable presets (e.g., trauma-heavy, chronic pain clinic, balanced) to the population generator and expose them in `src/zeropain_tui.py` and `src/zeropain_pipeline.py`.
* Provide a `--preset` CLI flag and a TUI drop-down to auto-fill age/weight/comorbidity distributions while keeping manual overrides.
* Benefit: faster setup for common workflows and fewer invalid configurations.

## 2) Add a 60-second smoke test path
* Create a tiny "smoke" mode in `src/zeropain_pipeline.py` that runs a 50-patient batch end-to-end with the distributed runner fallback.
* Wire it into `scripts/` (e.g., `scripts/smoke.sh`) and CI as a pre-flight gate to catch regressions quickly.
* Benefit: immediate confidence before long runs; keeps Xen-based domU nodes from idling while waiting for failures.

## 3) Centralize input validation for population knobs
* Move validation of age/weight/comorbidity distributions and receptor-binding params into a shared helper (e.g., `src/opioid_analysis_tools.py::validate_population_config`).
* Surface errors in the TUI with friendly messages and default corrections, and reuse the same checks in the CLI.
* Benefit: fewer invalid jobs and cleaner logs; reduces support load.

## 4) Lightweight run registry CLI
* Extend `src/utils/experiment_tracking.py` with a `zeropain-runs` entry point to list, show, and tail metrics for recent runs (`runs/<run-id>/metrics.jsonl`).
* Add a TUI "Runs" panel that shells out to the same helper for consistency.
* Benefit: instant visibility into checkpoints/metrics without opening files manually.

## 5) Deterministic seeding and checkpoint stamps
* Thread a `seed` parameter through `src/pipeline/distributed_runner.py` and simulation entry points, defaulting to a run-scoped seed saved in `runs/<run-id>/run.json`.
* Include the seed and batch checkpoint timestamps in tracker metadata to simplify resume debugging.
* Benefit: reproducible results across Ray/Dask/local backends and clearer provenance when auditing runs.
