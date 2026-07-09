## 2026-07-06T22:24:51Z
You are teamwork_preview_worker.
Your working directory is: /fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_worker_auto_routing
Your mission is to implement or verify the fix for the failing auto-routing native test in `test_auto_backend.c` (where the expected decision source differs from the compiled router path) so that KEYSTONE core native tests pass on this host, and ensure that the fix does not break any of the already passing tests in the KEYSTONE and ZEROPAIN test suites.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please do the following:
1. Read the project scope: `/fast/Main Workspace/ZEROPAIN/PROJECT.md`, the original request: `/fast/Main Workspace/ZEROPAIN/.agents/ORIGINAL_REQUEST.md`, and the Explorer synthesis: `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_orchestrator_auto_routing/synthesis.md`.
2. Inspect the current workspace. Check if the recommended fixes are already partially or fully present as uncommitted changes.
3. If not present or incomplete, implement the changes in `third_party/KEYSTONE/src/keystone.c` and `third_party/KEYSTONE/tests/test_auto_backend.c` precisely as recommended:
   - Check `keystone_fortran_backend_available()` before bypassing the scalar fast path.
   - Apply the same check in `keystone_static_auto_backend()`.
   - Clip `cached_p95_ns_per_key` during feedback loop to be at least `estimated_ns_per_key`.
   - Relax timing assertions in `tests/test_auto_backend.c` to check that `decision.p95_ns_per_key >= 0.0`.
4. Compile and run the test binary in `third_party/KEYSTONE/`:
   ```bash
   make clean
   make tests KEYSTONE_ENABLE_QIHSE_BRIDGE=1 QIHSE_ROOT=../QIHSE KEYSTONE_ENABLE_AVX2=1 KEYSTONE_ENABLE_AVX512=0 KEYSTONE_ENABLE_FORTRAN=0 KEYSTONE_ENABLE_CUDA=0 KEYSTONE_ENABLE_TAR_ZST=0
   ./bin/test_auto_backend
   ```
5. Run the full ZEROPAIN and KEYSTONE test suites (e.g., via `pytest` or any other test scripts at the root) to ensure everything passes and there are no regressions.
6. Verify output follows the code layout in `PROJECT.md`.
7. Write a detailed handoff report to `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_worker_auto_routing/handoff.md`. Include:
   - The exact changes made (including file diffs or descriptions).
   - The exact build and test commands run, and their success output.
   - Verification that the layout is compliant.

Action: Send a message to parent (id: 44e4506d-3f21-4b06-89e8-b5ace953c598) with the path to your handoff.md file when you are finished.
