import sys
from pathlib import Path
sys.path.insert(0, "/fast/Main Workspace/ZEROPAIN/src")

from opioid_analysis_tools import CompoundDatabase
from patient_simulation import PatientSimulator, PatientGenerationConfig, PopulationSimulation
from dsmil_adapter import _load_calibrated_tolerance_config
from opioid_optimization_framework import ProtocolConfig

db = CompoundDatabase()
sim = PopulationSimulation(db)

tc = _load_calibrated_tolerance_config()

protocol = ProtocolConfig(
    compounds=['SR-16435', 'Buprenorphine', 'Oxycodone'],
    doses=[16.17, 25.31, 10.0],
    frequencies=[2, 1, 4]
)

results = sim.run_simulation(n_patients=10, protocol=protocol, duration_days=90, tolerance_config=tc)

print(results)
