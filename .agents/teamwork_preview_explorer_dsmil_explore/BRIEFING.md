# BRIEFING — 2026-07-06T11:46:00Z

## Mission
Analyze ZEROPAIN codebase to prepare for implementing DSMIL adapter, compound profile expansions, dynamic patient simulation scaling, and adjustable tolerance/addiction models.

## 🔒 My Identity
- Archetype: explorer
- Roles: Teamwork explorer
- Working directory: /fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_dsmil_explore
- Original parent: 0d4377f3-d130-43c9-bc9e-27fc8934c895
- Milestone: DSMIL Exploration

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Run existing pytest suite and native test commands to verify baseline
- Locate compound profiles/templates
- Locate PatientProfile, PatientGenerator, PatientSimulator, and tolerance models
- Suggest exact file changes and design for features

## Current Parent
- Conversation ID: 0d4377f3-d130-43c9-bc9e-27fc8934c895
- Updated: 2026-07-06T11:46:00Z

## Investigation State
- **Explored paths**: `src/opioid_analysis_tools.py`, `src/patient_simulation_100k.py`, `src/tolerance_models.py`, `src/opioid_optimization_framework.py`, `src/zeropain_tui.py`, `src/zeropain_pipeline.py`, `tests/`
- **Key findings**: Compound templates are in `src/opioid_analysis_tools.py` under `CompoundProfile` and `CompoundDatabase`. Patient profiles, simulators, and populations are in `src/patient_simulation_100k.py`. Pluggable tolerance models are defined in `src/tolerance_models.py` but are not currently integrated into the core `PatientSimulator` run loops. The 100k patient simulation size is hardcoded in both Python and compiled C.
- **Unexplored areas**: None, the entire scope has been successfully explored.

## Key Decisions Made
- Suggested using Rich Layout for a multi-pane TUI dashboard.
- Recommended dynamic C-level array allocations in `patient_sim_main.c` to allow runtime population scaling.
- Designed a dynamic CYP metabolic clearance model mapping patient-specific variables to compound CYP pathways.

## Artifact Index
- /fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_dsmil_explore/handoff.md — Analysis and design handoff report
