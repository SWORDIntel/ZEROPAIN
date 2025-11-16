#!/bin/bash
# ZeroPain v4.0 Environment Setup Script
# Automated installation and configuration

set -e  # Exit on error

echo "================================================================"
echo "ZeroPain Therapeutics Framework v4.0 - Environment Setup"
echo "================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${CYAN}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo -e "${RED}Error: Python 3.8+ required. Found: $python_version${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $python_version${NC}"

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${CYAN}Creating virtual environment...${NC}"
    python3 -m venv zeropain_env
    source zeropain_env/bin/activate
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Already in virtual environment${NC}"
fi

# Upgrade pip
echo -e "${CYAN}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓ Pip upgraded${NC}"

# Install base requirements
echo -e "${CYAN}Installing base requirements...${NC}"
pip install -r requirements/base.txt
echo -e "${GREEN}✓ Base requirements installed${NC}"

# Install web requirements
echo -e "${CYAN}Installing web interface requirements...${NC}"
pip install -r requirements/web.txt
echo -e "${GREEN}✓ Web requirements installed${NC}"

# Ask about optional components
echo ""
read -p "Install molecular modeling tools? (requires conda) [y/N]: " install_molecular
if [[ $install_molecular =~ ^[Yy]$ ]]; then
    if command -v conda &> /dev/null; then
        echo -e "${CYAN}Installing RDKit and OpenBabel...${NC}"
        conda install -y -c conda-forge rdkit openbabel
        pip install -r requirements/molecular.txt
        echo -e "${GREEN}✓ Molecular tools installed${NC}"
    else
        echo -e "${RED}Warning: conda not found. Skipping molecular tools.${NC}"
        echo "Install conda from: https://docs.conda.io/en/latest/miniconda.html"
    fi
fi

# Intel optimizations
echo ""
read -p "Install Intel AI acceleration? (for Intel NPU/GPU) [y/N]: " install_intel
if [[ $install_intel =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Installing Intel optimizations...${NC}"
    pip install -r requirements/intel.txt
    echo -e "${GREEN}✓ Intel optimizations installed${NC}"
fi

# Database
echo ""
read -p "Install database support? [y/N]: " install_db
if [[ $install_db =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Installing database support...${NC}"
    pip install -r requirements/database.txt
    echo -e "${GREEN}✓ Database support installed${NC}"
fi

# Development tools
echo ""
read -p "Install development tools? [y/N]: " install_dev
if [[ $install_dev =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Installing development tools...${NC}"
    pip install -r requirements/dev.txt
    echo -e "${GREEN}✓ Development tools installed${NC}"
fi

# Create data directories
echo -e "${CYAN}Creating data directories...${NC}"
mkdir -p data/{compounds,receptors,protocols,results}
mkdir -p web/static/{pdb,images}
echo -e "${GREEN}✓ Directories created${NC}"

# Download receptor structures (optional)
echo ""
read -p "Download opioid receptor structures? (~50MB) [y/N]: " download_receptors
if [[ $download_receptors =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}Downloading receptor PDB files...${NC}"
    cd data/receptors

    # MOR (μ-opioid)
    echo "Downloading MOR (4DKL)..."
    wget -q https://files.rcsb.org/download/4DKL.pdb -O mor.pdb

    # DOR (δ-opioid)
    echo "Downloading DOR (4N6H)..."
    wget -q https://files.rcsb.org/download/4N6H.pdb -O dor.pdb

    # KOR (κ-opioid)
    echo "Downloading KOR (4DJH)..."
    wget -q https://files.rcsb.org/download/4DJH.pdb -O kor.pdb

    cd ../..
    echo -e "${GREEN}✓ Receptors downloaded${NC}"
fi

# Test installation
echo ""
echo -e "${CYAN}Testing installation...${NC}"

# Test imports
python3 -c "import numpy; import scipy; import pandas" && echo -e "${GREEN}✓ Scientific libraries OK${NC}" || echo -e "${RED}✗ Scientific libraries failed${NC}"
python3 -c "import fastapi; import uvicorn" && echo -e "${GREEN}✓ Web framework OK${NC}" || echo -e "${RED}✗ Web framework failed${NC}"

# Test ZeroPain modules
python3 -c "from zeropain.molecular import structure" && echo -e "${GREEN}✓ Molecular module OK${NC}" || echo -e "${RED}✗ Molecular module failed${NC}"

echo ""
echo "================================================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "================================================================"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source zeropain_env/bin/activate"
echo "  2. Read quickstart: cat QUICKSTART.md"
echo "  3. Start API: python zeropain/api/main.py"
echo "  4. Open web UI: open web/frontend/public/index.html"
echo ""
echo "Documentation: docs/"
echo "Examples: docs/tutorials/"
echo ""
echo -e "${CYAN}Zero Addiction • Zero Tolerance • Zero Withdrawal${NC}"
echo "================================================================"
