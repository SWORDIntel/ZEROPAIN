# Original User Request

## 2026-07-06T09:48:29Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Fully integrate QIHSE and KEYSTONE backends into the ZEROPAIN framework by fixing the remaining failing native integration tests and ensuring the auto-routing path is stable.

Working directory: /fast/Main Workspace/ZEROPAIN
Integrity mode: development

## Requirements

### R1. Fix Auto-Routing Native Test
Investigate and fix the failing auto-routing test in `test_auto_backend.c` (where the expected decision source differs from the compiled router path) so that KEYSTONE core native tests pass on this host.

### R2. Maintain Existing Functionality
Ensure that the fix does not break any of the already passing tests in the KEYSTONE and ZEROPAIN test suites.

## Verification Resources
The failing test can be run using the compiled binary: `third_party/KEYSTONE/bin/test_auto_backend`. The environment variables like `LD_LIBRARY_PATH` and `KEYSTONE_HOME` must be set correctly.

## Acceptance Criteria

### Test Suite Passes
- [ ] Running `third_party/KEYSTONE/bin/test_auto_backend` yields a success exit code and no assertion failures.
- [ ] Running the full ZEROPAIN and KEYSTONE test suites passes successfully.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*

## 2026-07-06T10:38:33Z

# Teamwork Project Prompt — Draft

> Status: Ready for launch — awaiting user approval
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Implement the DSMIL adapter for interface integration and expand simulation fidelity by adding PK/PD tunables and making patient simulations scalable.

Working directory: /fast/Main Workspace/ZEROPAIN
Integrity mode: development

## Requirements

### R1. Interface Integration and DSMIL Adapter
Land the DSMIL adapter and expose the CLI and TUI entrypoints. Ensure there is a unified dashboard for the compound browser, builder, optimization, and simulation tools, aiming for web/TUI parity.

### R2. Simulation Fidelity & Scalability
Expand the compound templates to include receptor affinities, metabolic pathways, and patient-specific PK/PD tunables (e.g., weight, age, sex, comorbidities).
Make patient simulations scalable (remove hardcoded limits like "100k") so the scale can be defined dynamically.
Add medically accurate tolerance and addiction progression models with adjustable slopes.

## Acceptance Criteria

### Integration & Fidelity
- [ ] The CLI and TUI are fully accessible via the DSMIL adapter and offer a unified dashboard experience.
- [ ] Compound templates and simulation logic incorporate the new PK/PD tunables (affinities, pathways, patient parameters).
- [ ] The patient simulation framework can dynamically scale to any requested number of patients without being hardcoded to 100k.
- [ ] Tolerance and addiction progression models are integrated and configurable.
- [ ] Existing core tests (ZEROPAIN and KEYSTONE native tests) still pass.

---
*Next: when approved → delegate via invoke_subagent (see Delegation Protocol)*


## 2026-07-06T10:55:07Z

# Teamwork Project Prompt

> Status: Resumed after server restart
> Goal: Execute the teamwork preview

Implement the DSMIL adapter for interface integration and expand simulation fidelity by adding PK/PD tunables and making patient simulations scalable.

NOTE: Your previous run was interrupted by a server restart. The Explorer subagent successfully created the design proposal, which is saved at `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_dsmil_explore/handoff.md`. Please read this handoff report and proceed directly to the implementation phase.
Additionally, note that I have already renamed `src/patient_simulation_100k.py` to `src/patient_simulation.py` and updated all the imports across the codebase. Please apply your changes for dynamic scaling and PK/PD to `src/patient_simulation.py` and remove any remaining hardcoded 100k constraints.

Working directory: /fast/Main Workspace/ZEROPAIN
Integrity mode: development

## Requirements

### R1. Interface Integration and DSMIL Adapter
Land the DSMIL adapter and expose the CLI and TUI entrypoints. Ensure there is a unified dashboard for the compound browser, builder, optimization, and simulation tools, aiming for web/TUI parity.

### R2. Simulation Fidelity & Scalability
Expand the compound templates to include receptor affinities, metabolic pathways, and patient-specific PK/PD tunables (e.g., weight, age, sex, comorbidities).
Make patient simulations scalable (remove hardcoded limits like "100k") so the scale can be defined dynamically.
Add medically accurate tolerance and addiction progression models with adjustable slopes.

## Acceptance Criteria

### Integration & Fidelity
- [ ] The CLI and TUI are fully accessible via the DSMIL adapter and offer a unified dashboard experience.
- [ ] Compound templates and simulation logic incorporate the new PK/PD tunables (affinities, pathways, patient parameters).
- [ ] The patient simulation framework can dynamically scale to any requested number of patients without being hardcoded to 100k.
- [ ] Tolerance and addiction progression models are integrated and configurable.
- [ ] Existing core tests (ZEROPAIN and KEYSTONE native tests) still pass.

## 2026-07-06T22:17:19Z

# Teamwork Project Prompt

> Goal: Execute the teamwork preview

Fully integrate QIHSE and KEYSTONE backends into the ZEROPAIN framework by fixing the remaining failing native integration tests and ensuring the auto-routing path is stable.

Working directory: /fast/Main Workspace/ZEROPAIN
Integrity mode: development

## Requirements

### R1. Fix Auto-Routing Native Test
Investigate and fix the failing auto-routing test in `test_auto_backend.c` (where the expected decision source differs from the compiled router path) so that KEYSTONE core native tests pass on this host.

### R2. Maintain Existing Functionality
Ensure that the fix does not break any of the already passing tests in the KEYSTONE and ZEROPAIN test suites.

## Verification Resources
The failing test can be run using the compiled binary: `third_party/KEYSTONE/bin/test_auto_backend`. The environment variables like `LD_LIBRARY_PATH` and `KEYSTONE_HOME` must be set correctly.

## Acceptance Criteria

### Test Suite Passes
- [ ] Running `third_party/KEYSTONE/bin/test_auto_backend` yields a success exit code and no assertion failures.
- [ ] Running the full ZEROPAIN and KEYSTONE test suites passes successfully.

