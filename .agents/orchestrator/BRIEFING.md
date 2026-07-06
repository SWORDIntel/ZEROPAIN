# BRIEFING — 2026-07-06T09:50:00Z

## Mission
Manage and drive the team to integrate QIHSE and KEYSTONE backends into the ZEROPAIN framework.

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/
- Original parent: parent
- Original parent conversation ID: 17da0cfb-5468-4b9f-ab30-2a81e5489734

## 🔒 My Workflow
- **Pattern**: Project Pattern
- **Scope document**: /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/PROJECT.md
1. **Decompose**: Decompose the task into milestones (e.g. Explorer investigation, worker execution, reviewer verification, challenger validation, and forensic auditor inspection)
2. **Dispatch & Execute** (pick ONE):
   - **Direct (iteration loop)**: Use the direct loop to spawn Explorer -> Worker -> Reviewer -> Challenger -> Auditor
   - **Delegate (sub-orchestrator)**: Spawn a sub-orchestrator if scope is too large (but this task seems self-contained enough for direct loop execution or a single milestone orchestrator)
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: Self-succeed at 16 spawns, write handoff.md, spawn successor
- **Work items**:
  1. Decompose & Plan [in-progress]
  2. Investigation [pending]
  3. Implementation & Unit Test [pending]
  4. Final Verification & Audit [pending]
- **Current phase**: 1
- **Current focus**: Decompose & Plan

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/ folder.
- If a Forensic Auditor reports INTEGRITY VIOLATION, the milestone FAILS UNCONDITIONALLY. Do not advance.
- Never reuse a subagent after it has delivered its handoff — always spawn fresh.

## Current Parent
- Conversation ID: 17da0cfb-5468-4b9f-ab30-2a81e5489734
- Updated: not yet

## Key Decisions Made
- Initialized briefing and plan.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| Explorer 1 | teamwork_preview_explorer | Investigate failing auto-routing test | completed | d8b97f94-2a5d-41e7-876e-27641668487f |
| Explorer 2 | teamwork_preview_explorer | Investigate failing auto-routing test | completed | 9c89dd8b-05e4-4f4a-87e6-2f8604fe61a0 |
| Explorer 3 | teamwork_preview_explorer | Investigate failing auto-routing test | completed | 9f83ce73-2bdf-4472-8e5f-cb312fda0145 |
| Worker 1 | teamwork_preview_worker | Implement auto-routing and flaky test fixes | completed | c2dbcb59-96e9-4b17-9c36-29ce20f92db3 |
| Reviewer 1 | teamwork_preview_reviewer | Verify correctness, build, and test ZEROPAIN/KEYSTONE | completed | 191d3383-163e-4037-b2b7-ae4a94e04ddd |
| Reviewer 2 | teamwork_preview_reviewer | Verify correctness, build, and test ZEROPAIN/KEYSTONE | completed | 73d081fc-876e-4b36-b71b-2f0e7b544cf1 |
| Challenger 1 | teamwork_preview_challenger | Stress test and verify auto-backend loop stability | completed | 9551ef38-c906-4b04-85c7-56ef989c3c35 |
| Challenger 2 | teamwork_preview_challenger | Stress test and verify auto-backend loop stability | completed | 89c7248e-95d7-4209-a29c-c9b2c352fb57 |
| Auditor 1 | teamwork_preview_auditor | Perform forensic integrity and cheating audit | completed | 3c332d30-0e32-4b1b-b835-f64e559c2da0 |

## Succession Status
- Succession required: no
- Spawn count: 9 / 16
- Pending subagents: none
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: task-11
- Safety timer: none
- On succession: kill all timers before spawning successor
- On context truncation: run `manage_task(Action="list")` — re-create if missing

## Artifact Index
- /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/ORIGINAL_REQUEST.md — Original request copy
- /fast/Main Workspace/ZEROPAIN/.agents/orchestrator/BRIEFING.md — Persistent working memory index
