# Tool Installation Location Guide

## The Problem

The DDD Capture Toolkit depends on several external tools like `tbc-video-export`, `vhs-decode`, and various `ld-decode` tools. There has been confusion about where these tools are installed and why they sometimes can't be found.

## Current Status (Before Fix)

### Where Tools Are Currently Installed

1. **tbc-video-export**: Installed in `~/.local/bin/tbc-video-export` via `pip install --user tbc-video-export`
2. **vhs-decode**: Installed in `~/.local/bin/vhs-decode` via `pip install --user vhs-decode`  
3. **ld-decode tools**: System-wide installation (e.g., `/usr/bin/ld-analyse`)

### Why This Causes Problems

1. **PATH Issues**: `~/.local/bin` is not always in the system PATH
2. **Manual Discovery**: Code has to manually search for tools in multiple locations
3. **Cross-Platform Inconsistency**: `~/.local/bin` path is Linux/macOS specific
4. **Testing Confusion**: When testing commands manually, tools appear "missing" but work in the application

### How the Job Queue Manager Currently Finds Tools

The job queue manager uses this search order for `tbc-video-export`:

```python
# 1. First check conda environment bin directory
conda_tbc_path = os.path.join(conda_prefix, 'bin', 'tbc-video-export')

# 2. Then check user local bin  
user_local_path = os.path.expanduser('~/.local/bin/tbc-video-export')

# 3. Finally fall back to system PATH
tbc_export_cmd = 'tbc-video-export'
```

## The Solution (After Fix)

### Updated Installation Method

All tools are now installed directly into the conda environment by adding them to the environment YAML files:

```yaml
- pip:
  - rich
  - tbc-video-export>=0.1.8
```

### Benefits

1. **Consistent PATH**: Tools are in `$CONDA_PREFIX/bin/` which is always in PATH when environment is active
2. **Cross-Platform**: Works identically on Linux, macOS, and Windows
3. **Isolated**: No system pollution, easy to remove by deleting the environment
4. **Predictable**: Standard conda/pip installation pattern

### For New Installations

After updating the environment files, new installations will automatically get the tools in the right location:

```bash
./setup.sh  # Will install tbc-video-export into conda environment
```

### For Existing Installations

To fix existing installations:

```bash
# Method 1: Update the environment
conda env update -f environment-linux.yml  # or your platform's yml file

# Method 2: Manual install into environment
conda activate ddd-capture-toolkit
pip install tbc-video-export>=0.1.8  # Installs into conda env, not ~/.local/
```

## Verifying Installation

After the fix, tools should be found in the conda environment:

```bash
conda activate ddd-capture-toolkit
which tbc-video-export  # Should show: /path/to/anaconda3/envs/ddd-capture-toolkit/bin/tbc-video-export
```

## For Developers/AI Assistants

When testing or debugging:

1. **Always activate the conda environment first**: `conda activate ddd-capture-toolkit`
2. **Use the dependency checker**: `python3 check_dependencies.py` 
3. **Don't assume tools are in system PATH**: They're in the conda environment
4. **When tools seem "missing"**: Check if the conda environment is properly activated

## Tool-Specific Notes

- **tbc-video-export**: Python package, can be installed via pip into conda environment
- **vhs-decode**: Python package, can be installed via pip into conda environment  
- **ld-decode tools**: May need manual compilation, but should target conda environment with `CMAKE_INSTALL_PREFIX=$CONDA_PREFIX`
- **DomesdayDuplicator**: Compiled binary, typically installed system-wide, requires manual compilation

## Reference

- Original discussion: Job queue progress monitoring improvements
- Related files: All `environment-*.yml` files updated to include `tbc-video-export`
- Testing: Use `check_dependencies.py` to verify all tools are found correctly
