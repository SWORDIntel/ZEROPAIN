# ZeroPain Pipeline - Usage Guide

## Overview

The ZeroPain Therapeutics Framework now includes a complete pipeline for local execution with:
- **Custom compound integration** - Build and test your own opioid compounds
- **Compound selection** - Choose from extensive database with Ki and receptor binding data
- **Local running** - No cloud dependencies, runs entirely on your machine
- **Intel NPU/Arc GPU acceleration** - Hardware acceleration for large-scale analysis
- **Full TUI interface** - Interactive terminal interface for ease of use
- **Multi-compound optimization** - Optimize protocols with multiple compounds

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For Intel NPU/GPU acceleration (optional)
pip install intel-extension-for-pytorch openvino
```

### Launch Interactive TUI

The easiest way to use ZeroPain is through the interactive TUI:

```bash
python src/zeropain_pipeline.py --tui
```

Or use the TUI directly:

```bash
python src/zeropain_tui.py
```

### Command Line Usage

#### 1. Browse Compounds

```bash
# Run analysis module to see available compounds
python src/opioid_analysis_tools.py
```

#### 2. Run Full Pipeline

Analyze → Optimize → Simulate in one command:

```bash
python src/zeropain_pipeline.py --full \
  --compounds SR-17018 SR-14968 Oxycodone \
  --n-patients-opt 1000 \
  --n-patients-sim 100000 \
  --output-dir results/
```

#### 3. Optimization Only

```bash
python src/zeropain_pipeline.py --optimize \
  --compounds SR-17018 Oxycodone \
  --n-patients-opt 1000 \
  --max-iterations 100 \
  --intel  # Enable Intel acceleration
```

#### 4. Simulation Only

```bash
# With protocol file
python src/zeropain_pipeline.py --simulate \
  --protocol optimal_protocol.json \
  --n-patients-sim 100000

# With direct compounds
python src/zeropain_pipeline.py --simulate \
  --compounds SR-17018 Oxycodone \
  --n-patients-sim 10000
```

#### 5. Compound Analysis

```bash
python src/zeropain_pipeline.py --analyze \
  --compounds Morphine Fentanyl Buprenorphine PZM21
```

## Custom Compound Integration

### Using the TUI

1. Launch TUI: `python src/zeropain_pipeline.py --tui`
2. Select `[3] Custom Compound Builder`
3. Enter compound parameters:
   - **Binding affinities** (Ki values for orthosteric and allosteric sites)
   - **Signaling bias** (G-protein and β-arrestin pathways)
   - **Pharmacokinetics** (half-life, bioavailability)
   - **Functional properties** (intrinsic activity, tolerance rate)
4. Save compound to database

### Programmatically

```python
from opioid_analysis_tools import CompoundDatabase, CompoundProfile

# Create custom compound
custom = CompoundProfile(
    name="MyCompound",
    ki_orthosteric=50.0,        # nM
    ki_allosteric1=float('inf'),
    ki_allosteric2=float('inf'),
    g_protein_bias=6.0,
    beta_arrestin_bias=0.3,
    t_half=8.0,                 # hours
    bioavailability=0.75,
    intrinsic_activity=0.45,
    tolerance_rate=0.2,
    prevents_withdrawal=True,
    reverses_tolerance=False
)

# Add to database
db = CompoundDatabase()
db.add_custom_compound(custom)

# Save for future use
db.export_to_json('custom_compounds.json')
```

## Compound Selection by Ki Values

### Filter by Ki Range

Using the TUI:
1. `[1] Browse Compounds`
2. `[1] Filter by Ki range`
3. Select binding site (orthosteric, allosteric1, allosteric2)
4. Enter range (e.g., 0-50 nM for high affinity)

Programmatically:

```python
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()

# Find high-affinity orthosteric binders
high_affinity = db.filter_by_ki_range(0, 20, site='orthosteric')
for compound in high_affinity:
    print(f"{compound.name}: Ki = {compound.ki_orthosteric:.2f} nM")

# Find allosteric modulators
allosteric = db.filter_by_ki_range(10, 100, site='allosteric1')
```

### Filter by Safety Score

```python
# Get only safe compounds (score ≥ 80)
safe_compounds = db.filter_by_safety(min_score=80.0)

for compound in safe_compounds:
    print(f"{compound.name}: Safety = {compound.calculate_safety_score():.1f}")
```

## Intel NPU/Arc GPU Acceleration

### Enable Acceleration

Via command line:
```bash
python src/zeropain_pipeline.py --optimize \
  --compounds SR-17018 SR-14968 \
  --intel
```

Via TUI:
1. Launch TUI
2. Go to `[6] Settings`
3. Toggle Intel acceleration

Programmatically:
```python
from opioid_optimization_framework import ProtocolOptimizer

optimizer = ProtocolOptimizer(
    compound_database=db,
    use_intel_acceleration=True  # Enable Intel NPU/GPU
)
```

### Supported Intel Hardware

- **Intel Arc GPUs** - Using Intel Extension for PyTorch
- **Intel NPUs** - Using OpenVINO runtime
- **Automatic detection** - Falls back to CPU if hardware not available

The framework will automatically detect and use available Intel hardware:
```
✓ Intel Extension for PyTorch enabled
✓ OpenVINO available. Devices: NPU, GPU, CPU
✓ Using Intel NPU for acceleration
```

## Available Compounds Database

### Standard Compounds

The database includes:

**FDA-Approved:**
- Morphine, Oxycodone, Fentanyl
- Buprenorphine, Tapentadol, Tramadol
- Oliceridine (TRV130), Nalbuphine

**Experimental:**
- SR-17018 (allosteric modulator, reverses tolerance)
- SR-14968 (highly biased agonist)
- PZM21 (computationally designed)
- Mitragynine (natural compound)

### Compound Properties

Each compound includes:
- **Ki values** - Binding affinities (nM) for 3 sites
- **Signaling bias** - G-protein and β-arrestin pathway selectivity
- **Pharmacokinetics** - Half-life, bioavailability
- **Functional properties** - Efficacy, tolerance rate
- **Special flags** - Withdrawal prevention, tolerance reversal

## Protocol Optimization

### Basic Optimization

```python
from opioid_optimization_framework import run_local_optimization

result = run_local_optimization(
    compounds=['SR-17018', 'SR-14968', 'Oxycodone'],
    n_patients=1000,
    max_iterations=100,
    use_intel=True
)

print(f"Success rate: {result.success_rate*100:.2f}%")
print(f"Optimal doses: {result.optimal_protocol.doses}")
```

### Advanced Configuration

```python
from opioid_optimization_framework import ProtocolOptimizer, ProtocolConfig
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()
optimizer = ProtocolOptimizer(
    db,
    use_multiprocessing=True,
    use_intel_acceleration=True
)

result = optimizer.optimize_protocol(
    base_compounds=['SR-17018', 'Oxycodone'],
    n_patients=5000,
    max_iterations=200,
    target_success_rate=0.75
)
```

## Patient Simulation

### Large-Scale Simulation (100k patients)

```python
from patient_simulation_100k import run_100k_simulation
from opioid_optimization_framework import ProtocolConfig

protocol = ProtocolConfig(
    compounds=['SR-17018', 'SR-14968', 'Oxycodone'],
    doses=[16.17, 25.31, 5.07],
    frequencies=[2, 1, 4]
)

results = run_100k_simulation(protocol)

print(f"Success rate: {results['success_rate']*100:.2f}%")
print(f"Tolerance rate: {results['tolerance_rate']*100:.2f}%")
```

### Custom Population Size

```python
from patient_simulation_100k import PopulationSimulation
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()
simulation = PopulationSimulation(db, use_multiprocessing=True)

results = simulation.run_simulation(
    protocol,
    n_patients=250000,  # Quarter million patients
    duration_days=90
)
```

## Output Files

### Results Directory Structure

```
results/
├── optimization_results.json
├── simulation_results.json
├── pipeline_complete.json
└── custom_compounds.json
```

### File Formats

All results are saved as JSON for easy parsing:

```json
{
  "optimal_protocol": {
    "compounds": ["SR-17018", "Oxycodone"],
    "doses": [16.2, 5.1],
    "frequencies": [2, 4]
  },
  "metrics": {
    "success_rate": 0.72,
    "tolerance_rate": 0.04,
    "addiction_rate": 0.02,
    "withdrawal_rate": 0.00
  }
}
```

## Performance Tips

### For Large Simulations (>50k patients)

1. **Enable multiprocessing** (default)
2. **Use Intel acceleration** if available
3. **Reduce iterations** during testing (use 20-50)
4. **Start with smaller population** (1k-10k) for validation

### Optimization Parameters

- **n_patients_opt**: 500-2000 (balance speed vs accuracy)
- **max_iterations**: 50-200 (more = better results but slower)
- **n_patients_sim**: 10k-500k (larger = more reliable statistics)

### Hardware Requirements

- **Minimum**: 4 cores, 8GB RAM
- **Recommended**: 8+ cores, 16GB RAM
- **Optimal**: Intel NPU/Arc GPU, 16+ cores, 32GB RAM

## Examples

### Example 1: Find Safest Compound

```python
from opioid_analysis_tools import CompoundDatabase

db = CompoundDatabase()
compounds = db.filter_by_safety(min_score=85.0)

best = max(compounds, key=lambda c: c.calculate_safety_score())
print(f"Safest compound: {best.name}")
print(f"Safety score: {best.calculate_safety_score():.1f}")
print(f"Bias ratio: {best.get_bias_ratio():.1f}x")
```

### Example 2: Optimize for Zero Tolerance

```python
# Select compounds with tolerance-preventing properties
compounds = ['SR-17018', 'Buprenorphine', 'PZM21']

result = run_local_optimization(
    compounds,
    n_patients=2000,
    max_iterations=150
)

if result.tolerance_rate < 0.05:
    print("✓ Achieved zero tolerance goal!")
```

### Example 3: Custom Biased Agonist

```python
# Design a safer alternative to morphine
safer_morphine = CompoundProfile(
    name="SaferMorphine",
    ki_orthosteric=120.0,      # Weaker binding
    ki_allosteric1=float('inf'),
    ki_allosteric2=float('inf'),
    g_protein_bias=8.0,         # High bias
    beta_arrestin_bias=0.2,     # Low arrestin
    t_half=5.0,
    bioavailability=0.8,
    intrinsic_activity=0.4,     # Partial agonist
    tolerance_rate=0.2,
    prevents_withdrawal=False,
    reverses_tolerance=False
)

db.add_custom_compound(safer_morphine)

# Test in optimization
result = run_local_optimization(
    ['SaferMorphine', 'SR-17018'],
    n_patients=1000
)
```

## Troubleshooting

### Import Errors

If you get import errors, ensure all dependencies are installed:
```bash
pip install numpy scipy matplotlib rich
```

### Intel Acceleration Not Working

Check if Intel packages are installed:
```bash
pip install intel-extension-for-pytorch openvino
```

The system will automatically fall back to CPU if Intel hardware is not detected.

### Slow Performance

- Enable multiprocessing (default)
- Reduce patient count for testing
- Use Intel acceleration if available
- Close other applications to free RAM

### Memory Issues

For very large simulations (>500k patients):
- Use batch processing
- Increase system swap space
- Use a machine with more RAM

## API Reference

See individual module docstrings for detailed API documentation:

```python
help(CompoundDatabase)
help(ProtocolOptimizer)
help(PopulationSimulation)
```

## Support

For issues or questions:
- Check documentation in `doc/` directory
- Review compound tuning guide: `doc/compound_tuning_guide.md`
- See README.md for project overview

---

**ZeroPain Therapeutics Framework v3.0**
Zero Addiction • Zero Tolerance • Zero Withdrawal
