# Domesday Duplicator + Clockgen Lite Sync Capture

## What Is This?

This is a **specialized archival tool** for VHS preservation enthusiasts using the Domesday Duplicator and the Clockgen Lite audio capture hardware.  If you're just digitising home videos with a regular USB capture device, this isn't what you need.

### Who This Is For:
- **Digital archivists, Enthusiasts or Advanced Users** preserving VHS content with Domesday Duplicator RF capture hardware running Clockgen Lite audio mods for 78.125kHz/24-bit audio needing frame-accurate A/V synchronisation for archival work.

### What Hardware You Need:
- **Domesday Duplicator** - RF-level capture device for maximum quality
- **Clockgen Lite mod** - Precision audio sampling modification
- **VCR** - For playing back tapes to be archived
- **Powerful computer** - For processing RF signals and high-bitrate audio

The automated audio/video synchronisation system includes:
- **Perfect 1kHz test tone generation** for timing calibration
- **Cross-platform support** (Windows, macOS, Linux)
- **Automated A/V alignment** using automated precision audio analysis
- **Archival formats** (FLAC + WAV output)

## Available Files

### Video Toolbox Files that can be created with this script (MP4)
- **`sync_test_10s.mp4`** - 10-second verification test (1.1 MB)
- **`pal_sync_test_1hour.mp4`** - PAL format 1-hour sync test for auto alignment (381 MB)
- **'pal_belle_nuit.mp4'** - PAL format 200 minute test video to help e.g. with tapping vcrs (1.2 GB)
- **`ntsc_sync_test_1hour.mp4`** - NTSC format 1-hour sync test for auto alignment (379 MB)
- **'ntsc_belle_nuit.mp4'** - NTSC format 200 minute test video to help e.g. with tapping vcrs (1.21 GB)

### DVD-Video Disc Images that can be created with this script (ISO)
- **`iso/pal_sync_test_1hour.iso`** - PAL format DVD-Video disc for hardware players
- **`iso/pal_belle_nuit.iso`** - PAL format DVD-Video disc for hardware players
- **`iso/ntsc_sync_test_1hour.iso`** - NTSC format DVD-Video disc for hardware players
- **`iso/ntsc_belle_nuit.iso`** - NTSC format DVD-Video disc for hardware players

> **Hardware DVD Testing**: The ISO files are proper DVD-Video discs with VIDEO_TS structure that can be burned to DVD and played directly on hardware DVD players, game consoles, or standalone video equipment. Perfect for recording to VHS to create sync test tapes.

## Test Pattern Specifications

### Video Pattern
- **ON Period**: Test pattern visible for 1 second
- **OFF Period**: Black screen for 1 second
- **Format**: Repeating 2-second cycle
- **Resolution**: 720x576 (PAL) / 720x480 (NTSC)
- **Frame Rate**: 25 fps (PAL) / 29.97 fps (NTSC)

### Audio Pattern
- **ON Period**: 1kHz sine wave tone for 1 second
- **OFF Period**: Silence for 1 second
- **Format**: Repeating 2-second cycle
- **Sample Rate**: 48kHz
- **Bit Depth**: 16-bit PCM
- **Channels**: Mono
- **Volume**: 50% to prevent clipping

### Synchronisation
- Video and audio patterns are **perfectly synchronised**
- Test pattern appears exactly when 1kHz tone plays
- Black screen appears exactly when audio is silent
- Timing verified with FFmpeg overlay filters

## Quick Start

1. **Verify Setup**: Play `sync_test_10s.mp4` to confirm sync timing
2. **Use in Production**: Import PAL or NTSC 1-hour version into your editing software
3. **Align Captures**: Use the sync files to align your Domesday Duplicator captures

## Technical Details

### Generation Process
1. **Audio Generation**: SOX creates precise 1kHz tone and silence segments
2. **Video Generation**: FFmpeg creates black background with overlay timing
3. **Synchronisation**: FFmpeg `overlay` filter with `enable='between(mod(t,2),0,1)'`
4. **Encoding**: H.264 video + PCM audio for maximum compatibility

### Scripts
- **`tools/create_sync_test.py`** - Main generation script
- **`tools/create_iso_from_mp4.py`** - Generate ISO disc images for hardware testing
- **`tools/test_sync_verification.py`** - Creates 10s verification test  
- **`tools/sync_test_summary.py`** - Shows file details and status
- **`ddd_clockgen_sync.py`** - Main capture application with A/V sync

### ISO Disc Generation

To create ISO disc images for hardware testing:

```bash
# Generate both PAL and NTSC ISO files
python tools/create_iso_from_mp4.py

# This creates:
# - media/iso/pal_sync_test_1hour.iso
# - media/iso/ntsc_sync_test_1hour.iso
```

**Hardware Use Cases:**
- Burn to DVD/CD for testing media players
- Test VHS decks with video/audio inputs
- Calibrate equipment timing
- Verify hardware A/V synchronisation

## Audio Verification

The 1kHz tone has been verified to be:
- Exactly 1000 Hz frequency
- Proper amplitude (50% volume)
- Clean sine wave with no artifacts
- Perfect timing alignment with video

## Usage Examples

### Video Editing Software
1. Import sync test file as reference track
2. Import your captured footage
3. Align the sync patterns visually and by audio
4. Apply the same timing offset to your main footage

### DaVinci Resolve
1. Drop sync test file into timeline
2. Use the pattern to establish sync reference
3. Match captured audio with the 1kHz tone bursts
4. Use visual test pattern for frame-accurate alignment

## References

- Domesday Duplicator: https://github.com/simoninns/DomesdayDuplicator/wiki/Overview
- Clockgen Lite: https://github.com/namazso/cxadc-clockgen-mod
- VHS Decode Project: https://github.com/oyvindln/vhs-decode
- Script support: https://digital-archivist.com/index.php/community/scene-by-scene-capturing-techniques/ddd-sync-capture/

## Dependencies

- `sox` - Audio processing
- `ffmpeg` - Video processing
- `python3` - Script execution

## New Automated A/V Alignment Feature

### Menu System
The capture script now includes a menu with two options:
1. **Capture New Video** - Original capture functionality
2. **Perform Automated A/V Alignment** - New automated timing calibration

### Automated Alignment Process

The automated audio/video alignment now uses multi-cycle detection over a reduced capture duration of 15 seconds. First and last cycles are ignored to account for potential human error. This ensures accurate offset calculation without unnecessary capture length.
1. **Pre-flight Check**: Verify test pattern is recorded on VHS
2. **Device Setup**: Ensure Domesday duplicator and clockgen lite are ready
3. **Capture Test**: Record 3 minutes of alignment audio automatically
4. **Analysis**: Automated audio pattern detection finds timing offset
5. **Calibration**: Automatically updates capture delay for perfect sync to your specific hardware

### Audio Analysis Technology
- **Tone Detection**: Identifies 1kHz tone bursts with high precision
- **Timing Analysis**: Measures intervals between bursts (expected: 2.000s)
- **Offset Calculation**: Determines exact timing offset in milliseconds
- **Quality Assessment**: Reports sync quality (< 10ms = excellent, < 50ms = good)

## VHS Audio Alignment

For users of the VHS decode project, this system includes audio alignment tools:

### What This Solves
The VHS decode process captures RF (video) and audio separately. Due to hardware timing differences, the audio often needs alignment with RF timing data for perfect synchronisation.

### Requirements
- **VHS decode setup** with RF capture capability
- **VhsDecodeAutoAudioAlign.exe** from the vhs-decode project
- **mono** runtime (Unix/macOS) or native Windows

### Workflow
```bash
# 1. Capture VHS with both RF and audio
# This creates: capture.tbc, capture.tbc.json, capture.wav

# 2. Align audio with RF timing
python tools/audio-sync/vhs_audio_align.py \
  capture.wav \
  capture.tbc.json \
  capture_aligned.wav

# 3. Use aligned audio in your archival workflow
```

### Installation
```bash
# Install dependencies
brew install mono  # macOS
sudo apt install mono-runtime  # Linux

# Download VhsDecodeAutoAudioAlign.exe to:
# tools/audio-sync/VhsDecodeAutoAudioAlign.exe
```

See `tools/audio-sync/README.md` for detailed documentation.

## Manual Capture Instructions

1. Place the script in the capture directory, or somewhere in your path
2. cd into your capture directory
3. Ensure you start the Domesday Capture Application and set all preferences as you desire
4. Ensure you have the Domesday Capture Application's 'Start Capture' or 'Stop Capture" button visible on the screen (not hidden behind a window)
5. Run the capture application: `ddd_main_menu.py`
6. Select option 4 to capture video or option 3 for semi-automated alignment (or one of the other options as required)
7. When finished, stop the capture by choosing menu option 9

## Project Structure

```
DdD-sync-capture/
├── ddd_clockgen_sync.py      # Main application - start here
├── check_dependencies.py     # Verify installation
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment
├── README.md                 # This file
├── media/                    # Test patterns and videos
│   ├── mp4/                     # MP4 video files
│   │   ├── sync_test_10s.mp4        # Quick verification test
│   │   ├── pal_sync_test_1hour.mp4  # PAL format test (381 MB)
│   │   └── ntsc_sync_test_1hour.mp4 # NTSC format test (379 MB)
│   ├── iso/                     # ISO disc images for hardware
│   │   ├── pal_sync_test_1hour.iso   # PAL disc image
│   │   └── ntsc_sync_test_1hour.iso  # NTSC disc image
│   └── Test Patterns/           # Source test chart images
│       ├── testchartpal.tif     # PAL test pattern
│       └── testchartntsc.tif    # NTSC test pattern
└── tools/                    # Utilities and generators
    ├── create_sync_test.py      # Generate test videos
    ├── create_iso_from_mp4.py   # Generate ISO disc images
    ├── simple_audio_analyzer.py # Audio timing analysis
    ├── sync_test_summary.py     # File status overview
    ├── test_sync_verification.py # Quick verification generator
    └── audio-sync/              # VHS audio alignment tools
        ├── vhs_audio_align.py   # Audio/RF timing alignment
        └── README.md            # Audio sync documentation
```

### Essential Files
- **`ddd_clockgen_sync.py`** - Main application with GUI automation and A/V sync
- **`check_dependencies.py`** - Verifies all dependencies are installed
- **`media/mp4/sync_test_10s.mp4`** - Test this first to verify your setup works

### Generated Media Files
- **PAL & NTSC test videos** - 1-hour precision timing references
- **Test pattern images** - Broadcast test charts
- **Quick verification** - 10-second samples for testing

## Verification Results

The system has been tested and verified:
- 1kHz tone generation accurate to specification
- Video/audio synchronisation perfect (0ms offset)
- Pattern timing precise (2.000s intervals)
- Audio analysis detects timing with millisecond accuracy
- Compatible with both PAL and NTSC formats
- Cross-platform support: **macOS**, **Linux**, and **Windows**

## Installation

### Option 1: Using Conda (Recommended)

The easiest way to install all dependencies is using conda:

```bash
# Clone the repository
git clone https://github.com/yourusername/DdD-sync-capture.git
cd DdD-sync-capture

# Create conda environment from file
conda env create -f environment.yml

# Activate the environment
conda activate ddd-sync-capture

# Verify installation
python check_dependencies.py

# Run the application
python ddd_clockgen_sync.py
```

### Option 2: Manual Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify installation:**
   ```bash
   python check_dependencies.py
   ```

3. **Install system dependencies:**

   **Windows:**
   - Download and install [SOX](http://sox.sourceforge.net/)
   - Download and install [FFmpeg](https://ffmpeg.org/download.html)
   - Add both to your system PATH

   **macOS:**
   ```bash
   brew install sox ffmpeg
   ```

   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt update
   sudo apt install sox ffmpeg python3-pip
   ```

### Platform-Specific Notes

#### Windows
- **Screenshot capture**: Uses PowerShell (built-in)
- **Audio recording**: Uses Windows DirectSound/WaveAudio
- **GUI automation**: Full PyAutoGUI support
- **Note**: May require running as administrator for some operations

#### macOS
- **Screenshot capture**: Uses built-in `screencapture`
- **Audio recording**: Uses Core Audio framework
- **GUI automation**: Full PyAutoGUI support

#### Linux
- **Screenshot capture**: Uses KDE Spectacle (install: `sudo apt install spectacle`)
- **Audio recording**: Uses ALSA framework
- **GUI automation**: Compatible with X11 and Wayland

### Desktop Environment Permissions

To ensure `pyautogui` works without prompts, adjust your desktop environment settings:

#### GNOME on Wayland
1. Open GNOME Settings (`gnome-control-center`).
2. Navigate to Privacy & Security → Screen Sharing.
3. Enable "Allow remote desktop connections".
4. Alternatively, enable assistive technologies under Accessibility.

#### KDE Plasma on Wayland
1. Open System Settings.
2. Go to Workspace → Workspace Behavior.
3. Enable "Screen Locker Integration" and "Desktop Effects" if applicable.
4. Check for Accessibility and ensure assistive technologies are enabled.

#### Notes
These settings help prevent permission prompts when using `pyautogui` for automation. Without these permissions, you may experience interruptions during automated tasks. Adjust accordingly for your system.
