#!/bin/bash

# Start script for DDD Capture Toolkit
# This script activates the conda environment and runs the main menu

# Get the directory where this script is located (should be the same as ddd_main_menu.py)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if the main menu file exists
if [ ! -f "ddd_main_menu.py" ]; then
    echo "Error: ddd_main_menu.py not found in current directory"
    exit 1
fi

# Try to activate the conda environment
if command -v conda &> /dev/null; then
    # Source conda initialization
    eval "$(conda shell.bash hook)"
    
    # Activate the environment
    conda activate ddd-capture-toolkit
    
    if [ $? -ne 0 ]; then
        echo "Warning: Could not activate conda environment 'ddd-capture-toolkit'"
        echo "Attempting to run with system Python..."
    else
        echo "Successfully activated conda environment 'ddd-capture-toolkit'"
        # Verify scipy is available
        if ! python3 -c "import scipy" &> /dev/null; then
            echo "Warning: scipy not available in conda environment"
            echo "You may need to install dependencies: conda install scipy"
        fi
    fi
else
    echo "Warning: conda not found, using system Python"
fi

# Run the main menu application
echo "Starting DDD Capture Toolkit..."
# Use exec to replace the shell process, keeping the conda environment active
exec python3 ddd_main_menu.py
