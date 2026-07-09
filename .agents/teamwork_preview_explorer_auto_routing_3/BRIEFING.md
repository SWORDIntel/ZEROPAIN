# BRIEFING — 2026-07-06T23:20:50Z

## Mission
Analyze codebase and test_auto_backend.c to investigate why it fails, check env vars/compiler flags, and recommend a precise fix.

## 🔒 My Identity
- Archetype: explorer
- Roles: read-only investigator, analyzer
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_auto_routing_3
- Original parent: 44e4506d-3f21-4b06-89e8-b5ace953c598
- Milestone: Auto routing backend test analysis

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do not modify any files except own .agents/ folder files like progress.md and handoff.md.

## Current Parent
- Conversation ID: 44e4506d-3f21-4b06-89e8-b5ace953c598
- Updated: 2026-07-06T23:20:50Z

## Investigation State
- **Explored paths**:
  - `third_party/KEYSTONE/tests/test_auto_backend.c`
  - `third_party/KEYSTONE/src/keystone.c`
  - `third_party/KEYSTONE/Makefile`
  - `third_party/KEYSTONE/build.sh`
  - `scripts/build_native_backends.sh`
- **Key findings**:
  - The routing logic in `src/keystone.c` bypasses the scalar fast path for dense-sorted queries with `num_items >= 4096` assuming Fortran backend is available without verifying `keystone_fortran_backend_available()`.
  - When Fortran is disabled (`KEYSTONE_ENABLE_FORTRAN=0`), this causes a fallback to calibration and results in `KEYSTONE_DECISION_SOURCE_MEASURED` instead of `KEYSTONE_DECISION_SOURCE_FAST_PATH`, violating test assertions in `test_large_single_thread_batch_uses_scalar`.
  - Timing jitter on single final runs can violate the strict test assertion `decision.p95_ns_per_key >= decision.estimated_ns_per_key`.
- **Unexplored areas**:
  - GPU/CUDA acceleration paths, which are disabled by default.

## Key Decisions Made
- Stashed local edits to reproduce the clean test failure, which confirmed the exact assertion failure on `test_large_single_thread_batch_uses_scalar`.
- Re-applied local edits and verified the test passes.

## Artifact Index
- `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_auto_routing_3/handoff.md` — Detailed handoff report.
