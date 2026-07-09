import re

def patch_file():
    with open('src/patient_simulation.py', 'r') as f:
        content = f.read()

    # Find the imports and add dili_modeling
    import_match = re.search(r'from typing import .*?\n', content)
    if import_match:
        content = content[:import_match.end()] + "from dili_modeling import HepatotoxicityModel\n" + content[import_match.end():]

    # Find where metrics are aggregated and add hepatotoxicity tracking
    metrics_match = re.search(r'        results = {\n            "simulation": {', content)
    if metrics_match:
        # Before metrics, instantiate and run DILI model
        dili_code = """
        # --- Hepatotoxicity (DILI) Tracking ---
        dili_model = HepatotoxicityModel(self.compounds)
        alt_levels = dili_model.simulate_liver_stress(self.doses, self.duration_days)
        avg_alt = np.mean(alt_levels)
        severe_dili_rate = sum(1 for alt in alt_levels if alt > 150) / len(alt_levels)
        """
        content = content[:metrics_match.start()] + dili_code + content[metrics_match.start():]
        
        # Add to results dict
        insert_idx = content.find('"n_patients":', metrics_match.start())
        if insert_idx != -1:
            content = content[:insert_idx] + '"avg_alt_level": float(avg_alt),\n            "severe_dili_rate": float(severe_dili_rate),\n            ' + content[insert_idx:]

    with open('src/patient_simulation.py', 'w') as f:
        f.write(content)
    print("Patched patient_simulation.py")

patch_file()
