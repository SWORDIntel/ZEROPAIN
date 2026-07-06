## Forensic Audit Report

**Work Product**: ZEROPAIN & KEYSTONE Integration Codebase
**Profile**: General Project
**Verdict**: CLEAN

### Phase Results
- **Hardcoded output detection**: PASS — No hardcoded test outputs, faked test results, or cheating routines were detected in the source code or test files. The relaxed assertion in `test_auto_backend.c` is correct because when the Fortran backend is unavailable, the auto selector falls back to the scalar fast path, where `p95_ns_per_key` is designed to be recorded as `0.0`.
- **Facade detection**: PASS — The custom MAP calibration in `src/pkpd_calibration.py` utilizes a genuine, iteratively converging coordinate descent optimization algorithm, avoiding SciPy dependency correctly. The CNSA 2.0 signature envelope in `cnsa.py` is implemented correctly and integrates with external signing/verification utilities when configured.
- **Pre-populated artifact detection**: PASS — No pre-populated `.log`, test results, or output files were found in the workspace prior to auditing.
- **Build and run**: PASS — The ZEROPAIN test suite (`pytest`) compiled and completed successfully (28/28 tests passed). The KEYSTONE library successfully compiled (`make tests`) and completed its entire native test suite successfully (`make check`).
- **Output verification**: PASS — The auto-backend test binary was run 50 times sequentially in a loop, verifying that the router correctly calibrates and routes batches without failure (100% success rate).
- **Dependency audit**: PASS — No forbidden external execution delegations or shortcuts were used. The core logic remains inside the codebase.

### Evidence

#### 1. ZEROPAIN pytest Output
```
tests/test_api_docking.py ..                                             [  7%]
tests/test_api_simulation.py ..                                          [ 14%]
tests/test_cli_runs.py ..                                                [ 21%]
tests/test_database_backends.py ..                                       [ 28%]
tests/test_distributed_runner.py ..                                      [ 35%]
tests/test_docking_pipeline.py ....                                      [ 50%]
tests/test_experiment_tracking.py ....                                   [ 64%]
tests/test_modeling.py ....                                              [ 78%]
tests/test_patient_generation.py ....                                    [ 92%]
tests/test_qihse_native_integration.py ..                                [100%]

======================== 28 passed, 1 warning in 4.63s =========================
```

#### 2. KEYSTONE Native Test Suite Output (`make check`)
```
==> bin/test_enhanced
🧪 DSMIL KEYSTONE Integration Test Suite
==========================================
✓ Context creation successful
✓ Telemetry search successful
✓ Security search successful
✓ Log search successful
✓ Error handling tests passed
✓ Statistics tracking works
✅ All integration tests passed!

==> bin/test_auto_backend
Running auto backend selector tests
===================================
Auto backend selector calibration verified.

==> bin/test_fortran_backend
Running Fortran backend tests
=============================
Fortran backend correctness verified.

==> bin/test_telemetry_processor_perf
Telemetry processor correctness/performance tests
=================================================
All telemetry processor tests passed.

==> bin/test_performance_fix
🧪 Verification of Performance Fix
=================================
✓ Internal cache mechanism verified (hit rate: 0.50)
✓ Explicit indexed search verified
✅ All performance fix tests passed!

==> bin/test_core_native
Running Enhanced KEYSTONE Test Suite
=======================================
✓ CPU feature detection works
✓ Memory-bounded anchor management works
✓ Workload-specific optimization works
✓ Enhanced statistics tracking works
✓ Performance improvements verified
✓ DSMIL workload initialization works
🎉 All Enhanced KEYSTONE tests passed!

==> bin/test_tar_zst
KEYSTONE tar.zst streaming search test suite
==============================================
  [PASS] open_close
  [PASS] iterate_members
  [PASS] search_text_member
  ...
Results: 12 passed, 0 failed
```

#### 3. KEYSTONE Auto-Backend Routing Patch
```diff
diff --git a/src/keystone.c b/src/keystone.c
index 9abf862..3c4b13a 100644
--- a/src/keystone.c
+++ b/src/keystone.c
@@ -1547,7 +1547,9 @@ static keystone_backend_t keystone_static_auto_backend(size_t n,
                                                            const keystone_parallel_config_t* config,
                                                            int thread_count,
                                                            int query_shape) {
-    if (query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
+    if (query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED &&
+        keystone_fortran_backend_available() &&
+        num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
         return KEYSTONE_BACKEND_FORTRAN;
     }
```

#### 4. Custom coordinate search algorithm in `src/pkpd_calibration.py`
```python
def _minimize_map(
    x0: np.ndarray,
    t: np.ndarray,
    y: np.ndarray,
    priors: Dict[str, PriorSpec],
    model: str,
    dose: float,
) -> _OptimizeResult:
    x = np.maximum(np.asarray(x0, dtype=float), 1e-9)
    best = _negative_log_posterior(x, t, y, priors, model, dose)
    steps = np.maximum(np.abs(x) * 0.25, 0.1)
    iterations = 0

    for iterations in range(1, 121):
        improved = False
        for idx in range(x.size):
            for direction in (-1.0, 1.0):
                candidate = x.copy()
                candidate[idx] = max(candidate[idx] + direction * steps[idx], 1e-9)
                score = _negative_log_posterior(candidate, t, y, priors, model, dose)
                if score < best:
                    x = candidate
                    best = score
                    improved = True
        if not improved:
            steps *= 0.5
        if float(np.max(steps)) < 1e-6:
            break
    ...
```
