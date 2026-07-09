import sys
import os
sys.path.insert(0, os.path.abspath('src'))

from opioid_analysis_tools import CompoundDatabase
from patient_simulation import PatientSimulator, PatientGenerationConfig, PopulationSimulation
from dsmil_adapter import _load_calibrated_tolerance_config
from opioid_optimization_framework import ProtocolConfig

db = CompoundDatabase()
sim = PopulationSimulation(db)
tc = _load_calibrated_tolerance_config()

protocol = ProtocolConfig(
    compounds=['SR-16435', 'Buprenorphine'],
    doses=[2.49, 0.5],
    frequencies=[2, 2]
)

print("\n--- Running 10k Trial (Extrapolates to 50k) with SR-16435 ---")
results = sim.run_simulation(n_patients=10000, protocol=protocol, duration_days=30, tolerance_config=tc)

print(f"\nResults for 10k patients (30 Days):")
print(f"Average Pain Score: {results['avg_pain_score']:.4f}")
print(f"Withdrawal Rate:    {results['withdrawal_rate']*100:.2f}%")
print(f"Addiction Rate:     {results['addiction_rate']*100:.2f}%")
print(f"Adverse Events:     {results['adverse_event_rate']*100:.2f}%")
