# Handoff Report: KEYSTONE Auto-Backend Selector Investigation

## 1. Observation
- **Test Executable**: `third_party/KEYSTONE/bin/test_auto_backend`
- **Execution Command**:
  ```bash
  KEYSTONE_HOME="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE" \
  LD_LIBRARY_PATH="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE/fortran" \
  ./bin/test_auto_backend
  ```
- **Error Output**:
  ```
  Running auto backend selector tests
  ===================================

  ASSERTION FAILED: decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH at tests/test_auto_backend.c:228 in test_large_single_thread_batch_uses_scalar
  ```
- **File & Line context**:
  - `third_party/KEYSTONE/tests/test_auto_backend.c` lines 223-229:
    ```c
    if (keystone_fortran_backend_available()) {
        TEST_ASSERT(decision.backend == KEYSTONE_BACKEND_FORTRAN || decision.backend == KEYSTONE_BACKEND_SCALAR);
        TEST_ASSERT(decision.decision_source == KEYSTONE_DECISION_SOURCE_MEASURED || decision.decision_source == KEYSTONE_DECISION_SOURCE_CACHE || decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH);
    } else {
        TEST_ASSERT(decision.backend == KEYSTONE_BACKEND_SCALAR);
        TEST_ASSERT(decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH);
    }
    ```
  - `third_party/KEYSTONE/src/keystone.c` lines 1791-1793:
    ```c
    const int query_shape = keystone_detect_auto_query_shape(arr, n, items, num_items);
    if (!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) &&
        keystone_auto_scalar_fast_path(num_items, config, thread_count)) {
    ```
  - `third_party/KEYSTONE/src/keystone.c` lines 1550-1552:
    ```c
    if (query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
        return KEYSTONE_BACKEND_FORTRAN;
    }
    ```

---

## 2. Logic Chain
1. The test `test_large_single_thread_batch_uses_scalar` calls `keystone_search_batch_auto` with a dense sorted query shape where `num_items` = 20000.
2. Since 20000 is greater than `KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` (4096), the sub-expression `(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS)` is `TRUE`.
3. In `keystone_search_batch_auto`, the condition to take the fast path is `!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) && keystone_auto_scalar_fast_path(...)`. Due to the sub-expression being `TRUE`, the negation `!(...)` is `FALSE`.
4. As a result, the code bypasses the fast path and goes to calibration/measurement, where it records the decision source as `KEYSTONE_DECISION_SOURCE_MEASURED` rather than `KEYSTONE_DECISION_SOURCE_FAST_PATH`.
5. However, since the Fortran backend is unavailable (`keystone_fortran_backend_available()` returns `0`), the test executes the `else` branch of the assertion block, which strictly expects `decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH`.
6. Therefore, the assertion fails because the router logic does not check if the Fortran backend is available before bypassing the fast path for dense sorted queries.

---

## 3. Caveats
- Investigated only the single-threaded and multi-threaded auto-backend selector tests.
- Assumes that if the Fortran backend is unavailable, it should never bypass the fast path for dense sorted queries when `keystone_auto_scalar_fast_path` returns `TRUE`.
- Did not verify dynamic loading of a shared library for Fortran if `KEYSTONE_ENABLE_FORTRAN` is defined at runtime but missing from the compilation toolchain (handled here as static availability).

---

## 4. Conclusion
The failure is caused by the router logic bypassing the scalar fast path for large dense sorted queries even when the Fortran backend is not available. To correct this, both `keystone_search_batch_auto` and `keystone_static_auto_backend` in `src/keystone.c` must check `keystone_fortran_backend_available()` before treating Fortran as a routing candidate.

---

## 5. Verification Method
1. Apply the patch `/fast/Main Workspace/ZEROPAIN/.agents/explorer_2/keystone_fortran_avail.patch`.
2. Build and run the test suite using:
   ```bash
   make clean && make tests
   KEYSTONE_HOME="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE" \
   LD_LIBRARY_PATH="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE/fortran" \
   ./bin/test_auto_backend
   ```
3. Check that the command exits successfully with `Auto backend selector calibration verified.`.
