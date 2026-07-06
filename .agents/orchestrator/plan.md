# Project Execution Plan

## Objective
Fully integrate QIHSE and KEYSTONE backends into ZEROPAIN framework by fixing failing native integration tests in KEYSTONE (`test_auto_backend`) and ensuring auto-routing stability.

## Steps

### Step 1: Decompose & Plan (Completed)
- Set up original request, briefing, project, and progress.md.
- Start heartbeat cron (task-11).

### Step 2: Investigation (Current)
- Spawn 3 Explorer subagents to run `third_party/KEYSTONE/bin/test_auto_backend` and investigate the root cause of the failure.
- Explorer subagents will analyze:
  - `third_party/KEYSTONE/tests/test_auto_backend.c`
  - The routing implementation and calibration code in KEYSTONE.
  - The compiler flags, environment variables (like `LD_LIBRARY_PATH`, `KEYSTONE_HOME`).
- Output: Explorer reports recommending fix strategies.

### Step 3: Implementation
- Spawn a Worker subagent with the chosen strategy to make the fix.
- Worker must:
  - Implement changes in KEYSTONE auto-backend routing code.
  - Run build and test commands (like `test_auto_backend` and the full KEYSTONE/ZEROPAIN test suite).
  - Verify layout and functionality.
  - Provide a handoff report with test outcomes.

### Step 4: Verification (Review, Challenge & Audit)
- Spawn 2 Reviewer subagents to verify code correctness and design conformance.
- Spawn 2 Challenger subagents to empirically verify solution correctness.
- Spawn 1 Forensic Auditor subagent to perform integrity audits.
- Collect all verdicts. If all pass, mark done. Else, loop back.

### Step 5: Wrap-up & Reporting
- Synthesize all findings.
- Report completion to the Sentinel (parent agent).
