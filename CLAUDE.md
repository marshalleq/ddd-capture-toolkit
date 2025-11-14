# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The DDD Capture Toolkit is a VHS archival workflow system combining the Domesday Duplicator hardware with automated workflow management. This is a complete pipeline from VHS RF capture through to final muxed video output, featuring automated audio/video synchronization, job queue management, and a rich terminal-based control interface.

## Setup Commands

### Environment Setup

```bash
# Initial setup (creates conda environment with all dependencies)
./setup.sh

# Clean reinstall
./clean-setup.sh && ./setup.sh

# Activate environment (required before running any commands)
conda activate ddd-capture-toolkit

# Launch main menu
python3 ddd_main_menu.py
# OR
./start.sh
```

### Common Development Commands

```bash
# Check dependencies
python3 check_dependencies.py

# Run workflow control centre directly
python3 workflow_control_centre.py

# Test parallel decode functionality
python3 test_parallel_decode.py

# Debug job queue
python3 debug_all_jobs.py
```

### Testing

There is no formal test suite. The repository contains various test files (`test_*.py` and `debug_*.py`) used for debugging specific components during development. Run these individually when troubleshooting issues.

## Architecture Overview

### Workflow Phases

The system manages a 6-stage VHS processing pipeline with dependency-aware task scheduling:

1. **CAPTURE**: RF capture from VHS using Domesday Duplicator → produces `.lds`/`.ldf` + `.flac` + `.json`
2. **DECODE**: RF to TBC conversion using vhs-decode → produces `.tbc` + `.tbc.json`
3. **COMPRESS**: TBC compression for storage → produces `.tbc.lz4`
4. **EXPORT**: TBC to video using tbc-video-export → produces `_ffv1.mkv`
5. **ALIGN**: Audio/video synchronization (parallel to decode/compress/export) → produces `_aligned.wav`
6. **FINAL**: Mux video + audio → produces `_final.mkv`

**Critical Dependencies:**

- DECODE requires CAPTURE complete
- COMPRESS requires DECODE complete
- EXPORT requires COMPRESS complete
- ALIGN can run in parallel (only requires original audio file from CAPTURE)
- FINAL requires EXPORT complete AND (ALIGN complete OR no audio file exists)

### Core Architecture Components

**Project Management & Discovery:**

- `project_discovery.py` - Scans directories for VHS projects by file patterns, groups files by base name
- `workflow_analyzer.py` - Analyzes project status across all workflow phases, determines step status (Ready/Blocked/Running/Complete/Failed)
- `directory_manager.py` - Manages multiple processing locations and file scanning
- `project_status_display.py` - Rich terminal display for project status matrices

**Job Queue & Background Processing:**

- `job_queue_manager.py` - Persistent job queue with threading, survives restarts, manages all job types
- `job_queue_display.py` - Real-time job status display with frame-level progress tracking
- `parallel_vhs_decode.py` - Parallel VHS decode processing with progress monitoring

**Main Interfaces:**

- `ddd_main_menu.py` - Main menu system and navigation entry point
- `workflow_control_centre.py` - Unified workflow interface with project matrix (A-G selection), interactive monitoring

**Configuration & Utilities:**

- `config.py` - Configuration management, settings persistence, disk space checking
- `platform_utils.py` - Cross-platform compatibility utilities
- `shared/progress_display_utils.py` - Shared progress display formatting

### External Tool Integration

The toolkit integrates these external tools (as git submodules in `external/`):

- **ld-decode** - LaserDisc/VHS RF decoding
- **vhs-decode** - VHS-specific RF decoding
- **tbc-video-export** - TBC to video conversion
- **DomesdayDuplicator** - Hardware interface

These tools are compiled during setup and executed as subprocesses with progress monitoring.

### Project Naming Convention

**Critical Design Principle:** The project base name remains consistent throughout the entire pipeline. Only extensions change.

Example: Base name `Movie_Night_1985`

- `Movie_Night_1985.lds` - RF capture
- `Movie_Night_1985.flac` - Audio capture
- `Movie_Night_1985.json` - Capture metadata
- `Movie_Night_1985.tbc` - Decoded video
- `Movie_Night_1985.tbc.json` - TBC metadata (required for export, NOT interchangeable with capture .json)
- `Movie_Night_1985.tbc.lz4` - Compressed TBC
- `Movie_Night_1985_ffv1.mkv` - Exported video
- `Movie_Night_1985_aligned.wav` - Aligned audio
- `Movie_Night_1985_final.mkv` - Final output

**Important:** `tbc-video-export` requires `ProjectName.tbc.json` (produced by vhs-decode) which contains `videoParameters` section. This is NOT the same as the capture metadata `ProjectName.json`.

### Key Data Structures

**Project** (project_discovery.py):

```python
@dataclass
class Project:
    name: str                      # Base project name
    source_directory: str          # Directory containing files
    capture_files: Dict[str, str]  # video, audio, metadata paths
    output_files: Dict[str, str]   # decode, export, align, final paths
```

**WorkflowStatus** (workflow_analyzer.py):

```python
@dataclass
class WorkflowStatus:
    project_name: str
    steps: Dict[WorkflowStep, StepStatus]  # Status for each workflow step
    step_details: Dict[WorkflowStep, str]  # Error messages, details
```

**QueuedJob** (job_queue_manager.py):

```python
@dataclass
class QueuedJob:
    job_id: str
    job_type: str              # "vhs-decode", "tbc-export", "audio-align", "final-mux"
    input_file: str
    output_file: str
    status: JobStatus          # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress: float            # 0-100
    total_frames: int
    current_frame: int
    project_name: str
```

### Job Queue Architecture

**Job Processing Flow:**

1. Jobs added to persistent queue (`config/job_queue.json`)
2. Background processor thread picks up jobs
3. External tools executed as subprocesses
4. Output parsed for frame progress (regex patterns)
5. Progress updated in real-time
6. Queue persists across restarts

**Progress Tracking:**

- Frame counts extracted from JSON metadata files before job starts
- VHS Decode: Uses Domesday Duplicator JSON duration + video standard (PAL=25fps, NTSC=29.97fps)
- TBC Export: Uses `.tbc.json` field count / 2 (interlaced video has 2 fields per frame)
- Progress parsed from tool output using regex patterns
- Real-time updates: current frame, FPS, ETA

### vhs-decode Command Structure

**PAL example:**

```bash
vhs-decode --tf vhs -t 3 --ts SP --no_resample --recheck_phase --ire0_adjust --pal input.lds output_basename
```

**NTSC example:**

```bash
vhs-decode --tf vhs -t 3 --ts SP --no_resample --recheck_phase --ire0_adjust --ntsc input.lds output_basename
```

**Key parameters:**

- `--tf vhs` - format flag (NOT --system)
- `-t 3` - number of threads (NOT --threads)
- `--ts SP` - tape speed: SP/LP/EP (NOT --tape-speed)
- `--no_resample`, `--recheck_phase`, `--ire0_adjust` - use underscores not hyphens
- Output must be base name WITHOUT .tbc extension (tool adds it)

## Configuration Files

- `config.json` - User preferences, capture directory, thread counts
- `config/processing_locations.json` - Processing directory configuration
- `config/job_queue.json` - Persistent job queue state

## Environment & Dependencies

**Python Version:** 3.10

**Key Dependencies (managed by conda):**

- FFmpeg - video encoding/decoding
- SOX - audio processing
- OpenCV - video processing
- Rich - terminal UI library
- NumPy, Pillow - image/data processing

**Installation Modes:**

- Easy mode (default): Pre-compiled conda packages, 5 minute setup
- Performance mode: Source compilation with CPU-specific optimizations, 30-60 minute setup

Everything runs in isolated `ddd-capture-toolkit` conda environment - no system-wide installation.

## Special Tools

**Timecode Generation** (`tools/timecode-generator/`):

- VHS timecode pattern generation for calibration
- FSK audio timecode encoding
- Frame-accurate test pattern creation

**Audio Alignment** (`tools/audio-sync/`):

- Automated audio/video synchronization
- Uses VhsDecodeAutoAudioAlign.exe (Windows tool, runs via mono on Unix)

## Working with the Codebase

### Adding New Job Types

1. Add job type handler in `job_queue_manager.py` (e.g., `_execute_new_job_type()`)
2. Implement progress parsing for tool output
3. Add workflow step to `WorkflowStep` enum in `workflow_analyzer.py`
4. Update dependency logic in workflow analyzer
5. Add UI display for new step in `project_status_display.py`

### Modifying Workflow Dependencies

Edit the dependency logic in `workflow_analyzer.py`:

- `_is_step_complete()` - check if output files exist
- `_is_step_ready()` - check if prerequisites satisfied
- `_get_step_status()` - determine overall status with priority order

### Adding Configuration Options

1. Add setting to `config.py` with getter/setter functions
2. Update default config in `load_config()`
3. Add UI menu option in `ddd_main_menu.py`
4. Update `config.json` schema

### UI Development

The system uses Rich library for terminal UI:

- Use `rich.table.Table` for status matrices
- Use `rich.progress.Progress` for progress bars
- Use `rich.live.Live` for auto-updating displays
- Use `rich.panel.Panel` for grouped information
- Fallback to simple text if Rich unavailable

### Cross-Platform Compatibility

- Use `platform_utils.py` for platform-specific code
- Test on Linux (primary platform), macOS, Windows
- Path handling: use `os.path.join()` and `pathlib.Path`
- Command execution: use `subprocess` with proper shell handling
- Platform detection available in `platform_utils.py`

## Common Patterns

### File Scanning Pattern

```python
# Projects are discovered by scanning configured directories
dir_manager = DirectoryManager()
locations = dir_manager.get_enabled_locations()
project_discovery = ProjectDiscovery()
projects = project_discovery.discover_projects([loc.path for loc in locations])
```

### Job Submission Pattern

```python
# Jobs are submitted through job queue manager
job_manager = get_job_queue_manager()
job_id = job_manager.add_job(
    job_type="vhs-decode",
    input_file=input_path,
    output_file=output_path,
    parameters={"video_standard": "pal", "tape_speed": "SP"}
)
```

### Progress Monitoring Pattern

```python
# Progress is parsed from tool output using regex
frame_match = re.search(r'(?:Processing frame|Frame)\s+(\d+)', line, re.IGNORECASE)
if frame_match:
    current_frame = int(frame_match.group(1))
    progress = (current_frame / total_frames) * 100
```

## Important Notes

- The workflow control centre (Menu 2.1) is in active development - Phase 1.3 implemented but some features incomplete
- Job queue is persistent and survives system restarts
- Always activate conda environment before running any commands
- Large files (multi-GB RF captures) are common - ensure sufficient disk space
- Frame-accurate progress tracking relies on JSON metadata files being present
- All destructive operations should require user confirmation
- Lock files prevent concurrent modification of job queue
