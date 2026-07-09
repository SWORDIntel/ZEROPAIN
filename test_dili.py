from src.dili_modeling import HepatotoxicityModel
from src.opioid_analysis_tools import CompoundDatabase
import numpy as np

if __name__ == "__main__":
    db = CompoundDatabase()
    sr17 = db.get_compound("SR-17018")
    sr14 = db.get_compound("SR-14968")
    bup = db.get_compound("Buprenorphine")
    
    model = HepatotoxicityModel([sr17, sr14, bup])
    alt_levels = model.simulate_liver_stress(doses=[30.0, 40.0, 2.0], days=90)
    print(f"Average ALT: {np.mean(alt_levels)}")
