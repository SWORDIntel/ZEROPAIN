import sys
from pathlib import Path
sys.path.insert(0, "/fast/Main Workspace/ZEROPAIN/src")

from dsmil_adapter import _load_calibrated_tolerance_config
config = _load_calibrated_tolerance_config()

print("Config:")
print(config)

from tolerance_models import make_addiction_model
ac = config.get("addiction", {})
model = make_addiction_model(ac)
print("Model:")
print(type(model))
print(vars(model))

# Also test a step of dopamine
from tolerance_models import AddictionState
state = AddictionState()
state = model.update(state, 100.0, 0.1)
print("Risk:", state.level)
