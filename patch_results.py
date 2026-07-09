import re

def patch_file():
    with open('src/patient_simulation.py', 'r') as f:
        content = f.read()

    # Find where the results dictionary is returned
    search_str = '"nt_substance_p": float(np.mean(neuro_substance_p) if neuro_substance_p else 0),'
    
    # Check if we already patched the DILI modeling in
    if 'avg_alt' in content and 'avg_alt_level' not in content:
        # It means dili_model is initialized and avg_alt is calculated but not injected into the final dict
        if search_str in content:
            replace_str = search_str + '\n            "avg_alt_level": float(avg_alt),\n            "severe_dili_rate": float(severe_dili_rate),'
            content = content.replace(search_str, replace_str)
            with open('src/patient_simulation.py', 'w') as f:
                f.write(content)
            print("Successfully patched results dict.")
        else:
            print("Could not find nt_substance_p")
            
patch_file()
