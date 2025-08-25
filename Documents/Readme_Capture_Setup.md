# VHS Capture Automation Setup

This document describes how to set up the environment for the VHS capture automation scripts.

## Environment Setup

The capture automation requires specific Python packages for image recognition and GUI automation.

### Option 1: Using Conda (Recommended)

Create the environment from the provided file:

```bash
conda env create -f environment.yml
```

Or create manually:

```bash
conda create -n DdD-sync-capture python=3.9
conda activate DdD-sync-capture
conda install -c conda-forge opencv pyautogui pillow numpy ffmpeg alsa-lib pulseaudio-client qt6-main xclip xsel
pip install opencv-python
```

### Option 2: Using pip only

If you prefer to use pip:

```bash
pip install -r requirements.txt
```

## Usage

**Recommended**: Activate the conda environment before running the main menu:

```bash
source ~/anaconda3/bin/activate DdD-sync-capture
python ddd_main_menu.py
```

**Note**: On systems with system-wide OpenCV (like Fedora), the script may work without activating the conda environment, but using the conda environment ensures consistency.

## Dependencies Explained

- **opencv-python**: Required for image recognition (button detection)
- **pyautogui**: GUI automation for clicking buttons
- **pillow**: Image processing support
- **numpy**: Numerical operations for image data
- **ffmpeg**: Video/audio processing (system dependency)
- **alsa-lib**: Audio system interface
- **spectacle**: KDE screenshot tool (system dependency)

## Troubleshooting

### "OpenCV not found" Error

This error occurs when the script runs with system Python instead of the conda environment.

**Solution**: Always activate the conda environment first:

```bash
source ~/anaconda3/bin/activate DdD-sync-capture
```

### Button Detection Fails

1. Ensure the DomesdayDuplicator application is visible on screen
2. Check that `start_button.png` matches the current button appearance
3. Consider taking a new screenshot of the start button if the GUI has changed

### Audio Recording Issues

1. Verify your audio device with: `arecord -l`
2. Check the SOX command parameters in the script match your hardware
3. Ensure ALSA permissions are correct for your user

## Files

- `capture_start.py`: Main automation script
- `start_button.png`: Screenshot of the DomesdayDuplicator start button
- `requirements.txt`: pip dependencies
- `environment.yml`: Complete conda environment specification
