# Handoff Report: DSMIL Integration & Simulation Fidelity Expansion

## 1. Observation
From the investigation of the ZEROPAIN repository, we observed the following:

1. **Compound Profiles & Database**:
   - Class `CompoundProfile` is defined in `src/opioid_analysis_tools.py` (lines 14–50) as a dataclass.
   - Database initialization is in `src/opioid_analysis_tools.py` under `CompoundDatabase._initialize_compounds` (lines 106–250).
   - Currently, it lacks separate MOR, DOR, KOR affinities (relying instead on a single `ki_orthosteric` and a string `receptor_type`) and metabolic pathway details.

2. **Patient & Simulation Classes**:
   - `PatientProfile` is defined in `src/patient_simulation_100k.py` (lines 134–161) as a dataclass.
   - `PatientGenerator` is defined in `src/patient_simulation_100k.py` (lines 217–318), generating virtual cohorts with age, weight, sex, and comorbidities.
   - `PatientSimulator` is defined in `src/patient_simulation_100k.py` (lines 320–562) with a hardcoded PK/PD and tolerance mechanism (lines 435–450).
   - It computes:
     ```python
     # Update tolerance
     if not compound.reverses_tolerance:
         tolerance_increment = compound.tolerance_rate * beta_activation * 0.0001
         tolerance_level += tolerance_increment
     ```
     This does not use pluggable models from `src/tolerance_models.py`.

3. **Tolerance Models**:
   - File `src/tolerance_models.py` (lines 1–114) defines `ToleranceState`, `ToleranceModel`, `LinearTolerance`, `SigmoidTolerance`, `LaggedTolerance`, and `SimpleWithdrawal`, but it is only used for lightweight post-simulation projections in the orchestrator pipeline (`src/zeropain_pipeline.py`, lines 241–260) and is not wired into the core simulator.

4. **Hardcoded Sizing (100k Patients)**:
   - Python files default `n_patients` to 100,000 in `src/patient_simulation_100k.py` (line 576) and `src/zeropain_pipeline.py` (line 520).
   - The C implementation `src/patient_sim_main.c` relies on `#define N_PATIENTS 100000` (line 468) and a static setup script (`scripts/comprehensive_setup_script.sh`, line 530).

5. **Test Baseline**:
   - Running the test suite (`pytest`) verifies 28 passing tests.
   - Native tests (`third_party/KEYSTONE/bin/test_core_native` and `third_party/KEYSTONE/bin/test_auto_backend`) pass successfully.

---

## 2. Logic Chain
1. To integrate ZEROPAIN with external DSMIL pharmaceutical workflows, a **DSMIL Adapter** (`src/dsmil_adapter.py`) must be built. It needs to expose the CLI/TUI entrypoints and handle a structured JSON contract matching `PatientGenerationConfig`, `ProtocolConfig`, and `CompoundProfile`.
2. The current TUI operates as a series of sequential linear menus. Under the new contract, it must present a **unified multi-pane dashboard** utilizing Rich `Layout` to show compound database details, active protocol/optimization variables, and simulation outcomes in a single terminal interface.
3. Compound profiles are currently too simple. Expanding them with specific receptor affinities (`ki_mor`, `ki_dor`, `ki_kor`) and CYP-based metabolic pathways allows for patient-specific PK/PD adjustments.
4. Patient clearance should scale with metabolic pathway weights mapped to patient-specific CYP activity levels (which vary with age, sex, liver/kidney disease, etc.), instead of the existing simplistic `metabolism_rate` multiplier.
5. In order to dynamically scale populations without compile-time restrictions, both the Python parameters and C dynamic arrays (in `src/patient_sim_main.c`) must be adjusted to accept and scale sizes at runtime using CLI flags.
6. The simulator must be decoupled from hardcoded progression steps. Importing and instantiating `ToleranceModel` and an added `AddictionModel` into `PatientSimulator` enables pluggable dynamics with customizable slopes and behaviors.

---

## 3. Caveats
- **OpenVINO/Arc NPU Accelerator Compilation**: The OpenVINO path is dynamically loaded; if hardware is unavailable, fallback execution paths must be verified.
- **C Implementation Alignment**: The C codebase (`src/patient_sim_main.c`) is compiled as a standalone benchmark and does not directly import Python's `tolerance_models.py`. Any progression model changes implemented in Python must be ported or mirrored in C/C++ if native acceleration for those specific outcomes is needed.

---

## 4. Conclusion & Design Proposal

### R1. DSMIL Adapter & Unified TUI Dashboard
- **Adapter (`src/dsmil_adapter.py`)**:
  Create an adapter module exposing:
  - `run_cli(args: list[str]) -> int`
  - `run_tui() -> None`
  - `process_request(payload: dict) -> dict` which routes operations dynamically.
- **TUI Dashboard (`src/zeropain_tui.py`)**:
  Replace the menu selection loop with a Rich `Layout` divided into:
  - `Header`: System and accelerator status.
  - `Left Panel`: Compound database list.
  - `Right Top Panel`: Active treatment protocol & Optimization status.
  - `Right Bottom Panel`: Population metrics & live simulation graphs (ascii/rich tables).
  - `Footer`: Live prompt bar allowing quick commands.

### R2. Compound Template & PK/PD Tunables Expansion
- **Compound Dataclass (`src/opioid_analysis_tools.py`)**:
  Add fields:
  ```python
  ki_mor: float = float('inf')
  ki_dor: float = float('inf')
  ki_kor: float = float('inf')
  metabolic_pathways: Dict[str, float] = field(default_factory=lambda: {"CYP2D6": 0.5, "CYP3A4": 0.5})
  ```
- **Patient PK/PD (`src/patient_simulation_100k.py` & `src/opioid_analysis_tools.py`)**:
  - Calculate patient CYP activity rates dynamically (e.g., base CYP levels modulated by comorbidities: `liver_disease` reduces CYP efficiency by 40%).
  - Compute adjusted half-life:
    $$\tau_{half} = \frac{T_{half\_base}}{\sum (\text{pathway\_ratio} \times \text{patient\_cyp\_activity})}$$
  - Evaluate receptor activation separately across MOR, DOR, and KOR pathways using receptor-specific Ki values.

### R3. Dynamic Patient Simulation Sizing
- **Python**: Pass the user-selected size parameter (e.g., `--n-patients-sim`) directly into the simulation execution function, removing the hardcoded 100k defaults.
- **C Native (`src/patient_sim_main.c`)**:
  Modify the entrypoint to accept arguments:
  ```c
  int n_patients = 100000; // Default
  if (argc > 1) {
      n_patients = atoi(argv[1]);
  }
  PatientCharacteristics* patients = generate_population(n_patients);
  TreatmentOutcome* outcomes = (TreatmentOutcome*)calloc(n_patients, sizeof(TreatmentOutcome));
  ```

### R4. Progression Models with Adjustable Slopes
- **Addiction Model (`src/tolerance_models.py`)**:
  Add `AddictionState` and `LinearAddiction` with configurable slope and dopamine thresholds:
  ```python
  class LinearAddiction(AddictionModel):
      def __init__(self, slope: float = 0.005, threshold: float = 60.0):
          self.slope = slope
          self.threshold = threshold
      def update(self, state, dopamine_release, dt):
          surge = max(0.0, dopamine_release - self.threshold)
          state.level = min(1.0, state.level + self.slope * surge * dt)
          return state
  ```
- **Simulator Integration**:
  Replace hardcoded updates in `PatientSimulator.simulate_patient` with invocations of the selected `ToleranceModel` and `AddictionModel` configurations.

---

## 5. Verification Method
1. **Pytest Verification**:
   Run `pytest` to verify existing tests remain passing.
2. **New Simulation & Scaling Test**:
   Verify dynamic population sizing:
   `python src/zeropain_pipeline.py --simulate --n-patients-sim 5000`
3. **Native Selector Verification**:
   Validate KEYSTONE native backend:
   `./third_party/KEYSTONE/bin/test_core_native`
4. **Invalidation Condition**:
   If custom progression slope values do not impact final tolerance rates or result in regression of existing baseline tests, the implementation is invalid.
