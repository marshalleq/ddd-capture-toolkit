#!/bin/bash
# clean-setup.sh - Clean environment wrapper for setup.sh
# This script ensures we start with a completely clean conda environment

echo "=== Clean Setup Wrapper ==="
echo "[INFO] Clearing all conda environment variables..."

# Clear all conda-related environment variables
unset CONDA_DEFAULT_ENV
unset CONDA_PREFIX
unset CONDA_PREFIX_1
unset CONDA_PREFIX_2
unset CONDA_PREFIX_3
unset CONDA_SHLVL
unset CONDA_PROMPT_MODIFIER
unset CONDA_BUILD_SYSROOT
unset CMAKE_PREFIX_PATH
unset PKG_CONFIG_PATH
unset LD_LIBRARY_PATH
unset LIBRARY_PATH
unset CMAKE_LIBRARY_PATH

# Start a fresh bash session with clean environment and run setup
echo "[INFO] Starting clean setup process..."
exec bash -c "./setup.sh $*"
