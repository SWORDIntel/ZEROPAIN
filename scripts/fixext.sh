#!/bin/bash

# fix_zeropain_extensions.sh - Fix all the .txt extensions from downloaded ZeroPain files
# Run this in the directory where you downloaded all the ZeroPain framework files

echo "ðŸ”§ FIXING ZEROPAIN FILE EXTENSIONS"
echo "==================================="
echo ""

# Fix all the known ZeroPain files with wrong extensions
declare -A FIX_MAP=(
    # Documentation files
    ["comprehensive_readme.txt"]="README.md"
    ["control_panel_readme.md"]="control_panel_readme.md"
    ["tutorial_notebook.py.txt"]="tutorial_notebook.py"
    
    # Python files
    ["opioid_optimization_framework.py"]="opioid_optimization_framework.py"
    ["patient_simulation_100k.py"]="patient_simulation_100k.py"
    ["opioid_analysis_tools.py"]="opioid_analysis_tools.py"
    ["honeypot_generator.py.txt"]="honeypot_generator.py"
    
    # Shell scripts
    ["zeropain.sh"]="zeropain.sh"
    ["comprehensive_setup_script.sh"]="comprehensive_setup_script.sh"
    ["run_simulation.sh"]="run_simulation.sh"
    ["build_control_panel.sh"]="build_control_panel.sh"
    ["launch_control_panel.sh"]="launch_control_panel.sh"
    
    # C/C++ files
    ["patient_sim_main.c"]="patient_sim_main.c"
    ["patient_sim.h"]="patient_sim.h"
    ["compound_profiles.c"]="compound_profiles.c"
    ["statistics.c"]="statistics.c"
    ["zeropain_control_panel.cpp"]="zeropain_control_panel.cpp"
    
    # Config files
    ["protocol_config.c"]="protocol_config.yaml"  # This is actually YAML
    ["requirements_txt.txt"]="requirements.txt"
    ["requirements.txt.txt"]="requirements.txt"
    [".env"]="env.example"
    
    # Build files
    ["Makefile.txt"]="Makefile"
    ["Dockerfile.txt"]="Dockerfile"
    ["CMakeLists.txt.txt"]="CMakeLists.txt"
)

# Counter
FIXED=0

# First: Remove .txt from files that shouldn't have it
echo "Fixing extensions..."
for old_file in *.txt; do
    [[ -f "$old_file" ]] || continue
    
    base_name="${old_file%.txt}"
    
    # Check if this is a known file
    if [[ -n "${FIX_MAP[$old_file]}" ]]; then
        new_name="${FIX_MAP[$old_file]}"
        mv "$old_file" "$new_name" 2>/dev/null && {
            echo "  âœ“ $old_file â†’ $new_name"
            ((FIXED++))
        }
    # Auto-detect based on content
    elif [[ -f "$old_file" ]]; then
        first_line=$(head -n1 "$old_file" 2>/dev/null)
        
        # Python files
        if [[ "$first_line" =~ ^#!.*python ]] || [[ "$base_name" =~ \.py$ ]]; then
            mv "$old_file" "$base_name.py" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.py"
                ((FIXED++))
            }
        # Shell scripts  
        elif [[ "$first_line" =~ ^#!.*sh ]] || [[ "$base_name" =~ \.sh$ ]]; then
            mv "$old_file" "$base_name.sh" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.sh"
                ((FIXED++))
            }
        # C files
        elif [[ "$base_name" =~ \.c$ ]]; then
            mv "$old_file" "$base_name.c" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.c"
                ((FIXED++))
            }
        # C++ files
        elif [[ "$base_name" =~ \.(cpp|cc|cxx)$ ]]; then
            mv "$old_file" "$base_name.cpp" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.cpp"
                ((FIXED++))
            }
        # Header files
        elif [[ "$base_name" =~ \.h$ ]]; then
            mv "$old_file" "$base_name.h" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.h"
                ((FIXED++))
            }
        # Markdown (if starts with #)
        elif [[ "$first_line" =~ ^#[[:space:]] ]] || [[ "$base_name" =~ readme ]]; then
            mv "$old_file" "$base_name.md" 2>/dev/null && {
                echo "  âœ“ $old_file â†’ $base_name.md"
                ((FIXED++))
            }
        # Keep requirements.txt as is
        elif [[ "$base_name" == "requirements" ]]; then
            echo "  âš  Keeping $old_file as is"
        fi
    fi
done

# Make scripts executable
echo ""
echo "Setting executable permissions..."
chmod +x *.sh *.py 2>/dev/null

# Summary
echo ""
echo "==================================="
echo "âœ… Fixed $FIXED files"
echo ""
echo "ðŸ“ Current directory structure:"
ls -la | grep -E "\.(py|sh|c|cpp|h|md)$|requirements\.txt|Makefile|Dockerfile" | head -20

echo ""
echo "ðŸ’¡ Next step: ./comprehensive_setup_script.sh"
