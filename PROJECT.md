# Project: Auto-Routing Native Test Fix

## Architecture
- KEYSTONE core native tests (specifically `test_auto_backend`) run a router binary or call router functions.
- The compiled router path and expected decision source in `test_auto_backend.c` have a mismatch, causing the test to fail.
- System requires fixing the mismatch (either updating the expected source, configuration, or compilation parameters) without breaking existing tests.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Fix Auto-Routing Test | Fix test_auto_backend.c so that KEYSTONE core native tests pass and ZEROPAIN/KEYSTONE test suites remain passing. | None | IN_PROGRESS (Explorers: 925850e3-53bd-4343-82d1-a66bb56d9994, 2e14c05f-d893-4c5b-8c83-30ec14f5f634, e690a0ba-1230-4e59-a4e0-69e266d9af27) |

## Code Layout
- Test file: `third_party/KEYSTONE/tests/test_auto_backend.c`
- Test binary: `third_party/KEYSTONE/bin/test_auto_backend`
