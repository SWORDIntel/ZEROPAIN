# ZeroPain v4.0 - Quick Start Guide
## Professional Molecular Therapeutics Platform

---

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/SWORDIntel/ZEROPAIN.git
cd ZEROPAIN
```

### 2. Create Virtual Environment
```bash
python3 -m venv zeropain_env
source zeropain_env/bin/activate  # On Windows: zeropain_env\Scripts\activate
```

### 3. Install Base Requirements
```bash
# Install core dependencies
pip install -r requirements/base.txt

# Install web interface
pip install -r requirements/web.txt
```

### 4. Install Molecular Modeling (Optional but Recommended)
```bash
# RDKit requires conda
conda install -c conda-forge rdkit openbabel

# Or use pip for some components
pip install -r requirements/molecular.txt
```

### 5. Install Intel AI Acceleration (Optional)
```bash
# For Intel Arc GPU / NPU
pip install -r requirements/intel.txt

# Download and install OpenVINO
# https://www.intel.com/content/www/us/en/developer/tools/openvino-toolkit/download.html
```

---

## 🎯 Quick Test

### Test Molecular Analysis
```bash
python zeropain/molecular/structure.py
```

### Test Intel AI Inference
```bash
python zeropain/molecular/intel_ai.py
```

### Test Docking Module
```bash
python zeropain/molecular/docking.py
```

---

## 🌐 Launch Web Interface

### 1. Start API Backend
```bash
cd zeropain/api
python main.py
```

API will be available at:
- **API Docs**: http://localhost:8000/api/docs
- **API Server**: http://localhost:8000

### 2. Open Web Frontend
```bash
# Open in browser
open web/frontend/public/index.html

# Or use Python server
cd web/frontend/public
python -m http.server 3000
# Then visit: http://localhost:3000
```

---

## 📊 Example Usage

### Example 1: Analyze a Compound
```python
from zeropain.molecular.structure import from_smiles

# Morphine
morphine_smiles = "CN1CC[C@]23[C@H]4Oc5c(O)ccc(C[C@@H]1[C@@H]2C=C[C@@H]4O)c35"
struct = from_smiles(morphine_smiles, "Morphine", generate_3d=True)

print(f"Molecular Weight: {struct.mol_weight:.2f}")
print(f"LogP: {struct.logp:.2f}")
print(f"Drug-like: {struct.is_drug_like()}")
```

### Example 2: Molecular Docking
```python
from zeropain.molecular.docking import AutoDockVina

docking = AutoDockVina()
result = docking.dock(
    ligand_smiles=morphine_smiles,
    compound_name="Morphine",
    receptor="MOR"
)

print(f"Binding Affinity: {result.binding_affinity:.2f} kcal/mol")
print(f"Predicted Ki: {result.ki_predicted:.2f} nM")
```

### Example 3: Intel AI ADMET Prediction
```python
from zeropain.molecular.intel_ai import IntelAIMolecularPredictor
from zeropain.molecular.structure import from_smiles

predictor = IntelAIMolecularPredictor()

struct = from_smiles(morphine_smiles, "Morphine")
admet = predictor.predict_admet(struct.to_dict())

print(f"Bioavailability: {admet.bioavailability*100:.1f}%")
print(f"Half-life: {admet.half_life:.1f} hours")
print(f"BBB Permeability: {admet.bbb_permeability*100:.1f}%")
```

### Example 4: API Usage
```python
import requests

# Analyze molecule via API
response = requests.post(
    "http://localhost:8000/api/molecular/analyze",
    json={
        "name": "Morphine",
        "smiles": morphine_smiles
    }
)

data = response.json()
print(f"Molecular Weight: {data['molecular_weight']}")
```

---

## 🧪 Run Complete Pipeline

### Using Python API
```python
from zeropain.molecular.docking import AutoDockVina
from zeropain.molecular.intel_ai import IntelAIMolecularPredictor
from zeropain.molecular.structure import from_smiles

# 1. Analyze structure
struct = from_smiles(your_smiles, "MyCompound")

# 2. Predict ADMET
predictor = IntelAIMolecularPredictor()
admet = predictor.predict_admet(struct.to_dict())

# 3. Dock to receptor
docking = AutoDockVina()
result = docking.dock(your_smiles, "MyCompound", "MOR")

# 4. Analyze results
print(f"Safety Score: {struct.calculate_safety_score()}")
print(f"Binding Affinity: {result.binding_affinity} kcal/mol")
print(f"Bioavailability: {admet.bioavailability*100}%")
```

---

## 🎨 Web Interface Features

### TEMPEST Class C Theme
- **Dark tactical interface** with grid overlay
- **Real-time status indicators**
- **High-contrast data visualization**
- **Secure, classified aesthetic**

### Available Modules
1. **Compound Browser** - Search and analyze compounds
2. **Molecular Docking** - Protein-ligand binding prediction
3. **Protocol Optimization** - Multi-compound protocol design
4. **Patient Simulation** - Large-scale population studies
5. **Data Analysis** - Statistical analysis and reporting
6. **Intel AI Inference** - ADMET and toxicity prediction

---

## 🔧 Configuration

### Intel Acceleration
Create `.env` file:
```bash
USE_INTEL_ACCELERATION=true
OPENVINO_DEVICE=AUTO  # AUTO, NPU, GPU, CPU
```

### API Configuration
```bash
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=4
LOG_LEVEL=info
```

---

## 📦 Download Receptor Structures

```bash
# Download PDB files for opioid receptors
cd data/receptors

# μ-opioid receptor (MOR) - PDB: 4DKL
wget https://files.rcsb.org/download/4DKL.pdb

# δ-opioid receptor (DOR) - PDB: 4N6H
wget https://files.rcsb.org/download/4N6H.pdb

# κ-opioid receptor (KOR) - PDB: 4DJH
wget https://files.rcsb.org/download/4DJH.pdb

# Convert to PDBQT format (requires MGLTools or Open Babel)
# obabel 4DKL.pdb -O mor.pdbqt -p 7.4
```

---

## 🧬 Add Custom Compounds

### Via Python
```python
from zeropain.core.compounds import CompoundProfile

custom = CompoundProfile(
    name="MyCompound",
    ki_orthosteric=25.0,  # nM
    ki_allosteric1=float('inf'),
    ki_allosteric2=float('inf'),
    g_protein_bias=6.0,
    beta_arrestin_bias=0.3,
    t_half=8.0,  # hours
    bioavailability=0.75,
    intrinsic_activity=0.45,
    tolerance_rate=0.2,
    prevents_withdrawal=True
)

# Save to database
custom.save()
```

### Via Web Interface
1. Navigate to "Compound Browser"
2. Click "Add Custom Compound"
3. Enter molecular properties
4. Upload SMILES or draw structure
5. Run docking and ADMET prediction
6. Save to database

---

## 📊 Performance Benchmarks

On 16-core system with Intel NPU:
- **Molecular Docking**: < 5 minutes per compound
- **ADMET Prediction**: 1000+ predictions/second
- **Patient Simulation**: 100k patients in ~2 minutes
- **Protocol Optimization**: 1000 patients/second

---

## 🆘 Troubleshooting

### RDKit Not Found
```bash
# Install via conda (recommended)
conda install -c conda-forge rdkit

# Or use pip (limited features)
pip install rdkit-pypi
```

### AutoDock Vina Not Found
```bash
# Download from GitHub
wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64
chmod +x vina_1.2.5_linux_x86_64
sudo mv vina_1.2.5_linux_x86_64 /usr/local/bin/vina
```

### Intel Optimizations Not Working
- Verify Intel Extension for PyTorch: `python -c "import intel_extension_for_pytorch as ipex; print(ipex.__version__)"`
- Check OpenVINO: `python -c "from openvino.runtime import Core; print(Core().available_devices)"`
- System will fall back to CPU if hardware not detected

### API Not Starting
```bash
# Check if port 8000 is available
lsof -i :8000

# Use different port
uvicorn zeropain.api.main:app --port 8080
```

---

## 📚 Next Steps

1. **Read Full Documentation**: `docs/api/`
2. **Try Tutorial Notebooks**: `docs/tutorials/`
3. **View Example Workflows**: `docs/guides/`
4. **Join Development**: See `CONTRIBUTING.md`

---

## 🔐 Security Note

This is a TEMPEST Class C system. Ensure:
- No unauthorized access
- Encrypted data transmission
- Secure compound database
- Audit logging enabled

---

**ZeroPain Therapeutics v4.0**
Zero Addiction • Zero Tolerance • Zero Withdrawal
