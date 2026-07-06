# BRIEFING — 2026-07-06T10:52:27+01:00

## Mission
Investigate KEYSTONE auto backend selector and analyze test_auto_backend failure.

## 🔒 My Identity
- Archetype: Explorer
- Roles: Explorer 3
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/explorer_3/
- Original parent: 24533436-ee82-47cd-99ee-26081df67a85
- Milestone: KEYSTONE Auto Backend Selector Investigation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Code-only network mode (no external services or HTTP requests)

## Current Parent
- Conversation ID: 24533436-ee82-47cd-99ee-26081df67a85
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `third_party/KEYSTONE/src/keystone.c`
  - `third_party/KEYSTONE/tests/test_auto_backend.c`
  - `third_party/KEYSTONE/fortran/keystone_batch.f90`
  - `third_party/KEYSTONE/tests/test_fortran_backend.c`
- **Key findings**:
  - Auto-backend router bypasses the scalar fast path when Fortran is unavailable, causing incorrect decision source.
  - Flaky performance assertions compare single run time with p95 calibration time and fail under CPU timing jitter.
  - Test binary fails to load `fortran/libkeystone_batch.so` dynamically unless CWD is set to `third_party/KEYSTONE`.
- **Unexplored areas**:
  - CUDA backend compilation and integration correctness (bypassed due to lack of `cuda_runtime.h` headers on host).

## Key Decisions Made
- Determined that both router check modification and test assertion relaxation are required for robust test passes.

## Artifact Index
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_3/analysis.md — Detailed analysis of findings
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_3/handoff.md — 5-component handoff report
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_3/progress.md — Liveness tracker
