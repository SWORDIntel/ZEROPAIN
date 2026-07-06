
# Gemini Project File

This file provides context for the Gemini AI to understand and work with this project.

## Project Structure

```
/
├── doc/
│   ├── compound_tuning_guide.md
│   ├── control_panel_readme.md
│   ├── docker_compose_security.md
│   ├── dockerfile_honeypot.md
│   ├── dockerfile_security.md
│   ├── MANIFEST.md
│   ├── mlops_pipeline_sr_cases.md
│   ├── tutorial_notebook.py
│   └── web_requirements.md
├── scripts/
│   ├── build_native_backends.sh
│   ├── build_installer_script.sh
│   ├── comprehensive_setup_script.sh
│   ├── control_panel_build.sh
│   ├── deploy_web_security.sh
│   ├── extract_and_organize.sh
│   ├── fixext.sh
│   └── zfsbootmenu-setup.sh
├── src/
│   ├── pipeline/
│   │   └── distributed_runner.py   # Checkpointed batch runner (Ray/Dask/local)
│   ├── utils/
│   │   ├── experiment_tracking.py
│   │   └── hardware.py
│   ├── dsmil_adapter.py            # DSMIL hub adapter (CLI/TUI/JSON gateway)
│   ├── framework-interface.cpp
│   ├── honeypot_generator.py
│   ├── opioid_analysis_tools.py    # CompoundProfile, CompoundDatabase (MOR/DOR/KOR Ki, CYP pathways)
│   ├── opioid_optimization_framework.py
│   ├── patient_sim_main.c          # Native C benchmark (runtime-scalable via argv)
│   ├── patient_simulation.py       # Scalable patient simulation engine (was patient_simulation_100k.py)
│   ├── pkpd_calibration.py
│   ├── protocol_config.c
│   ├── scenarios.py
│   ├── tolerance_models.py         # Pluggable ToleranceModel + AddictionModel
│   ├── yubikey_setup.py
│   ├── zeropain_control_panel.cpp
│   ├── zeropain_pipeline.py        # Main CLI orchestrator (--dsmil-adapter flag)
│   └── zeropain_tui.py             # Unified 4-pane Rich TUI dashboard
├── tests/
│   ├── test_new_features.py
│   ├── test_patient_generation.py
│   ├── test_progression_challenger.py
│   └── ...
├── third_party/
│   ├── QIHSE/                      # Native QIHSE KV/document store
│   └── KEYSTONE/                   # Native auto-routing backend
├── zeropain/
│   ├── api/                        # FastAPI application
│   ├── database/                   # Backend abstraction (SQLModel/QIHSE)
│   └── security/                   # CNSA 2.0 signature envelope helpers
├── DOWNLOAD_INDEX.html
├── README.md
└── requirements.txt
```

## Key Files

*   `src/dsmil_adapter.py`: DSMIL hub adapter — `run_cli()`, `run_tui()`, `process_request()` JSON gateway.
*   `src/opioid_optimization_framework.py`: Protocol optimiser.
*   `src/patient_simulation.py`: Scalable patient simulation engine (dynamic population size, pluggable models).
*   `src/opioid_analysis_tools.py`: Compound library with MOR/DOR/KOR Ki affinities and CYP metabolic pathways.
*   `src/tolerance_models.py`: Pluggable `ToleranceModel` (linear/sigmoid/lagged) and `AddictionModel`.
*   `src/zeropain_tui.py`: Unified 4-pane Rich TUI dashboard.
*   `src/pipeline/distributed_runner.py`: Numpy-safe checkpoint runner.
*   `requirements.txt`: Python dependencies.
*   `README.md`: Main documentation.

## Commands

*   **Install dependencies:** `pip install -e ".[alldeps]" --user --break-system-packages`
*   **Run the TUI dashboard:** `python src/zeropain_tui.py`
*   **Run via DSMIL adapter:**
    ```bash
    python src/dsmil_adapter.py --list-compounds
    python src/dsmil_adapter.py --simulate --compounds SR-17018 SR-14968 --n-patients-sim 5000
    python src/dsmil_adapter.py --optimize --compounds SR-17018 --n-patients-sim 500
    ```
*   **Run the pipeline CLI:**
    ```bash
    python src/zeropain_pipeline.py --simulate --n-patients-sim 10000 --tolerance-model sigmoid
    python src/zeropain_pipeline.py --dsmil-adapter --tui
    ```
*   **Run tests:** `pytest tests/`
*   **Build native backends:**
    ```bash
    scripts/build_native_backends.sh
    export ZEROPAIN_DB_BACKEND=qihse
    export QIHSE_HOME="$PWD/third_party/QIHSE"
    export KEYSTONE_HOME="$PWD/third_party/KEYSTONE"
    export LD_LIBRARY_PATH="$QIHSE_HOME:${LD_LIBRARY_PATH:-}"
    ```
*   **Run linter:** `flake8 src/`
*   **Run formatter:** `black src/`
