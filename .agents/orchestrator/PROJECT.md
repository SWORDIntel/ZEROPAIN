# Project: ZEROPAIN QIHSE & KEYSTONE Integration

## Architecture
- ZEROPAIN integrates the QIHSE and KEYSTONE backends.
- KEYSTONE core contains an auto-routing layer (`keystone_search_batch_auto`) that dynamically selects the optimal backend (SCALAR, FORTRAN, C_OPENMP, etc.) based on inputs, calibration, and cache.
- Current issue: `test_auto_backend` fails in integration due to a mismatch in expected decision source or routing path.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Explorer Investigation | Investigate failing test and routing logic | none | DONE |
| 2 | Implementation of Routing Fix | Correct routing path / decision source in KEYSTONE auto-backend selector | M1 | DONE |
| 3 | Verification and Audit | Verify full KEYSTONE & ZEROPAIN test suites, perform Forensic Audit | M2 | DONE |

## Interface Contracts
### KEYSTONE Auto-Backend Selector
- API: `size_t keystone_search_batch_auto(const int64_t* data, size_t data_size, keystone_batch_item_t* items, size_t num_items, keystone_anchor_table_t* table, size_t max_anchors, const keystone_parallel_config_t* config)`
- Returns number of found keys, updates `items[i].result` and `items[i].ordinal`, and sets the last backend decision retrieved via `keystone_get_last_backend_decision`.
