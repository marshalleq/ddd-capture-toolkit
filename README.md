# DDD Capture Toolkit

A VHS archival workflow system using the Domesday Duplicator, Raspberry Pi Pico and Aliexpress Audio capture board for automated audio/video synchronisation.

## Overview

This toolkit provides a complete workflow for digitising VHS tapes using the Domesday Duplicator hardware, featuring:

- **Cross-platform support** - Works on Linux, macOS, and Windows
- **Automated workflow management** - Complete pipeline from capture to final output
- **Audio/video synchronisation** - Automated alignment of audio to video
- **Interactive control interface** - Rich terminal-based UI for monitoring and control
- **Job queue system** - Parallel processing and batch operations
- **Quality assurance** - Built-in validation and error detection

## Quick Start

### Prerequisites

- **Conda** (Miniconda or Anaconda)
- **Git** (for cloning and submodules)
- **Domesday Duplicator hardware** (for capture)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd ddd-capture-toolkit
   ```

2. **Initialize submodules:**
   ```bash
   git submodule update --init --recursive
   ```

3. **Run the setup script:**
   ```bash
   ./setup.sh
   ```
   
   This will:
   - Install conda if not present
   - Create the `ddd-capture-toolkit` environment
   - Install all required dependencies including:
     - FFmpeg, OpenCV, NumPy, Pillow
     - Rich (for terminal UI)
     - Audio processing tools (Sox)
     - Video processing libraries
     - Platform-specific build tools

4. **Activate the environment:**
   ```bash
   conda activate ddd-capture-toolkit
   ```

5. **Launch the main menu:**
   ```bash
   python3 ddd_main_menu.py
   ```

## Usage

### First Time Setup

1. **Configure processing locations** (Menu → Configuration → Manage Processing Locations)
   - Set your capture directory
   - Add any additional processing locations

2. **Check dependencies** (Menu → System → Check Dependencies)
   - Verify all tools are properly installed
   - Ensure hardware connectivity

### Basic Workflow

1. **Capture** - Use menu option 1 for VHS capture workflows
2. **Monitor** - Use menu option 2.1 for the Workflow Control Centre
3. **Process** - Jobs will automatically progress through the pipeline:
   - Decode (VHS-decode processing)
   - Compress (intermediate format conversion)
   - Export (TBC to video conversion)
   - Align (audio synchronisation)
   - Final (mux audio and video)

### Workflow Control Centre

The Workflow Control Centre (menu option 2.1) provides:

- **Project matrix view** - Visual status of all projects across workflow stages
- **Real-time progress** - Live updates of job progress and system status
- **Interactive control** - Direct commands for job management
- **System monitoring** - Resource usage and performance metrics

**Commands:**
- `h` - Show help
- `d` - Show detailed information
- `q` - Quit
- `clean <project><step>` - Clean stuck/failed jobs (e.g., `clean 1e`)
- `force <project><step>` - Force restart workflow step

## Platform-Specific Notes

### macOS
- Requires Xcode command line tools
- Uses conda-forge for most dependencies
- Hardware drivers may require additional setup

### Linux
- Most comprehensive platform support
- All dependencies available through conda/system packages
- Recommended for production use

### Windows
- Requires Windows Subsystem for Linux (WSL) or native Windows tools
- Some external tools may need manual installation
- Environment setup may require additional steps

## Troubleshooting

### Common Issues

**"name 'Layout' is not defined" error:**
- Ensure you've run `./setup.sh`
- Activate the conda environment: `conda activate ddd-capture-toolkit`
- Verify rich library: `python3 -c "from rich.layout import Layout; print('OK')"`

**Missing dependencies:**
- Run the dependency checker from the main menu
- Reinstall environment: `./clean-setup.sh && ./setup.sh`

**Environment activation fails:**
- Ensure conda is in your PATH
- Try: `source ~/.bashrc` or `source ~/.zshrc`
- Manual activation: `conda activate ddd-capture-toolkit`

### Getting Help

1. Check the system dependency checker (main menu)
2. Review log files in the project directory
3. Ensure all submodules are properly initialised
4. Verify hardware connections and drivers

## Architecture

The toolkit consists of several integrated components:

- **Main Menu System** (`ddd_main_menu.py`) - Entry point and navigation
- **Workflow Control Centre** (`workflow_control_centre.py`) - Interactive monitoring
- **Job Queue Manager** (`job_queue_manager.py`) - Parallel job processing
- **Project Discovery** (`project_discovery.py`) - Automatic project detection
- **Capture Tools** - VHS capture and calibration utilities
- **Processing Pipeline** - Decode, compress, export, align, and mux stages

## Configuration

Configuration files are stored in the `config/` directory:

- `processing_locations.json` - Scan directories for projects
- Job queue backups and state files
- Workflow step configurations

## Contributing

This project integrates several external tools:

- [ld-decode](https://github.com/happycube/ld-decode) - LaserDisc/VHS RF decoding
- [vhs-decode](https://github.com/oyvindln/vhs-decode) - VHS-specific decoding
- [tbc-video-export](https://github.com/JuniorIsAJitterbug/tbc-video-export) - TBC to video conversion
- [Domesday Duplicator](https://github.com/simoninns/DomesdayDuplicator) - Hardware interface

## Licence

This project builds upon multiple open-source components. Please refer to individual component licences for specific terms.
