# DDD Capture Toolkit - Quick Setup

This guide will get you up and running with the DDD Capture Toolkit in under 10 minutes.

## Prerequisites

1. **Miniconda/Anaconda** - Download from: https://docs.conda.io/en/latest/miniconda.html
2. **Git** - Most systems have this pre-installed

## Quick Setup (3 steps)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/ddd-capture-toolkit.git
cd ddd-capture-toolkit

# 2. Run the setup script
./setup.sh

# 3. Start the toolkit
./start.sh
```

That's it! The setup script will:
- Detect your operating system (Linux/Mac/Windows)
- Create an isolated conda environment with all dependencies
- Install everything you need (no system-wide installations)
- Handle platform-specific requirements

## Manual Setup (if needed)

If the automatic setup doesn't work:

```bash
# Create environment manually
conda env create -f environment-linux.yml    # Linux
# OR
conda env create -f environment-macos.yml    # macOS
# OR
conda env create -f environment.yml          # Windows/Generic

# Activate environment
conda activate ddd-capture-toolkit

# Install Python packages
pip install -r requirements.txt

# Run the application
python3 ddd_main_menu.py
```

## Hardware Setup

You'll still need to:
1. Set up your Domesday Duplicator hardware
2. Configure USB permissions (Linux)
3. Install USB drivers (Windows)

See the full build.txt file for hardware-specific instructions.

## Benefits of This Approach

- **No system modifications**: Everything runs in an isolated environment
- **Cross-platform**: Same commands work on Linux, Mac, and Windows
- **Easy uninstall**: Just delete the conda environment
- **Reproducible**: Others get exactly the same setup
- **No compilation**: Pre-built packages from conda-forge

## Troubleshooting

If you have issues:
1. Make sure conda is installed and in your PATH
2. Try the manual setup steps above
3. Check the full build.txt for detailed instructions
4. Report issues on the project repository

## Performance Notes

This approach uses pre-compiled binaries optimised for broad compatibility. While this might be slightly slower than custom compilation for your specific CPU, the difference is minimal for most users, and the setup simplicity is worth the trade-off.

For maximum performance on specific systems, you can still compile from source using the detailed instructions in build.txt.
