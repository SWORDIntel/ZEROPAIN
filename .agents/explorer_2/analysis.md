# Analysis Report: KEYSTONE Auto-Backend Selector Issue

## Executive Summary
The test binary `test_auto_backend` fails in `test_large_single_thread_batch_uses_scalar` due to an assertion failure because the auto-backend selector routing logic bypasses the scalar fast path for large dense sorted queries even when the Fortran backend is unavailable. This results in the decision source being recorded as `KEYSTONE_DECISION_SOURCE_MEASURED` instead of the expected `KEYSTONE_DECISION_SOURCE_FAST_PATH`.

---

## 1. Investigation Details

### Component Locations
The KEYSTONE auto backend selector and its tests are located at:
- **Header Definitions**: `third_party/KEYSTONE/include/keystone.h` (declares `keystone_search_batch_auto` and types).
- **Core Router Logic**: `third_party/KEYSTONE/src/keystone.c` (implements routing, calibration, and caching).
- **Test Suite**: `third_party/KEYSTONE/tests/test_auto_backend.c` (contains the failing test cases).

---

## 2. Test Execution & Observed Failure

Running the compiled test binary yields the following failure:

- **Command**:
  ```bash
  KEYSTONE_HOME="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE" \
  LD_LIBRARY_PATH="/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE/fortran" \
  ./bin/test_auto_backend
  ```
- **Output**:
  ```
  Running auto backend selector tests
  ===================================

  ASSERTION FAILED: decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH at tests/test_auto_backend.c:228 in test_large_single_thread_batch_uses_scalar
  ```

---

## 3. Root Cause Analysis

In `tests/test_auto_backend.c` at lines 222-229:
```c
    TEST_ASSERT(keystone_get_last_backend_decision(&decision) == 0);
    if (keystone_fortran_backend_available()) {
        TEST_ASSERT(decision.backend == KEYSTONE_BACKEND_FORTRAN || decision.backend == KEYSTONE_BACKEND_SCALAR);
        TEST_ASSERT(decision.decision_source == KEYSTONE_DECISION_SOURCE_MEASURED || decision.decision_source == KEYSTONE_DECISION_SOURCE_CACHE || decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH);
    } else {
        TEST_ASSERT(decision.backend == KEYSTONE_BACKEND_SCALAR);
        TEST_ASSERT(decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH); // <-- FAILS HERE
    }
```

### Analysis of the Routing Decision Logic
In `src/keystone.c` at lines 1791-1813:
```c
    const int query_shape = keystone_detect_auto_query_shape(arr, n, items, num_items);
    if (!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) &&
        keystone_auto_scalar_fast_path(num_items, config, thread_count)) {
        // ... (Runs scalar fast path and records KEYSTONE_DECISION_SOURCE_FAST_PATH) ...
    }
```

- When the Fortran backend is **unavailable** (meaning `keystone_fortran_backend_available()` returns `0`), the test case executes with `num_items = 20000` (which is $\ge$ `KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` of `4096`) and the query shape is detected as `KEYSTONE_QUERY_SHAPE_DENSE_SORTED`.
- Because `(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS)` is `TRUE`, the negated prefix `!(...)` evaluates to `FALSE`.
- This causes the router to bypass the fast path check completely and proceed to active calibration/measurement via `keystone_calibrate_auto_backend`.
- Since calibration runs measurement on the Scalar backend (no other backends are available since thread count is 1 and Fortran is disabled), the last backend decision is recorded with `KEYSTONE_DECISION_SOURCE_MEASURED` (or `KEYSTONE_DECISION_SOURCE_CACHE` on subsequent lookups).
- The test expected the router to bypass calibration and run the scalar fast path (`KEYSTONE_DECISION_SOURCE_FAST_PATH`) since the Fortran backend is not available.

---

## 4. Proposed Fix Strategy

To prevent unnecessary calibration and fix the test failure, we must check if the Fortran backend is available before bypassing the fast path or returning Fortran as a static fallback.

### Recommended Code Modifications in `third_party/KEYSTONE/src/keystone.c`:

#### 1. In `keystone_search_batch_auto` (lines 1791-1793):
- **Before**:
  ```c
      if (!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) &&
          keystone_auto_scalar_fast_path(num_items, config, thread_count)) {
  ```
- **After**:
  ```c
      if (!(keystone_fortran_backend_available() && query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) &&
          keystone_auto_scalar_fast_path(num_items, config, thread_count)) {
  ```

#### 2. In `keystone_static_auto_backend` (lines 1550-1552):
- **Before**:
  ```c
      if (query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
          return KEYSTONE_BACKEND_FORTRAN;
      }
  ```
- **After**:
  ```c
      if (keystone_fortran_backend_available() && query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
          return KEYSTONE_BACKEND_FORTRAN;
      }
  ```

A complete, machine-applicable patch has been written to `/fast/Main Workspace/ZEROPAIN/.agents/explorer_2/keystone_fortran_avail.patch`.
