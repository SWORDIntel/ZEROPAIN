# BRIEFING — 2026-07-06T09:52:30Z

## Mission
Investigate KEYSTONE's auto backend selector, run and analyze `test_auto_backend` failure, and recommend a fix strategy.

## 🔒 My Identity
- Archetype: Explorer
- Roles: Read-only investigator
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/explorer_1/
- Original parent: 24533436-ee82-47cd-99ee-26081df67a85
- Milestone: KEYSTONE Backend Selector Investigation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Must write findings to analysis.md and handoff report to handoff.md
- Log progress to progress.md

## Current Parent
- Conversation ID: 24533436-ee82-47cd-99ee-26081df67a85
- Updated: 2026-07-06T09:52:30Z

## Investigation State
- **Explored paths**:
  - `third_party/KEYSTONE/src/keystone.c`
  - `third_party/KEYSTONE/tests/test_auto_backend.c`
  - `third_party/KEYSTONE/include/keystone.h`
  - `third_party/KEYSTONE/Makefile`
- **Key findings**:
  - Identified two distinct issues in `keystone_search_batch_auto` in `third_party/KEYSTONE/src/keystone.c`:
    1. Fast-path bypass issue: The scalar fast path is bypassed for dense sorted queries larger than `KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` without checking if the Fortran backend is actually available. This causes a test assertion failure `decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH` in `test_large_single_thread_batch_uses_scalar` when Fortran is not available.
    2. Timing noise / p95 bounding issue: An assertion `decision.p95_ns_per_key >= decision.estimated_ns_per_key` fails flakily because the single actual search execution's elapsed time can exceed the 95th percentile estimated during the calibration phase.
  - Verified a complete fix by copying the file, modifying it, compiling and linking with the tests. Tested both Fortran-enabled and Fortran-disabled builds over 20 iterations each, achieving 100% success.
- **Unexplored areas**: None, the core task is fully analyzed and verified.

## Key Decisions Made
- Performed compilation and execution verification of the fixes locally in the agent's working directory.
- Created a patch file `keystone_routing_fixes.patch` containing the precise diff.

## Artifact Index
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_1/analysis.md — Detailed analysis of KEYSTONE's auto backend selector failure
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_1/handoff.md — Handoff report following the Handoff Protocol
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_1/progress.md — Liveness progress heartbeat
- /fast/Main Workspace/ZEROPAIN/.agents/explorer_1/keystone_routing_fixes.patch — Diff patch containing the proposed changes
