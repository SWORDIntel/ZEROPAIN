#!/usr/bin/env bash
# IDENTIFIER: zeropain_complete_installer
# Complete installation script with all enhancements
set -euo pipefail

# Enhanced dark theme colors
BLACK='\033[0;30m'
RED='\033[0;91m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
BLUE='\033[0;94m'
PURPLE='\033[0;95m'
CYAN='\033[0;96m'
WHITE='\033[0;97m'
DARK_GRAY='\033[0;90m'
LIGHT_GRAY='\033[0;37m'
BG_BLACK='\033[40m'
BG_BLUE='\033[44m'
BOLD='\033[1m'
NC='\033[0m'

# Thermal monitoring variables
THERMAL_LIMIT=100
THERMAL_TARGET=80
THERMAL_THROTTLE=103
INSTALL_MODE="standard"

# ==============================================================================
# FUNCTIONS
# ==============================================================================

# Check system temperature
check_temperature() {
    local temp=50  # Default safe value
    
    # Try multiple methods to get CPU temperature
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print int($1/1000)}')
    elif command -v sensors &> /dev/null; then
        temp=$(sensors | grep -oP 'Core 0:\s+\+\K[0-9]+' | head -1)
    fi
    
    echo $temp
}

# Thermal-aware compilation
thermal_compile() {
    local temp=$(check_temperature)
    local jobs="-j$(nproc)"
    
    if [ $temp -gt $THERMAL_THROTTLE ]; then
        echo -e "${RED}âš  CRITICAL: CPU temperature ${temp}Â°C - Emergency throttling!${NC}"
        jobs="-j2"
        sudo cpupower frequency-set -g powersave 2>/dev/null || true
        sleep 5  # Cool down period
    elif [ $temp -gt $THERMAL_TARGET ]; then
        echo -e "${YELLOW}âš  WARNING: CPU temperature ${temp}Â°C - Reducing parallelism${NC}"
        jobs="-j$(($(nproc)/2))"
    else
        echo -e "${GREEN}âœ“ CPU temperature ${temp}Â°C - Full performance mode${NC}"
    fi
    
    make clean 2>/dev/null || true
    make $jobs all
}

# Detect hardware capabilities
detect_hardware() {
    echo -e "${CYAN}Detecting hardware capabilities...${NC}"
    
    # CPU detection
    CPU_MODEL=$(lscpu | grep "Model name" | cut -d: -f2 | xargs)
    CPU_CORES=$(nproc)
    CPU_ARCH=$(uname -m)
    
    # Check for AVX/AVX2 support
    AVX_SUPPORT="no"
    if grep -q avx2 /proc/cpuinfo; then
        AVX_SUPPORT="AVX2"
    elif grep -q avx /proc/cpuinfo; then
        AVX_SUPPORT="AVX"
    fi
    
    # Check for NPU/GPU
    NPU_AVAILABLE="no"
    if lspci | grep -qi "VPU\|Neural\|Movidius"; then
        NPU_AVAILABLE="Intel NPU"
    elif lspci | grep -qi "NVIDIA"; then
        NPU_AVAILABLE="NVIDIA GPU"
    elif lspci | grep -qi "AMD.*Radeon"; then
        NPU_AVAILABLE="AMD GPU"
    elif lspci | grep -qi "Intel.*Graphics"; then
        NPU_AVAILABLE="Intel GPU"
    fi
    
    # Memory check
    TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
    
    echo -e "${GREEN}Hardware Profile:${NC}"
    echo -e "  CPU: ${WHITE}$CPU_MODEL${NC}"
    echo -e "  Cores: ${WHITE}$CPU_CORES${NC}"
    echo -e "  Architecture: ${WHITE}$CPU_ARCH${NC}"
    echo -e "  SIMD Support: ${WHITE}$AVX_SUPPORT${NC}"
    echo -e "  Accelerator: ${WHITE}$NPU_AVAILABLE${NC}"
    echo -e "  RAM: ${WHITE}${TOTAL_RAM}GB${NC}"
    echo ""
}

# Install dependencies based on OS
install_dependencies() {
    echo -e "${CYAN}Installing system dependencies...${NC}"
    
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y \
            build-essential cmake git \
            libomp-dev libopenblas-dev \
            python3-dev python3-pip python3-venv \
            libglfw3-dev libglew-dev \
            lm-sensors cpufrequtils \
            htop iotop \
            pkg-config wget curl
            
        # OpenVINO for Ubuntu
        if [ "$NPU_AVAILABLE" != "no" ]; then
            echo -e "${CYAN}Installing OpenVINO...${NC}"
            wget -q https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
            sudo apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
            echo "deb https://apt.repos.intel.com/openvino/2023 ubuntu20 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2023.list
            sudo apt update
            sudo apt install -y intel-openvino-dev-ubuntu20-2023.0.0 || true
        fi
        
    elif command -v yum &> /dev/null; then
        # RHEL/CentOS/Fedora
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y \
            gcc-c++ cmake git \
            openblas-devel \
            python3-devel python3-pip \
            glfw-devel glew-devel \
            lm_sensors cpupower \
            htop iotop
            
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        sudo pacman -Syu --noconfirm
        sudo pacman -S --noconfirm \
            base-devel cmake git \
            openblas \
            python python-pip \
            glfw glew \
            lm_sensors cpupower \
            htop iotop
    fi
    
    # Install Python packages
    echo -e "${CYAN}Installing Python packages...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip wheel setuptools
    pip install -r requirements.txt 2>/dev/null || pip install \
        numpy pandas scipy matplotlib seaborn \
        torch scikit-learn plotly dash \
        tqdm colorlog rich psutil
}

# ==============================================================================
# ANIMATED BANNER
# ==============================================================================

show_banner() {
    clear
    echo -e "${DARK_GRAY}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
    echo -e "${CYAN}"
    cat << 'EOF'
    â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ•—   â–ˆâ–ˆâ•—
    â•šâ•â•â–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•”â•â•â•â•â•â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ•‘
      â–ˆâ–ˆâ–ˆâ•”â• â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â–ˆâ–ˆâ•— â–ˆâ–ˆâ•‘
     â–ˆâ–ˆâ–ˆâ•”â•  â–ˆâ–ˆâ•”â•â•â•  â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â•â• â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘
    â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘ â•šâ–ˆâ–ˆâ–ˆâ–ˆâ•‘
    â•šâ•â•â•â•â•â•â•â•šâ•â•â•â•â•â•â•â•šâ•â•  â•šâ•â• â•šâ•â•â•â•â•â• â•šâ•â•     â•šâ•â•  â•šâ•â•â•šâ•â•â•šâ•â•  â•šâ•â•â•â•
EOF
    echo -e "${NC}"
    echo -e "${PURPLE}         Framework v3.0 - Complete Installation System${NC}"
    echo -e "${DARK_GRAY}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
    echo ""
    
    # Animated loading bar
    echo -ne "${CYAN}Initializing "
    for i in {1..10}; do
        echo -ne "â–ˆ"
        sleep 0.1
    done
    echo -e " ${GREEN}âœ“${NC}"
    echo ""
}

# ==============================================================================
# MAIN INSTALLATION MENU
# ==============================================================================

show_menu() {
    echo -e "${CYAN}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
    echo -e "${CYAN}â•‘          Installation Mode Selection                 â•‘${NC}"
    echo -e "${CYAN}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
    echo ""
    echo -e "${WHITE}[1]${NC} ${GREEN}Quick Install${NC} - Core components only (5 min)"
    echo -e "${WHITE}[2]${NC} ${BLUE}Standard Install${NC} - Recommended setup (10 min)"
    echo -e "${WHITE}[3]${NC} ${PURPLE}Complete Install${NC} - All features + NPU (15 min)"
    echo -e "${WHITE}[4]${NC} ${YELLOW}Developer Install${NC} - With debug tools (20 min)"
    echo -e "${WHITE}[5]${NC} ${RED}Custom Install${NC} - Choose components"
    echo ""
    read -p "Select installation mode [1-5]: " -n 1 -r
    echo ""
    
    case $REPLY in
        1) INSTALL_MODE="quick" ;;
        2) INSTALL_MODE="standard" ;;
        3) INSTALL_MODE="complete" ;;
        4) INSTALL_MODE="developer" ;;
        5) INSTALL_MODE="custom" ;;
        *) INSTALL_MODE="standard" ;;
    esac
}

# ==============================================================================
# INSTALLATION STEPS
# ==============================================================================

perform_installation() {
    local start_time=$(date +%s)
    
    # Step 1: System preparation
    echo -e "\n${PURPLE}[Step 1/7]${WHITE} Preparing system...${NC}"
    detect_hardware
    
    # Step 2: Check thermal status
    echo -e "${PURPLE}[Step 2/7]${WHITE} Checking thermal status...${NC}"
    CURRENT_TEMP=$(check_temperature)
    echo -e "Current CPU temperature: ${CYAN}${CURRENT_TEMP}Â°C${NC}"
    
    if [ $CURRENT_TEMP -gt $THERMAL_TARGET ]; then
        echo -e "${YELLOW}âš  CPU is warm. Installation will use reduced parallelism.${NC}"
    fi
    
    # Step 3: Install dependencies
    echo -e "\n${PURPLE}[Step 3/7]${WHITE} Installing dependencies...${NC}"
    if [ "$INSTALL_MODE" != "quick" ]; then
        install_dependencies
    fi
    
    # Step 4: Create project structure
    echo -e "\n${PURPLE}[Step 4/7]${WHITE} Creating project structure...${NC}"
    bash master_sort.sh 2>/dev/null || bash master_zeropain_sorter.sh 2>/dev/null || {
        # Fallback: create basic structure
        mkdir -p src/{c,cpp,python} include scripts build docs data outputs
        echo -e "${GREEN}âœ“ Basic structure created${NC}"
    }
    
    # Step 5: Build C/C++ components
    echo -e "\n${PURPLE}[Step 5/7]${WHITE} Building C/C++ components...${NC}"
    if [ "$INSTALL_MODE" != "quick" ]; then
        thermal_compile
    else
        echo -e "${YELLOW}Skipping compilation in quick mode${NC}"
    fi
    
    # Step 6: Setup Python environment
    echo -e "\n${PURPLE}[Step 6/7]${WHITE} Setting up Python environment...${NC}"
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --quiet --upgrade pip
    
    if [ "$INSTALL_MODE" == "complete" ] || [ "$INSTALL_MODE" == "developer" ]; then
        pip install --quiet torch numpy pandas scipy matplotlib plotly \
                           scikit-learn tqdm colorlog rich psutil
    else
        pip install --quiet numpy pandas matplotlib tqdm
    fi
    
    # Step 7: Configure thermal management
    echo -e "\n${PURPLE}[Step 7/7]${WHITE} Configuring thermal management...${NC}"
    
    # Create thermal config
    cat > configs/thermal.conf << EOF
# Thermal Management Configuration
THERMAL_LIMIT=$THERMAL_LIMIT
THERMAL_TARGET=$THERMAL_TARGET
THERMAL_THROTTLE=$THERMAL_THROTTLE
CHECK_INTERVAL=500
ENABLE_AUTO_THROTTLE=true
GOVERNOR_NORMAL=performance
GOVERNOR_THROTTLE=powersave
EOF
    
    # Create systemd service for thermal monitoring (if developer mode)
    if [ "$INSTALL_MODE" == "developer" ]; then
        sudo tee /etc/systemd/system/zeropain-thermal.service > /dev/null << EOF
[Unit]
Description=ZeroPain Thermal Monitor
After=multi-user.target

[Service]
Type=simple
ExecStart=$(pwd)/scripts/thermal_monitor.sh
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF
        echo -e "${GREEN}âœ“ Thermal monitoring service created${NC}"
    fi
    
    # Calculate installation time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo -e "${GREEN}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
    echo -e "${GREEN}         âœ“ INSTALLATION COMPLETE (${duration}s)${NC}"
    echo -e "${GREEN}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
}

# ==============================================================================
# POST-INSTALLATION
# ==============================================================================

post_installation() {
    echo ""
    echo -e "${CYAN}ðŸ“‹ Installation Summary:${NC}"
    echo -e "  Mode: ${WHITE}$INSTALL_MODE${NC}"
    echo -e "  CPU Temperature: ${WHITE}$(check_temperature)Â°C${NC}"
    echo -e "  NPU Support: ${WHITE}$NPU_AVAILABLE${NC}"
    echo -e "  SIMD Support: ${WHITE}$AVX_SUPPORT${NC}"
    
    # Create launch script
    cat > run.sh << 'LAUNCHER'
#!/usr/bin/env bash
# ZeroPain Framework Launcher

source venv/bin/activate 2>/dev/null

echo -e "\033[0;96mâ•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—\033[0m"
echo -e "\033[0;96mâ•‘     ZeroPain Framework Launcher        â•‘\033[0m"
echo -e "\033[0;96mâ•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\033[0m"
echo ""
echo "[1] Run Patient Simulation (C)"
echo "[2] Run NPU-Accelerated Simulation"
echo "[3] Run Python Framework"
echo "[4] Launch Web Dashboard"
echo "[5] Monitor System"
echo "[6] Run Tests"
echo ""
read -p "Select option: " choice

case $choice in
    1) ./build/bin/patient_sim ;;
    2) ./build/bin/npu_sim ;;
    3) python src/python/enhanced_framework.py ;;
    4) python -m http.server 8080 --directory . & echo "Open http://localhost:8080/dashboard.html" ;;
    5) watch -n 1 'sensors; echo "---"; nvidia-smi 2>/dev/null || echo "No GPU"' ;;
    6) make test ;;
    *) echo "Invalid option" ;;
esac
LAUNCHER
    
    chmod +x run.sh
    
    # Create desktop entry (Linux)
    if [ "$INSTALL_MODE" == "complete" ] || [ "$INSTALL_MODE" == "developer" ]; then
        cat > ~/.local/share/applications/zeropain.desktop << EOF
[Desktop Entry]
Name=ZeroPain Framework
Comment=Opioid Optimization Framework
Exec=$(pwd)/run.sh
Icon=$(pwd)/docs/images/icon.png
Terminal=true
Type=Application
Categories=Science;Development;
EOF
        echo -e "${GREEN}âœ“ Desktop entry created${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}ðŸš€ Quick Start Commands:${NC}"
    echo -e "  ${WHITE}./run.sh${NC}              - Launch interactive menu"
    echo -e "  ${WHITE}make all${NC}              - Build all components"
    echo -e "  ${WHITE}make thermal${NC}          - Check thermal status"
    echo -e "  ${WHITE}source venv/bin/activate${NC} - Activate Python environment"
    
    echo ""
    echo -e "${CYAN}ðŸ“Š Verification:${NC}"
    
    # Test imports
    echo -ne "  Testing C compilation... "
    if [ -f "build/bin/patient_sim" ]; then
        echo -e "${GREEN}âœ“${NC}"
    else
        echo -e "${RED}âœ—${NC}"
    fi
    
    echo -ne "  Testing Python imports... "
    python -c "import numpy, pandas, matplotlib" 2>/dev/null && echo -e "${GREEN}âœ“${NC}" || echo -e "${RED}âœ—${NC}"
    
    echo -ne "  Testing thermal monitoring... "
    temp=$(check_temperature)
    if [ $temp -gt 0 ] && [ $temp -lt 120 ]; then
        echo -e "${GREEN}âœ“ (${temp}Â°C)${NC}"
    else
        echo -e "${YELLOW}âš  (Unable to read)${NC}"
    fi
    
    # Performance test
    if [ "$INSTALL_MODE" == "developer" ]; then
        echo ""
        echo -e "${CYAN}ðŸ”¬ Running performance test...${NC}"
        echo -e "  Generating 1000 test patients..."
        time python -c "
import numpy as np
np.random.seed(42)
patients = np.random.randn(1000, 50)
print(f'  Matrix shape: {patients.shape}')
print(f'  Memory usage: {patients.nbytes / 1024:.1f} KB')
" 2>/dev/null || echo -e "${YELLOW}  Performance test skipped${NC}"
    fi
    
    echo ""
    echo -e "${PURPLE}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
    echo -e "${GREEN}âœ¨ ZeroPain Framework is ready to use!${NC}"
    echo -e "${PURPLE}â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”${NC}"
}

# ==============================================================================
# ERROR HANDLING
# ==============================================================================

error_handler() {
    echo -e "\n${RED}âŒ Installation failed at line $1${NC}"
    echo -e "${YELLOW}Attempting recovery...${NC}"
    
    # Clean up partial installation
    deactivate 2>/dev/null || true
    
    # Log error
    echo "Error at $(date): Line $1" >> install_error.log
    
    echo -e "${YELLOW}Check install_error.log for details${NC}"
    exit 1
}

trap 'error_handler $LINENO' ERR

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        echo -e "${RED}Please do not run as root/sudo${NC}"
        exit 1
    fi
    
    # Show banner
    show_banner
    
    # Show menu
    show_menu
    
    # Perform installation
    perform_installation
    
    # Post-installation setup
    post_installation
    
    # Optional: Launch dashboard
    echo ""
    read -p "Launch web dashboard now? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}Starting web server...${NC}"
        python -m http.server 8080 --directory . &
        SERVER_PID=$!
        echo -e "${GREEN}Dashboard available at: ${WHITE}http://localhost:8080/dashboard.html${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
        
        # Open browser if possible
        if command -v xdg-open &> /dev/null; then
            sleep 2
            xdg-open "http://localhost:8080/dashboard.html"
        fi
        
        # Wait for user to stop
        wait $SERVER_PID
    fi
}

# Run main function
main "$@"