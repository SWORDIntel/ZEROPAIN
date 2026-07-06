# BRIEFING — 2026-07-06T10:57:00+01:00

## Mission
Implement the fix for the failing native test in test_auto_backend.c to stabilize KEYSTONE auto-routing backend and ZEROPAIN integration.

## 🔒 My Identity
- Archetype: worker_1
- Roles: implementer, qa, specialist
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/worker_1
- Original parent: 24533436-ee82-47cd-99ee-26081df67a85
- Milestone: Implementation of Routing Fix

## 🔒 Key Constraints
- Code-only network mode (no external curl/wget/lynx or web access).
- No cheat mandate (no hardcoded test results, facade implementations).
- Scale testing (run test_auto_backend in a 50x loop).
- Ensure correctness of both KEYSTONE and ZEROPAIN test suites.

## Current Parent
- Conversation ID: 24533436-ee82-47cd-99ee-26081df67a85
- Updated: not yet

## Task Summary
- **What to build**: 
  - Fix router bypass in `third_party/KEYSTONE/src/keystone.c`: check `keystone_fortran_backend_available()` before bypassing the scalar fast path when `num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` in `keystone_search_batch_auto` and `keystone_static_auto_backend`.
  - Fix timing noise/flaky assertions in `third_party/KEYSTONE/src/keystone.c` around line 1887 (Option A) and relax the assertions in `third_party/KEYSTONE/tests/test_auto_backend.c` lines 148 and 448 (Option B).
- **Success criteria**:
  - `make clean check KEYSTONE_ENABLE_CUDA=0` passes in `third_party/KEYSTONE`.
  - `for i in {1..50}; do ./bin/test_auto_backend || exit 1; done` passes.
  - `pytest` passes in ZEROPAIN root.
- **Interface contracts**: /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/PROJECT.md
- **Code layout**: KEYSTONE sources in `third_party/KEYSTONE/src/`, tests in `third_party/KEYSTONE/tests/`.

## Key Decisions Made
- Implemented BOTH Option A (capping p95 measurements below estimated_ns_per_key) and Option B (relaxing test assertions in test_auto_backend.c to checking for >= 0.0) as requested for maximum robustness under CPU jitter.
- Avoided bypassing scalar fast path for dense-sorted inputs when Fortran backend is unavailable.
- Fixed a compatibility bug in `src/pkpd_calibration.py` where `np.trapezoid` was used but failed because the current environment uses NumPy < 2.0.0 (which has `np.trapz` instead). Created a robust fallback that resolves the issue dynamically on any NumPy version.

## Artifact Index
- `/fast/Main Workspace/ZEROPAIN/.agents/worker_1/handoff.md` — Final handoff report containing findings, code modifications, and verification details.

## Change Tracker
- **Files modified**:
  - `third_party/KEYSTONE/src/keystone.c`: Added `keystone_fortran_backend_available()` check to routing/bypass decisions, and clamp `cached_p95_ns_per_key` to at least `estimated_ns_per_key`.
  - `third_party/KEYSTONE/tests/test_auto_backend.c`: Relaxed flaky timing assertions at lines 148 and 448 to check `p95_ns_per_key >= 0.0`.
  - `src/pkpd_calibration.py`: Fixed NumPy 2.0 compatibility fallback for trapezoidal integration.
- **Build status**: pass
- **Pending issues**: none

## Quality Status
- **Build/test result**: pass
- **Lint status**: 0 outstanding violations
- **Tests added/modified**: modified `third_party/KEYSTONE/tests/test_auto_backend.c`

## Loaded Skills
- **Source**: none
- **Local copy**: none
- **Core methodology**: none
