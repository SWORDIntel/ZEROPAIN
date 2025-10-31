
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
│   ├── tutorial_notebook.py
│   └── web_requirements.md
├── scripts/
│   ├── build_installer_script.sh
│   ├── comprehensive_setup_script.sh
│   ├── control_panel_build.sh
│   ├── deploy_web_security.sh
│   ├── extract_and_organize.sh
│   ├── fixext.sh
│   └── zfsbootmenu-setup.sh
├── src/
│   ├── framework-interface.cpp
│   ├── honeypot_generator.py
│   ├── opioid_analysis_tools.py
│   ├── opioid_optimization_framework.py
│   ├── patient_sim_main.c
│   ├── patient_simulation_100k.py
│   ├── protocol_config.c
│   ├── yubikey_setup.py
│   └── zeropain_control_panel.cpp
├── DOWNLOAD_INDEX.html
├── README.md
└── requirements.txt
```

## Key Files

*   `src/opioid_optimization_framework.py`: The main script for running the optimization framework.
*   `src/patient_simulation_100k.py`: The main script for running the patient simulation.
*   `src/opioid_analysis_tools.py`: The main script for running the analysis tools.
*   `requirements.txt`: The list of Python dependencies.
*   `README.md`: The main documentation file.

## Commands

*   **Install dependencies:** `pip install -r requirements.txt`
*   **Run the framework:**
    ```bash
    python src/opioid_optimization_framework.py
    python src/patient_simulation_100k.py
    python src/opioid_analysis_tools.py
    ```
*   **Run linter:** `flake8 src/`
*   **Run formatter:** `black src/`

