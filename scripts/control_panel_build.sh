#!/bin/bash

# ============================================================================
# ZeroPain Therapeutics - Control Panel Build Script
# Automatically downloads and builds all dependencies
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
BUILD_DIR="control_panel_build"
DEPS_DIR="$BUILD_DIR/deps"
IMGUI_DIR="$DEPS_DIR/imgui"
IMPLOT_DIR="$DEPS_DIR/implot"

# ASCII Art Header
clear
echo -e "${CYAN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ███████╗███████╗██████╗  ██████╗ ██████╗  █████╗ ██╗███╗   ██╗ ║
║     ╚══███╔╝██╔════╝██╔══██╗██╔═══██╗██╔══██╗██╔══██╗██║████╗  ██║ ║
║       ███╔╝ █████╗  ██████╔╝██║   ██║██████╔╝███████║██║██╔██╗ ██║ ║
║      ███╔╝  ██╔══╝  ██╔══██╗██║   ██║██╔═══╝ ██╔══██║██║██║╚██╗██║ ║
║     ███████╗███████╗██║  ██║╚██████╔╝██║     ██║  ██║██║██║ ╚████║ ║
║     ╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ║
║                                                                      ║
║              LABORATORY CONTROL PANEL BUILD SYSTEM                  ║
║                  With Mercury Arc Rectifier Visualization           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Progress function
progress() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} ${GREEN}►${NC} $1"
}

error() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} ${RED}✗${NC} $1"
    exit 1
}

success() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} ${GREEN}✓${NC} $1"
}

# Check prerequisites
progress "Checking system prerequisites..."

# Check for required tools
for tool in g++ git cmake make pkg-config; do
    if ! command -v $tool &> /dev/null; then
        error "$tool is not installed. Please install it first."
    fi
done
success "All build tools found"

# Check for OpenGL libraries
progress "Checking OpenGL dependencies..."
MISSING_LIBS=""

# Function to check library
check_lib() {
    if ! pkg-config --exists $1 2>/dev/null; then
        MISSING_LIBS="$MISSING_LIBS $1"
        return 1
    fi
    return 0
}

check_lib glfw3 || true
check_lib glew || true
check_lib gl || true

if [ ! -z "$MISSING_LIBS" ]; then
    echo -e "${YELLOW}Missing libraries:${MISSING_LIBS}${NC}"
    echo -e "${YELLOW}Installing dependencies...${NC}"
    
    # Detect OS and install
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y libglfw3-dev libglew-dev libgl1-mesa-dev \
                                    libxrandr-dev libxinerama-dev libxcursor-dev \
                                    libxi-dev libxxf86vm-dev
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y glfw-devel glew-devel mesa-libGL-devel
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm glfw glew mesa
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install glfw glew
        else
            error "Please install Homebrew first: https://brew.sh"
        fi
    fi
fi
success "OpenGL dependencies ready"

# Create build directory
progress "Creating build directory structure..."
mkdir -p $BUILD_DIR
mkdir -p $DEPS_DIR
mkdir -p $BUILD_DIR/fonts
cd $BUILD_DIR

# Download Dear ImGui
if [ ! -d "$IMGUI_DIR" ]; then
    progress "Downloading Dear ImGui..."
    git clone --depth 1 https://github.com/ocornut/imgui.git $IMGUI_DIR
    success "ImGui downloaded"
else
    success "ImGui already present"
fi

# Download ImPlot
if [ ! -d "$IMPLOT_DIR" ]; then
    progress "Downloading ImPlot..."
    git clone --depth 1 https://github.com/epezent/implot.git $IMPLOT_DIR
    success "ImPlot downloaded"
else
    success "ImPlot already present"
fi

# Download font
if [ ! -f "fonts/Roboto-Medium.ttf" ]; then
    progress "Downloading Roboto font..."
    wget -q https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Medium.ttf \
         -O fonts/Roboto-Medium.ttf || \
    curl -sL https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Medium.ttf \
         -o fonts/Roboto-Medium.ttf
    success "Font downloaded"
else
    success "Font already present"
fi

# Copy source files
progress "Preparing source files..."
cd ..
cp zeropain_control_panel.cpp $BUILD_DIR/
if [ -f patient_sim.h ]; then
    cp patient_sim.h $BUILD_DIR/
else
    echo -e "${YELLOW}Warning: patient_sim.h not found. Creating stub...${NC}"
    # Create stub header for standalone build
    cat > $BUILD_DIR/patient_sim.h << 'STUB'
#ifndef PATIENT_SIM_H
#define PATIENT_SIM_H
typedef struct {
    float sr17018_dose;
    float sr14968_dose;
    float dpp26_dose;
} Protocol;
typedef struct {
    const char* name;
    float ki_orthosteric;
    float ki_allosteric1;
    float ki_allosteric2;
    float g_protein_bias;
    float beta_arrestin_bias;
    float t_half;
    float bioavailability;
    float intrinsic_activity;
    float tolerance_rate;
    bool prevents_withdrawal;
    bool reverses_tolerance;
} CompoundProfile;
#endif
STUB
fi

cd $BUILD_DIR

# Create combined source file
progress "Creating combined source file..."
cat > imgui_impl.cpp << 'EOF'
// Combined ImGui implementation file
#include "deps/imgui/imgui.cpp"
#include "deps/imgui/imgui_demo.cpp"
#include "deps/imgui/imgui_draw.cpp"
#include "deps/imgui/imgui_tables.cpp"
#include "deps/imgui/imgui_widgets.cpp"
#include "deps/imgui/backends/imgui_impl_glfw.cpp"
#include "deps/imgui/backends/imgui_impl_opengl3.cpp"
#include "deps/implot/implot.cpp"
#include "deps/implot/implot_items.cpp"
EOF

# Compile flags
progress "Setting up compilation flags..."
CXXFLAGS="-std=c++17 -O3 -march=native -mtune=native -Wall -Wextra -flto -ffast-math"
INCLUDES="-I$IMGUI_DIR -I$IMGUI_DIR/backends -I$IMPLOT_DIR -I."
LIBS="-lGL -lglfw -lGLEW -pthread -fopenmp -lm -ldl"

# Platform-specific adjustments
if [[ "$OSTYPE" == "darwin"* ]]; then
    LIBS="-framework OpenGL -framework Cocoa -framework IOKit -framework CoreVideo -lglfw -lGLEW"
fi

# Compile
progress "Compiling control panel..."
echo "g++ $CXXFLAGS $INCLUDES zeropain_control_panel.cpp imgui_impl.cpp $LIBS -o zeropain_control"
g++ $CXXFLAGS $INCLUDES zeropain_control_panel.cpp imgui_impl.cpp $LIBS -o zeropain_control

if [ $? -eq 0 ]; then
    success "Compilation successful!"
    
    # Create launcher script
    cat > ../launch_control_panel.sh << 'LAUNCHER'
#!/bin/bash
cd control_panel_build
./zeropain_control
LAUNCHER
    chmod +x ../launch_control_panel.sh
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                    BUILD COMPLETE!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}Executable:${NC} control_panel_build/zeropain_control"
    echo -e "${CYAN}Launcher:${NC}   ./launch_control_panel.sh"
    echo ""
    echo -e "${YELLOW}Features:${NC}"
    echo "  • Dark laboratory theme"
    echo "  • Mercury arc rectifier visualization"
    echo "  • Real-time simulation monitoring"
    echo "  • Compound profile editor"
    echo "  • Safety analysis dashboard"
    echo "  • Protocol optimization"
    echo ""
    echo -e "${BLUE}To run:${NC}"
    echo "  ./launch_control_panel.sh"
    echo ""
    
    # Ask to run
    read -p "Launch control panel now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./zeropain_control
    fi
else
    error "Compilation failed. Check error messages above."
fi