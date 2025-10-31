# ZeroPain Therapeutics Laboratory Control System

## Overview
Professional-grade control panel for the 100K patient simulation framework, featuring a dark laboratory theme with vintage mercury arc rectifier visualization for operation intensity monitoring.

![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green)
![Cores: 22](https://img.shields.io/badge/Cores-22%20Parallel-blue)
![Patients: 100K](https://img.shields.io/badge/Simulation-100K%20Patients-orange)

---

## Features

### ðŸ”¬ **Laboratory-Inspired Interface**
- **Dark Theme**: Deep charcoal backgrounds with mercury-blue accents
- **Mercury Arc Rectifier**: Animated vintage vacuum tube showing process intensity
  - Blue plasma arc with realistic flicker
  - Intensity correlates with simulation progress
  - Random spark effects at high load
  - Glow pulsing and electrode effects

### ðŸ“Š **Real-Time Monitoring**
- Live metrics dashboard with streaming plots
- Success rate, tolerance, addiction tracking
- Target achievement indicators
- Batch-by-batch progress visualization

### ðŸ§ª **Compound Profile Editor**
- Complete pharmacological parameter tuning
- Safety scoring with color-coded indicators
- Expandable parameter sections:
  - Binding affinities (orthosteric & allosteric)
  - Signaling properties (G-protein/Î²-arrestin bias)
  - Pharmacokinetics (half-life, bioavailability)
  - Special properties (tolerance reversal, withdrawal prevention)

### ðŸŽ¯ **Protocol Designer**
- Multi-compound combination optimization
- Preset protocols (Maximum Safety, Breakthrough Pain, Opioid Rotation)
- Custom protocol creation
- Automatic dose optimization

### ðŸ“ˆ **Analysis Dashboards**
- Population statistics viewer
- Safety analysis matrix
- Compound comparison tables
- Real-time simulation metrics

---

## Installation

### Quick Build (Automated)
```bash
# Run the automated build script
chmod +x build_control_panel.sh
./build_control_panel.sh

# The script will:
# 1. Check/install dependencies
# 2. Download ImGui and ImPlot
# 3. Compile with native optimizations
# 4. Create launcher script
```

### Manual Build
```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get install libglfw3-dev libglew-dev libgl1-mesa-dev

# Clone ImGui
git clone https://github.com/ocornut/imgui.git
git clone https://github.com/epezent/implot.git

# Compile with native optimizations
g++ -std=c++17 -O3 -march=native -mtune=native -flto -ffast-math \
    zeropain_control_panel.cpp imgui/*.cpp implot/*.cpp \
    -lGL -lglfw -lGLEW -pthread -fopenmp -lm \
    -o zeropain_control
```

### Platform Support
- **Linux**: Full support with automated dependency installation
- **macOS**: Requires Homebrew for dependencies
- **Windows**: Use MSYS2 or Visual Studio (adjust paths)

---

## Usage

### Starting the Control Panel
```bash
# Using launcher script
./launch_control_panel.sh

# Or directly
cd control_panel_build
./zeropain_control
```

### Interface Layout

#### Main Menu Bar
- **System**: Toggle panels, exit application
- **Analysis**: Open analysis tools
- **View**: Theme settings, layout reset

#### Mercury Arc Rectifier
Located in the Simulation Control panel:
- **Idle**: No glow (0% intensity)
- **Running**: Blue plasma arc
- **Progress**: Intensity increases with completion
- **Flicker**: Realistic arc instability simulation

#### Compound Editor Workflow
1. Select compound from library (left panel)
2. Adjust parameters in editor (right panel)
3. Monitor safety score (auto-calculated)
4. Color indicators:
   - ðŸŸ¢ Green: Safe (>80%)
   - ðŸŸ¡ Amber: Caution (60-80%)
   - ðŸ”´ Red: Dangerous (<60%)

#### Running Simulations
1. Configure protocol doses in Simulation Control
2. Click "START SIMULATION"
3. Monitor progress via:
   - Mercury arc intensity
   - Progress bar
   - Live metrics plots
   - Target achievement indicators

---

## Compound Parameter Guide

### Key Safety Metrics

#### Bias Ratio (G-protein / Î²-arrestin)
- **>10**: Excellent (SR-17018 level)
- **5-10**: Good (safe for take-home)
- **2-5**: Moderate (use with caution)
- **<2**: Poor (traditional opioid problems)

#### Intrinsic Activity
- **0.0-0.3**: Strong ceiling effect (safest)
- **0.3-0.5**: Moderate ceiling
- **0.5-0.7**: Limited ceiling
- **0.7-1.0**: No ceiling (requires other safety mechanisms)

#### Half-Life Considerations
- **2-4h**: Breakthrough pain, PRN use
- **6-8h**: TID dosing
- **8-12h**: BID dosing (ideal for compliance)
- **>24h**: QD dosing (risk of accumulation)

---

## Advanced Features

### Sub-Menus & Expansions

#### Compound Editor Sections
- **Binding Parameters** â–¼
  - Ki values with tooltips
  - Allosteric site configuration
  - Competitive binding simulation

- **Signaling Properties** â–¼
  - Real-time bias ratio calculation
  - Visual bias indicator
  - Pathway preference display

- **Pharmacokinetics** â–¼
  - Clearance predictions
  - Dose scheduling optimizer
  - Steady-state calculator

- **Special Properties** â–¼
  - Withdrawal prevention flag
  - Tolerance reversal capability
  - Abuse-deterrent features

### Information Density Controls
- **Compact Mode**: Hide tooltips, minimize spacing
- **Standard Mode**: Default laboratory layout
- **Expanded Mode**: Show all parameters, detailed help

### Keyboard Shortcuts
- `Ctrl+N`: New compound
- `Ctrl+S`: Save configuration
- `Ctrl+R`: Run simulation
- `Space`: Pause/Resume simulation
- `F1`: Toggle help overlays
- `F11`: Fullscreen mode

---

## Performance Optimization

### Native CPU Flags
The build script automatically uses:
- `-march=native`: CPU-specific instruction sets
- `-mtune=native`: CPU-specific tuning
- `-O3`: Maximum optimization
- `-flto`: Link-time optimization
- `-ffast-math`: Aggressive floating-point optimization
- `-fopenmp`: OpenMP parallelization

### Expected Performance
- **Compilation**: ~30-60 seconds
- **Startup**: <1 second
- **Frame rate**: 60 FPS (VSync limited)
- **Simulation**: ~700 patients/second/core
- **Memory usage**: ~200MB baseline, ~2GB during 100K simulation

---

## Troubleshooting

### Build Issues

#### Missing Dependencies
```bash
# The build script auto-installs, but manually:
# Ubuntu/Debian
sudo apt-get install build-essential libglfw3-dev libglew-dev

# Fedora
sudo dnf install glfw-devel glew-devel mesa-libGL-devel

# Arch
sudo pacman -S glfw glew mesa
```

#### ImGui/ImPlot Not Found
```bash
# Re-run build script, it will download:
./build_control_panel.sh
```

### Runtime Issues

#### OpenGL Errors
- Ensure GPU drivers are updated
- Check OpenGL version: `glxinfo | grep "OpenGL version"`
- Minimum required: OpenGL 3.3

#### Mercury Arc Not Animating
- Check VSync is enabled in GPU settings
- Verify simulation is actually running
- Arc only glows during active processing

#### Font Not Loading
- Roboto font is auto-downloaded
- Manual fix: Download from Google Fonts
- Place in `control_panel_build/fonts/`

---

## Configuration Files

### Saving/Loading Compounds
```json
{
  "compounds": [
    {
      "name": "SR-17018",
      "ki_orthosteric": 0,
      "ki_allosteric1": 26,
      "g_protein_bias": 8.2,
      "beta_arrestin_bias": 0.01,
      "safety_score": 95.2
    }
  ]
}
```

### Protocol Templates
```json
{
  "protocol_name": "Zero Tolerance Achievement",
  "compounds": ["SR-17018", "SR-14968", "DPP-26"],
  "doses": [16.17, 25.31, 5.07],
  "frequencies": ["BID", "QD", "Q6H"]
}
```

---

## Development

### Adding Custom Visualizations
```cpp
// Add to DrawLiveMetrics()
if (ImPlot::BeginPlot("Custom Metric")) {
    ImPlot::PlotLine("My Data", x_data, y_data, count);
    ImPlot::EndPlot();
}
```

### Creating New Analysis Panels
```cpp
void DrawCustomAnalysis() {
    ImGui::Begin("My Analysis", &show_custom);
    // Your analysis code
    ImGui::End();
}
```

### Extending Mercury Arc Effects
```cpp
// In MercuryArcRectifier::Draw()
// Add custom plasma effects, colors, particles
```

---

## Credits

- **ImGui**: Omar Cornut (ocornut)
- **ImPlot**: Evan Pezent (epezent)
- **OpenGL**: Khronos Group
- **Design**: Inspired by vintage General Electric mercury arc rectifiers

---

## License

Proprietary - ZeroPain Therapeutics
For authorized research use only

---

*"Precision in visualization, excellence in simulation"*