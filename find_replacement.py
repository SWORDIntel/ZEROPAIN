import sys
import os
sys.path.insert(0, os.path.abspath('src'))
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()
compounds = db.list_compounds()

print("Finding potential replacements for SR-17018 based on tolerance reversal / withdrawal prevention:")
for name in compounds:
    c = db.get_compound(name)
    if not c: continue
    
    # Check for similar properties
    if c.reverses_tolerance or c.prevents_withdrawal or c.tolerance_rate <= 0.2:
        print(f"\n--- {c.name} ---")
        print(f"Tolerance Rate: {c.tolerance_rate}")
        print(f"Reverses Tolerance: {c.reverses_tolerance}")
        print(f"Prevents Withdrawal: {c.prevents_withdrawal}")
        print(f"Activities: {c.pharmacological_activities}")
        print(f"Notes: {c.mechanism_notes}")
