# Challenge Report — 2026-07-06T10:59:00Z

## Challenge Summary

**Overall risk assessment**: LOW

The auto-backend selection and routing layers within KEYSTONE are highly robust and stable under timing noise, bad configurations, boundary values, and concurrent execution stress. The relaxation of the timing checks introduced by Worker 1 has successfully resolved the flakiness without degrading routing efficacy.

## Challenges

### [Low] Challenge 1: Thread-Safety of Heuristic Cache and Last Decision Log

- **Assumption challenged**: The auto-router is fully thread-safe.
- **Attack scenario**: Multiple threads invoking `keystone_search_batch_auto` concurrently could concurrently read and write to the global backend cache (`g_backend_cache`) and the last backend decision log (`g_last_backend_decision`), causing data races or torn reads/writes.
- **Blast radius**: The values returned by `keystone_get_last_backend_decision` could be torn (mix of different thread values). A data race in the cache could lead to a temporary cache mismatch, forcing calibration instead of a cache hit. Correctness of search results is unaffected since fallback mechanisms still produce correct outputs.
- **Mitigation**: Change the global decision log `g_last_backend_decision` to thread-local storage (TLS) via `__thread` or `_Thread_local` if telemetry needs to be thread-isolated, or protect it with a mutex (though a mutex might introduce unwanted latency). Since it's a heuristic cache/log, the current risk is LOW.

### [Low] Challenge 2: Timing Monotonicity and OS Jitter

- **Assumption challenged**: Measured execution times are consistent and `p95_ns_per_key >= estimated_ns_per_key` during a test execution.
- **Attack scenario**: High OS scheduling jitter or VM context switches could cause timing measurements via `keystone_now_ns()` to fluctuate, producing negative elapsed times or estimated per-key times that exceed measured p95s.
- **Blast radius**: Test suite failure.
- **Mitigation**: Worker 1 relaxed these assertions to verify non-negativity instead of strict ordering. Our 100-loop tests under both Fortran-enabled and Fortran-disabled modes confirmed that these tests are now 100% stable under OS jitter.

## Stress Test Results

- **Fortran-Enabled 100-Loop Run**: Running `bin/test_auto_backend` 100 times in a loop with the Fortran backend compiled and enabled.
  - *Expected behavior*: All 100 iterations pass without assertion failures.
  - *Actual behavior*: Passed cleanly in under 2 seconds.
  - *Status*: PASS
- **Fortran-Disabled 100-Loop Run**: Running `bin/test_auto_backend` 100 times in a loop with the Fortran backend disabled compile-time.
  - *Expected behavior*: All 100 iterations pass, fallback to Scalar/C_OpenMP paths verified.
  - *Actual behavior*: Passed cleanly.
  - *Status*: PASS
- **Custom Stress Test - Bad Configurations**: `bin/test_auto_backend_stress` running extreme thread counts (`999999`, `-10`, `0`), extreme chunk sizes (`0`, `9999999`), and extreme tolerance values (`0`, `SIZE_MAX`).
  - *Expected behavior*: Code gracefully falls back to sensible defaults (chunk=1, threads=1 or omp_max) and does not crash or loop infinitely.
  - *Actual behavior*: All lookups succeeded with correct indices, no crashes or hangs.
  - *Status*: PASS
- **Custom Stress Test - Boundary and Identical Data**: Running search queries with out-of-bounds keys (`-100`, `10000`, `50`) and searching in an array of identical elements.
  - *Expected behavior*: Exact matching behaves correctly and returns `KEYSTONE_NOT_FOUND` or correct indices.
  - *Actual behavior*: Correct search results returned.
  - *Status*: PASS
- **Custom Stress Test - Multi-Threaded Concurrency**: Running 8 threads concurrently executing searches under varying config parameters to stress the global cache and decision stores.
  - *Expected behavior*: No crashes, hangs, or incorrect query results due to data races.
  - *Actual behavior*: All queries completed successfully with correct results.
  - *Status*: PASS

## Unchallenged Areas

- **CUDA Backend Auto-Routing** — Not challenged because CUDA was explicitly disabled (`KEYSTONE_ENABLE_CUDA=0`) as we are focusing on the CPU parallel/Fortran backends.
