import numpy as np
from opioid_analysis_tools import CompoundDatabase

class HepatotoxicityModel:
    def __init__(self, compounds):
        self.compounds = compounds
        # Arbitrary baseline reactive metabolite formation rates
        # In reality, this requires in-vitro human hepatocyte assay data
        self.dili_risk_factors = {
            'SR-17018': 0.02, # Low expected reactive metabolites
            'SR-14968': 0.05, # Moderate
            'Buprenorphine': 0.01, # Very low
            'Oxycodone': 0.03
        }
        
    def simulate_liver_stress(self, doses, days, liver_disease_prevalence=0.06):
        liver_enzymes_alt = [] # Alanine transaminase (ALT) marker
        
        for patient in range(1000):
            has_liver_disease = np.random.rand() < liver_disease_prevalence
            clearance_efficiency = 0.5 if has_liver_disease else 1.0
            
            alt_baseline = np.random.normal(25, 5) # Normal ALT is ~7-55 U/L
            alt_level = alt_baseline
            
            for day in range(days):
                daily_toxic_load = 0
                for compound, dose in zip(self.compounds, doses):
                    risk = self.dili_risk_factors.get(compound.name, 0.05)
                    # Toxic load scales with dose and lack of clearance
                    daily_toxic_load += (dose * risk) / clearance_efficiency
                
                # ALT spikes if toxic load accumulates beyond liver regeneration
                alt_level += daily_toxic_load * np.random.normal(1.0, 0.2)
                # Liver heals slowly
                alt_level -= (alt_level - alt_baseline) * 0.1 
                
            liver_enzymes_alt.append(alt_level)
            
        return liver_enzymes_alt

if __name__ == "__main__":
    db = CompoundDatabase()
    sr17 = db.get_compound("SR-17018")
    sr14 = db.get_compound("SR-14968")
    bup = db.get_compound("Buprenorphine")
    
    model = HepatotoxicityModel([sr17, sr14, bup])
    
    # Simulate 90 days on our protocol
    alt_levels = model.simulate_liver_stress(doses=[30.0, 40.0, 2.0], days=90)
    
    avg_alt = np.mean(alt_levels)
    max_alt = np.max(alt_levels)
    dili_cases = sum(1 for alt in alt_levels if alt > 150) # 3x upper limit of normal
    
    print(f"90-Day Hepatotoxicity Simulation (N=1000)")
    print(f"Average ALT Level: {avg_alt:.1f} U/L (Normal: 7-55 U/L)")
    print(f"Max ALT Level observed: {max_alt:.1f} U/L")
    print(f"Severe DILI Cases (>150 U/L): {dili_cases} / 1000 ({dili_cases/10:.1f}%)")
