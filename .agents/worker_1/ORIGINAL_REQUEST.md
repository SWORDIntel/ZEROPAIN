## 2026-07-06T09:52:56Z
You are Worker 1.
Your working directory is /fast/Main Workspace/ZEROPAIN/.agents/worker_1/.
Read /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/PROJECT.md and /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/plan.md.

Task:
Implement the fix for the failing native test in `test_auto_backend.c`.

Explorer findings and proposed strategy:
1. Fast-Path Router Bypass:
In `third_party/KEYSTONE/src/keystone.c`, the router bypasses the scalar fast path for dense-sorted inputs when `num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` (4096), without checking if the Fortran backend is actually available.
Fix: Modify `src/keystone.c` to check `keystone_fortran_backend_available()` before bypassing the scalar fast path.
Specifically, update the condition in `keystone_search_batch_auto` and in `keystone_static_auto_backend` to require `keystone_fortran_backend_available()`.
2. Timing Noise/Flaky Assertions:
The assertions in `third_party/KEYSTONE/tests/test_auto_backend.c` at lines 148 and 448 (which check `decision.p95_ns_per_key >= decision.estimated_ns_per_key`) can fail flakily due to OS jitter / timing noise during the single execution run.
Fix:
Option A: Modify `third_party/KEYSTONE/src/keystone.c` around line 1887 to ensure that the recorded `p95` time is at least the actual single run's `estimated` time:
```c
    if (cached_p95_ns_per_key <= 0.0) {
        cached_p95_ns_per_key = estimated_ns_per_key;
    } else if (cached_p95_ns_per_key < estimated_ns_per_key) {
        cached_p95_ns_per_key = estimated_ns_per_key;
    }
```
Option B: Relax the flaky assertions in `third_party/KEYSTONE/tests/test_auto_backend.c` at lines 148 and 448 to:
```c
    TEST_ASSERT(decision.p95_ns_per_key >= 0.0);
```
Please implement BOTH Option A and Option B to make the system highly robust and stable under CPU noise.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Verification Steps to Execute:
1. Go to `third_party/KEYSTONE` and compile and run the KEYSTONE test suite:
   ```bash
   make clean check KEYSTONE_ENABLE_CUDA=0
   ```
2. Run a loop of the auto-backend tests to guarantee no intermittent failures occur:
   ```bash
   for i in {1..50}; do ./bin/test_auto_backend || exit 1; done
   ```
3. Run the full ZEROPAIN test suite:
   ```bash
   pytest
   ```
4. Document the exact commands used, the files changed, and the test results in your handoff report.
5. Write your handoff report to `/fast/Main Workspace/ZEROPAIN/.agents/worker_1/handoff.md`.

Once completed, send a message to the orchestrator (conversation ID: 24533436-ee82-47cd-99ee-26081df67a85).
