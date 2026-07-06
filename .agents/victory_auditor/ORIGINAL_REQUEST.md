## 2026-07-06T10:00:18Z
You are the Victory Auditor (teamwork_preview_victory_auditor).
Your working directory is `/fast/Main Workspace/ZEROPAIN/.agents/victory_auditor/`.
Your mission is to independently audit the codebase, verified changes, and implementation timeline for the ZEROPAIN and KEYSTONE integration project.
Please read `/fast/Main Workspace/ZEROPAIN/.agents/ORIGINAL_REQUEST.md` and the Orchestrator's progress/handoff in `/fast/Main Workspace/ZEROPAIN/.agents/orchestrator/` to understand the goal.
Perform the 3-phase audit:
1. Timeline verification.
2. Cheating/facade/hardcoding detection.
3. Independent execution of test suites and verification scripts.
Write your audit results to `/fast/Main Workspace/ZEROPAIN/.agents/victory_auditor/audit.md` and your progress/status in `/fast/Main Workspace/ZEROPAIN/.agents/victory_auditor/progress.md`.
Report back to the Sentinel (parent agent) with a clear verdict of either `VICTORY CONFIRMED` or `VICTORY REJECTED`, along with your findings.

## 2026-07-06T11:20:21Z
You are the Forensic Auditor (teamwork_preview_auditor).
Your working directory is `/fast/Main Workspace/ZEROPAIN/.agents/victory_auditor`.
You must run in the main repository directory: `/fast/Main Workspace/ZEROPAIN`.
Your task is to perform systematic integrity forensics on all modified files to ensure that there is no cheating, hardcoded test outcomes, dummy implementations, or bypassed verification steps.

Please:
1. Audit all modified files (e.g., in `src/` and `tests/`) for integrity issues.
2. Produce a clear verdict (CLEAN or INTEGRITY VIOLATION) and detailed evidence.
3. Document your audit verdict and findings in `handoff.md` and report back.
