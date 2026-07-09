import re

def patch_file():
    with open('src/patient_simulation.py', 'r') as f:
        content = f.read()

    # The previous patch might not have injected the keys correctly into the dictionary structure
    # Let's fix the output dict injection
    
    # We want to find:
    # "nt_substance_p": float(np.mean(neuro_substance_p) if neuro_substance_p else 0),
    # "pain_score_std": float(np.std(pain_scores) if pain_scores else 0),
    
    search_str = '"nt_substance_p": float(np.mean(neuro_substance_p) if neuro_substance_p else 0),'
    
    if search_str in content:
        replace_str = search_str + '\n            "avg_alt_level": float(avg_alt),\n            "severe_dili_rate": float(severe_dili_rate),'
        content = content.replace(search_str, replace_str)
        
        with open('src/patient_simulation.py', 'w') as f:
            f.write(content)
        print("Patched output dict successfully.")
    else:
        print("Could not find injection point.")

patch_file()
