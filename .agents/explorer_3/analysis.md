# Analysis Report: KEYSTONE Auto-Backend Router and Test Flakiness Investigation

## Executive Summary
This report analyzes the failures in the KEYSTONE auto-backend routing test suite (`test_auto_backend`). The investigation identified two distinct issues causing tests to fail:
1. **A Routing Bug (when Fortran is disabled)**: The router bypasses the scalar fast path for large dense-sorted queries even when the Fortran backend is unavailable, resulting in unnecessary calibration and a mismatched `decision_source` (`KEYSTONE_DECISION_SOURCE_MEASURED` instead of `KEYSTONE_DECISION_SOURCE_FAST_PATH`).
2. **A Flaky Assertion Bug (when Fortran is enabled)**: The tests assert that the calibration run's $p95$ time is greater than or equal to the real run's elapsed time. This assertion is mathematically unstable under system scheduling jitter and cache state differences, causing intermittent failures.

---

## 1. Investigation Details

### Component Locations
The KEYSTONE auto backend selector and its tests are defined across the following files:
*   **Header Definitions**: `third_party/KEYSTONE/include/keystone.h` (declares `keystone_search_batch_auto` and metrics structures).
*   **Core Routing Logic**: `third_party/KEYSTONE/src/keystone.c` (implements the auto selector, fast path checks, and calibration routing).
*   **Fortran Backend Implementation**: `third_party/KEYSTONE/fortran/keystone_batch.f90` (defines the Fortran batch search routines).
*   **Test Suite**: `third_party/KEYSTONE/tests/test_auto_backend.c` (contains test cases for the auto backend routing behavior).

---

## 2. Failure Observations

Two types of failures were observed depending on compile-time configurations:

### Failure A (Fortran Disabled/Unavailable)
*   **Command**: Running `bin/test_auto_backend` where `keystone_fortran_backend_available()` returns `0`.
*   **Error**:
    ```
    Running auto backend selector tests
    ===================================

    ASSERTION FAILED: decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH at tests/test_auto_backend.c:228 in test_large_single_thread_batch_uses_scalar
    ```

### Failure B (Fortran Enabled, Intermittent)
*   **Command**: Running `bin/test_auto_backend` in a loop with Fortran enabled.
*   **Error**:
    ```
    ASSERTION FAILED: decision.p95_ns_per_key >= decision.estimated_ns_per_key at tests/test_auto_backend.c:448 in test_large_multi_thread_batch_calibrates_viable_backend
    ```
    (Or at line 148 in `test_sorted_8k_batch_uses_expected_backend`.)

---

## 3. Root Cause Analysis

### 3.1. Analysis of Failure A (Mismatched Decision Source)
In `third_party/KEYSTONE/src/keystone.c` (lines 1792–1793):
```c
    if (!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) &&
        keystone_auto_scalar_fast_path(num_items, config, thread_count)) {
```
*   When executing `test_large_single_thread_batch_uses_scalar`, `num_items` is `20000` (which is $\ge$ `KEYSTONE_AUTO_FORTRAN_MIN_ITEMS` of `4096`), and `query_shape` is `KEYSTONE_QUERY_SHAPE_DENSE_SORTED`.
*   Because the condition `(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS)` is true, the negated expression evaluates to `false`.
*   This causes the router to skip the scalar fast path and proceed to calibration (`keystone_calibrate_auto_backend`).
*   During calibration, because Fortran is not available and the thread count is 1, only the Scalar backend is measured, resulting in a decision source of `KEYSTONE_DECISION_SOURCE_MEASURED` (or `KEYSTONE_DECISION_SOURCE_CACHE`).
*   However, the test case asserts that the fast path should have been taken when Fortran is unavailable:
    ```c
    } else {
        TEST_ASSERT(decision.backend == KEYSTONE_BACKEND_SCALAR);
        TEST_ASSERT(decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH); // <-- FAILS
    }
    ```
*   **The Issue**: The router bypasses the scalar fast path for dense-sorted queries assuming Fortran is a potential candidate, without checking if Fortran is actually available.

### 3.2. Analysis of Failure B (Flaky Performance Assertions)
In `tests/test_auto_backend.c` (lines 148 and 448):
```c
    TEST_ASSERT(decision.p95_ns_per_key >= decision.estimated_ns_per_key);
```
*   During calibration, the selected backend is run 3 times, and `p95_ns_per_key` is set to the maximum duration among those runs.
*   The real run executes the selected backend once more, and its duration is recorded as `decision.estimated_ns_per_key`.
*   If the real run experiences any system scheduling jitter, a CPU frequency scaling change, or a page fault, its elapsed time (`estimated_ns_per_key`) can exceed the $p95$ of the 3 calibration runs, violating the assertion.
*   **The Issue**: Asserting that a single execution is faster than the $p95$ of previous runs is fundamentally flaky and susceptible to noise.

---

## 4. Recommended Fix Strategy

### Part 1: Router Fast-Path Bypass Fix
Modify the routing logic in `third_party/KEYSTONE/src/keystone.c` to check for Fortran backend availability:

1.  **In `keystone_search_batch_auto`** (around line 1792):
    ```c
    // Before:
    if (!(query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) && ...
    
    // After:
    if (!(keystone_fortran_backend_available() && query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) && ...
    ```

2.  **In `keystone_static_auto_backend`** (around line 1550):
    ```c
    // Before:
    if (query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
        return KEYSTONE_BACKEND_FORTRAN;
    }
    
    // After:
    if (keystone_fortran_backend_available() && query_shape == KEYSTONE_QUERY_SHAPE_DENSE_SORTED && num_items >= KEYSTONE_AUTO_FORTRAN_MIN_ITEMS) {
        return KEYSTONE_BACKEND_FORTRAN;
    }
    ```

### Part 2: Relaxing Flaky Test Assertions
Modify the assertions in `third_party/KEYSTONE/tests/test_auto_backend.c` to avoid checking runtime speed relationships that are subject to system noise:

*   **In `test_sorted_8k_batch_uses_expected_backend`** (line 148) and **`test_large_multi_thread_batch_calibrates_viable_backend`** (line 448):
    ```c
    // Before:
    TEST_ASSERT(decision.p95_ns_per_key >= decision.estimated_ns_per_key);
    
    // After:
    TEST_ASSERT(decision.p95_ns_per_key >= 0.0);
    ```

### Part 3: Test Runtime Context (Verification Prerequisite)
Because `fortran/libkeystone_batch.so` is linked using a relative path, the executable specifies the dynamic dependency as `fortran/libkeystone_batch.so`. By Linux dynamic loader conventions, libraries with slashes in their name are loaded strictly relative to the current working directory (CWD).
*   **Requirement**: Tests must be executed from the `third_party/KEYSTONE/` directory to ensure dynamic linking succeeds.
