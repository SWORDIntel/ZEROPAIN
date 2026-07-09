import sys
import os
sys.path.insert(0, os.path.abspath('src'))
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()
compounds = db.list_compounds()

print("Expanded search for potential SR-17018 replacements:")
for name in compounds:
    c = db.get_compound(name)
    if not c: continue
    
    notes_lower = c.mechanism_notes.lower()
    
    # Check for similar properties
    if "tolerance" in notes_lower or "withdrawal" in notes_lower or c.reverses_tolerance or c.prevents_withdrawal:
        if name not in ['Morphine', 'Oxycodone', 'Fentanyl', 'Tapentadol', 'Tramadol', 'SR-17018']:
            print(f"\n--- {c.name} ---")
            print(f"Notes: {c.mechanism_notes}")
