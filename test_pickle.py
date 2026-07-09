from functools import partial
import pickle
from src.patient_simulation import PatientSimulator
from src.opioid_optimization_framework import PharmacokineticModel, ProtocolConfig

def test():
    simulator = PatientSimulator()
    sim_func = partial(simulator.simulate_patient, protocol=ProtocolConfig([10], [4], [0.1]), duration_days=90, tolerance_config={})
    try:
        pickle.dumps(sim_func)
        print("Picklable!")
    except Exception as e:
        print(f"Not picklable: {e}")

if __name__ == '__main__':
    test()
