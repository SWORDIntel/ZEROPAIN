## 2026-07-06T10:47:33Z
Your working directory is `/fast/Main Workspace/ZEROPAIN/.agents/worker_core_impl`.
Please implement the following features in the ZEROPAIN codebase:

1. DSMIL Adapter & CLI/TUI Entrypoints:
   - Create `src/dsmil_adapter.py` that wraps and exposes the CLI/TUI entrypoints and handles a structured JSON contract matching `PatientGenerationConfig`, `ProtocolConfig`, and `CompoundProfile`.
   - Update `src/zeropain_pipeline.py` or other files to allow entry through the DSMIL adapter.
2. Unified TUI Dashboard:
   - Refactor `src/zeropain_tui.py` to offer a unified dashboard experience using a Rich `Layout` combining the compound browser, builder, optimization, and simulation dashboards, ensuring web/TUI parity.
3. Compound Template & PK/PD Tunables Expansion:
   - In `src/opioid_analysis_tools.py`, expand `CompoundProfile` with receptor affinities (`ki_mor`, `ki_dor`, `ki_kor`, defaults to float('inf')) and metabolic pathways (`metabolic_pathways` e.g., mapping CYP enzymes to ratios, default `{"CYP2D6": 0.5, "CYP3A4": 0.5}`).
   - Update initial database compounds with representative values for these tunables.
   - In `src/patient_simulation_100k.py` (and relevant PK/PD logic), calculate patient CYP activity rates dynamically based on demographics (age, sex) and comorbidities (e.g., liver disease reduces CYP efficiency by 40%). Apply these to compute adjusted half-lives and evaluate receptor occupancy across separate MOR, DOR, and KOR pathways.
4. Scale Simulation Dynamically:
   - Modify `src/patient_simulation_100k.py`, `src/zeropain_pipeline.py`, and other scripts to support dynamic population sizes (remove hardcoded 100k limits).
   - Update the C implementation in `src/patient_sim_main.c` to accept population size arguments at runtime (e.g., from command line `argv[1]`) and dynamically allocate/free memory for the patients and outcomes.
5. Tolerance & Addiction Progression Models:
   - Add/enhance progression models in `src/tolerance_models.py` (e.g. `AddictionState`, `LinearAddiction`) with adjustable slopes.
   - Integrate them into `PatientSimulator` in `src/patient_simulation_100k.py` so the simulation utilizes the selected and configured progression models instead of hardcoded rules.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Verification:
- Ensure all pytests pass.
- Verify native tests (e.g. `third_party/KEYSTONE/bin/test_core_native`, `test_auto_backend`) pass.
- Write unit tests targeting the new DSMIL adapter, PK/PD tunables, simulation scalability, and progression models.
- Write your handoff report to `/fast/Main Workspace/ZEROPAIN/.agents/worker_core_impl/handoff.md` and send a message back.

## 2026-07-06T10:57:53Z
You are the Worker Core Implementation (teamwork_preview_worker).
Your working directory is `/fast/Main Workspace/ZEROPAIN/.agents/worker_core_impl`.
You must run in the main repository directory: `/fast/Main Workspace/ZEROPAIN`.
Your mission is to implement all core features, expand simulation fidelity, remove hardcoded limits, and verify the test suites.

Refer to the Explorer's Handoff Report at `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_explorer_dsmil_explore/handoff.md` and the original request at `/fast/Main Workspace/ZEROPAIN/.agents/teamwork_preview_orchestrator_dsmil/ORIGINAL_REQUEST.md` for context.

Please complete the following tasks:

1. Land the DSMIL adapter:
   - Create `src/dsmil_adapter.py` that implements CLI and TUI entrypoints (`run_cli(args: list[str]) -> int`, `run_tui() -> None`, etc.).
   - Update `src/zeropain_pipeline.py` to parse and support the `--dsmil-adapter` argument, routing execution to `src/dsmil_adapter.py`.
   - Update `src/zeropain_tui.py` to provide a unified multi-pane dashboard using Rich `Layout`. Divide the layout into:
     - Header: System and accelerator status (e.g. OpenVINO NPU status).
     - Left Panel: Compound database browser.
     - Right Top Panel: Active treatment protocol & Optimization status (Compound Builder & Optimization options).
     - Right Bottom Panel: Population metrics & live simulation graphs (live progress/results).
     - Footer: Live prompt/command bar allowing quick commands (menu/navigation/actions).
     - Ensure Web/TUI parity by supporting compound browsing, custom compound building, protocol optimization, and patient simulation in this unified interface.

2. Expand compound templates and patient-specific PK/PD tunables:
   - Expand `CompoundProfile` in `src/opioid_analysis_tools.py` to include separate receptor affinities: `ki_mor` (default `inf`), `ki_dor` (default `inf`), and `ki_kor` (default `inf`), and metabolic pathways `metabolic_pathways` (default factory mapping CYP enzymes: `{"CYP2D6": 0.5, "CYP3A4": 0.5}`).
   - Update database initialization in `CompoundDatabase._initialize_compounds` to populate these values for default compounds.
   - Update patient PK/PD calculations in `src/patient_simulation.py`:
     - Calculate patient-specific CYP activity rates dynamically, e.g. base CYP levels modulated by age, sex, and comorbidities (like `liver_disease` reducing it by 40%).
     - Compute adjusted half-life: t_half = base_t_half / sum(pathway_ratio * patient_cyp_activity).
     - Evaluate receptor occupancy separately across MOR, DOR, and KOR pathways using receptor-specific Ki values instead of the single `ki` value.

3. Make patient simulations scalable:
   - Remove hardcoded 100k limits and defaults (such as in `src/patient_simulation.py` and `src/zeropain_pipeline.py`). Allow setting population size dynamically via CLI flags (`--n-patients-sim`).
   - In `src/patient_sim_main.c`, modify the main function to accept the patient count dynamically at runtime (e.g., from command line `argv[1]`, with a fallback default like 100,000). Dynamically allocate and free patient and outcomes arrays (using `malloc`/`calloc` on the heap) instead of hardcoding static arrays or macros. Ensure it compiles and runs correctly.

4. Add tolerance and addiction progression models:
   - In `src/tolerance_models.py`, add `AddictionState` and `LinearAddiction` progression model (with configurable slopes and thresholds).
   - In `src/patient_simulation.py`, wire the `ToleranceModel` and `AddictionModel` into the `PatientSimulator.simulate_patient` loop, replacing the hardcoded tolerance updates with the pluggable models from `src/tolerance_models.py`. Ensure these models use adjustable slopes from the simulation configuration.

5. Verification:
   - Run `pytest` to verify existing tests and write new tests covering the newly added features.
   - Run the native KEYSTONE tests: `third_party/KEYSTONE/bin/test_core_native` and `third_party/KEYSTONE/bin/test_auto_backend`.
   - Verify that all tests pass.

6. Report:
   - Document all changes, compilation commands, and test results in `handoff.md` and report back when finished.

MANDATORY INTEGRITY WARNING — include this verbatim:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.
