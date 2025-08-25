# DDD Capture Toolkit - Comprehensive Architecture

## Overview

The DDD Capture Toolkit is a complete VHS archival system combining the Domesday Duplicator hardware with automated workflow management. The system has evolved from a simple build tool into a comprehensive workflow management platform supporting the entire VHS capture-to-archive pipeline.

## Core Architectural Principles

### 1. Environment Isolation & Cross-Platform Support
- **Complete Conda Environment Isolation**: All tools run in isolated `ddd-capture-toolkit` environment
- **Cross-Platform Portability**: Supports Linux (primary), macOS, Windows
- **Version Coexistence**: No interference with existing user installations
- **Source & Binary Distribution**: Performance (source) vs Easy (binary) installation modes

### 2. Modular Workflow Management
- **Phase-Based Architecture**: Capture → Decode → Process → Export → Archive
- **Real-Time Status Tracking**: Live progress monitoring and job queue integration
- **Project-Centric Organisation**: Files grouped by base name across multiple directories
- **Rich Terminal Interface**: Professional display using Rich library

### 3. Background Processing & Concurrency
- **Persistent Job Queue**: Survives system restarts and crashes
- **Parallel Processing**: Configurable concurrent job execution
- **Non-Blocking UI**: Interface remains responsive during long operations
- **Real-Time Progress**: Frame-level progress tracking with ETA calculation

## System Dependencies & External Libraries

### Core Python Dependencies (environment.yml)
- **Python 3.10**: Base runtime environment
- **Rich**: Terminal UI library for status displays and progress bars
- **OpenCV**: Video processing and frame generation
- **NumPy**: Numerical processing for audio/video data
- **Keyboard**: Interactive input handling for workflow control centre
- **Pillow**: Image processing and manipulation

### System Libraries (Conda Environment)
- **FFmpeg**: Video encoding/decoding and format conversion
- **SOX**: Audio processing and format conversion
- **FFTW**: Fast Fourier Transform library for signal processing
- **Qt6**: GUI framework (for tools that require it)
- **GCC/G++**: Compiler toolchain for source builds
- **CMake**: Build system for C++ projects
- **pkg-config**: Library configuration management

### External Tool Dependencies (Git Submodules)
- **ld-decode** (external/ld-decode): LaserDisc RF processing tools
- **vhs-decode** (external/vhs-decode): VHS RF processing tools  
- **tbc-video-export** (external/tbc-video-export): TBC to video conversion
- **DomesdayDuplicator** (external/DomesdayDuplicator): Hardware control interface

### Optional Dependencies
- **mono**: .NET runtime for Windows tools on Unix systems
- **VhsDecodeAutoAudioAlign.exe**: Audio alignment tool (separate project)
- **Various system packages**: Platform-specific libraries for hardware access

## Code Architecture & Module Organisation

### Core Configuration & Management
| Module | Purpose |
|--------|---------|
| `config.py` | Configuration management, settings persistence, disk space checking |
| `directory_manager.py` | Multiple processing location management and file scanning |
| `platform_utils.py` | Cross-platform compatibility utilities and system detection |

### Workflow Management & Project Discovery
| Module | Purpose |
|--------|---------|
| `project_discovery.py` | Scans directories to identify VHS projects by file patterns |
| `workflow_analyzer.py` | Analyses project status across all workflow phases |
| `project_status_display.py` | Rich terminal display for project status matrices |
| `project_workflow.py` | Main workflow management interface (compatibility wrapper) |
| `project_workflow_browser.py` | Enhanced project browser with detailed status |

### Job Queue & Background Processing
| Module | Purpose |
|--------|---------|
| `job_queue_manager.py` | Persistent job queue with threading and process management |
| `job_queue_display.py` | Real-time job status display with progress tracking |
| `parallel_vhs_decode.py` | Parallel VHS decode processing with progress monitoring |

### Workflow Control Centre
| Module | Purpose |
|--------|---------|
| `workflow_control_centre.py` | Main workflow interface with project matrix (A-G labels) |
| `shared/progress_display_utils.py` | Shared utilities for progress display formatting |

### Tools & Utilities
| Directory | Purpose |
|-----------|---------|
| `tools/timecode-generator/` | VHS timecode pattern generation for calibration |
| `tools/audio-sync/` | Audio alignment tools and utilities |
| `tools/` | Various analysis and diagnostic tools |

### Build System & Installation
| Directory | Purpose |
|-----------|---------|
| `build-scripts/` | Cross-platform build scripts for external dependencies |
| `build-scripts/common/` | Shared build utilities (platform detection, optimization) |

### User Interface & Menu System
| Module | Purpose |
|--------|---------|
| `ddd_main_menu.py` | Main menu system and high-level navigation |

## Data Flow & System Integration

### 1. Project Discovery Flow
```
Configuration (config.json) → Directory Manager → Project Discovery → 
File Categorisation → Project Objects
```

### 2. Workflow Analysis Flow  
```
Project Objects → Workflow Analyzer → Job Queue Status → 
File System Status → Workflow Status Objects
```

### 3. Job Processing Flow
```
User Input → Job Queue Manager → Background Threads → 
External Tools (vhs-decode, etc.) → Progress Tracking → Status Updates
```

### 4. Display Flow
```
Workflow Status → Project Status Display → Rich Terminal → 
Live Updates → User Interface
```

## Key Classes & Data Structures

### Project Management Classes

#### `Project` (project_discovery.py)
```python
@dataclass
class Project:
    name: str                           # Base project name
    source_directory: str               # Directory containing files
    capture_files: Dict[str, str]       # video, audio, metadata paths
    output_files: Dict[str, str]        # decode, export, align, final paths
    file_sizes: Dict[str, int]          # File sizes for validation
    timestamps: Dict[str, datetime]     # File creation/modification times
```

#### `WorkflowStatus` (workflow_analyzer.py)
```python
@dataclass
class WorkflowStatus:
    project_name: str
    steps: Dict[WorkflowStep, StepStatus] 
    step_details: Dict[WorkflowStep, str]  # Error messages, additional info
```

#### `ProcessingLocation` (directory_manager.py)
```python
@dataclass
class ProcessingLocation:
    name: str                   # User-friendly name
    path: str                   # Absolute directory path
    enabled: bool              # Whether to scan this location
    priority: int              # Display priority
    scan_subdirs: bool         # Recursive scanning
    last_scanned: str          # Timestamp of last scan
```

### Job Queue Classes

#### `QueuedJob` (job_queue_manager.py)
```python
@dataclass
class QueuedJob:
    job_id: str
    job_type: str              # "vhs-decode", "tbc-export", etc.
    input_file: str
    output_file: str
    parameters: Dict[str, Any]
    status: JobStatus          # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress: float            # 0-100
    total_frames: int          # For progress calculation
    current_frame: int         # Real-time progress
    project_name: str          # Associated project
```

#### `DecodeJob` (parallel_vhs_decode.py)
```python
@dataclass
class DecodeJob:
    job_id: int
    job_type: str              # "VHS-Decode", "TBC-Export", etc.
    input_file: str
    output_file: str
    video_standard: str        # PAL/NTSC
    tape_speed: str           # SP/LP/EP
    # Progress tracking fields
    total_frames: int
    current_frame: int
    current_fps: float
    status: str               # "Queued", "Running", "Completed", "Failed"
```

### Enums & Status Types

#### `WorkflowStep` (workflow_analyzer.py)
- `CAPTURE`: Initial RF capture from VHS
- `DECODE`: RF to TBC conversion (vhs-decode)
- `COMPRESS`: TBC compression for storage
- `EXPORT`: TBC to video conversion
- `ALIGN`: Audio/video alignment
- `FINAL`: Final muxed output creation

#### `StepStatus` (workflow_analyzer.py)
- `COMPLETE`: Step finished successfully
- `FAILED`: Error occurred, needs attention
- `VIDEO_ONLY`: No audio present, video-only workflow
- `READY`: Prerequisites met, can start
- `PROCESSING`: Currently being processed
- `QUEUED`: Waiting in job queue
- `MISSING`: Prerequisites not satisfied

#### `JobStatus` (job_queue_manager.py)
- `QUEUED`: Waiting to be processed
- `RUNNING`: Currently being processed
- `COMPLETED`: Finished successfully
- `FAILED`: Failed with error
- `CANCELLED`: User cancelled

## Function Inventory

### Configuration Management (config.py)
- `load_config()`: Load configuration from JSON file
- `save_config(config)`: Save configuration to JSON file
- `get_capture_directory()`: Get current capture directory path
- `set_capture_directory(path)`: Set new capture directory
- `check_disk_space(directory, required_gb)`: Check available disk space
- `get_ffmpeg_threads()`: Get configured FFmpeg thread count
- `set_ffmpeg_threads(count)`: Set FFmpeg thread count

### Directory Management (directory_manager.py)
- `DirectoryManager.add_location()`: Add new processing location
- `DirectoryManager.remove_location()`: Remove processing location
- `DirectoryManager.update_location()`: Update location properties
- `DirectoryManager.get_enabled_locations()`: Get active processing locations
- `DirectoryManager.scan_location()`: Scan location for project files
- `DirectoryManager.get_unique_project_names()`: Extract project names

### Project Discovery (project_discovery.py)
- `ProjectDiscovery.discover_projects(directories)`: Scan directories for projects
- `ProjectDiscovery._scan_directory(directory)`: Scan single directory
- `ProjectDiscovery._extract_base_name(filename)`: Extract project base name
- `ProjectDiscovery._categorize_file()`: Categorise file by type and naming

### Workflow Analysis (workflow_analyzer.py)
- `WorkflowAnalyzer.analyze_project_workflow()`: Analyse all workflow steps
- `WorkflowAnalyzer.get_step_status()`: Get individual step status
- `WorkflowAnalyzer._is_step_running()`: Check if step is currently running
- `WorkflowAnalyzer._is_step_queued()`: Check if step is queued
- `WorkflowAnalyzer._is_step_complete()`: Check if step is complete

### Job Queue Management (job_queue_manager.py)
- `JobQueueManager.add_job()`: Add job to queue
- `JobQueueManager.add_job_nonblocking()`: Add job with timeout
- `JobQueueManager.start_processor()`: Start background job processor
- `JobQueueManager.stop_processor()`: Stop background job processor
- `JobQueueManager.get_queue_status()`: Get current queue statistics
- `JobQueueManager.cancel_job()`: Cancel specific job
- `JobQueueManager.cleanup_completed_jobs()`: Remove old completed jobs
- `JobQueueManager._get_total_frames_from_tbc_json()`: Extract frame count from TBC JSON metadata
- `JobQueueManager._execute_vhs_decode_job()`: Execute VHS decode job with progress tracking
- `JobQueueManager._execute_tbc_export_job()`: Execute TBC export job with frame-accurate progress
- `JobQueueManager._execute_audio_align_job()`: Execute audio alignment job
- `JobQueueManager._execute_final_mux_job()`: Execute final video/audio muxing

### Parallel Processing (parallel_vhs_decode.py)
- `ParallelVHSDecoder.get_frame_count_from_json()`: Extract frame count from metadata
- `ParallelVHSDecoder.parse_decode_output()`: Parse progress from tool output
- `ParallelVHSDecoder.run_single_decode()`: Execute single decode job
- `ParallelVHSDecoder.monitor_progress()`: Real-time progress monitoring

### Workflow Control Centre (workflow_control_centre.py)
- `WorkflowControlCentre.run()`: Main control centre interface
- `WorkflowControlCentre._refresh_display()`: Update status display
- `WorkflowControlCentre._handle_keyboard_input()`: Process user input
- `WorkflowControlCentre._update_selection_state()`: Manage A-G project selection

### Timecode Generation (tools/timecode-generator/vhs_timecode_generator.py)
- `VHSTimecodeGenerator.generate_frame_image()`: Create video frame with timecode
- `VHSTimecodeGenerator.generate_audio_timecode()`: Create FSK audio timecode
- `VHSTimecodeGenerator.generate_test_video()`: Create complete calibration video
- `VHSTimecodeGenerator.frame_to_timecode()`: Convert frame number to timecode string

### Audio Alignment (tools/audio-sync/vhs_audio_align.py)
- `check_dependencies()`: Verify required tools are available
- `find_align_tool()`: Locate VhsDecodeAutoAudioAlign.exe
- `align_audio()`: Execute audio alignment pipeline

### Build System (build-scripts/build-ld-decode.sh)
- `build_ld_decode()`: Compile LD-Decode from source
- `setup_build_environment()`: Configure build environment
- `needs_build()`: Check if tool needs rebuilding

### Platform Utilities (platform_utils.py)
- Platform detection and compatibility functions
- Cross-platform path handling
- System-specific optimisation detection

## File Organisation & Naming Conventions

### Project File Patterns
The system recognises VHS projects through file naming patterns:

**Base Project Name**: `Movie_Night_1985`

**Workflow Files**:
- **RF Capture**: `Movie_Night_1985.lds` (raw RF capture)
- **Audio Capture**: `Movie_Night_1985.wav` (captured audio)
- **TBC Files**: `Movie_Night_1985.tbc` (decoded video)
- **Compressed TBC**: `Movie_Night_1985.tbc.lz4` (compressed for storage)
- **Aligned Audio**: `Movie_Night_1985_aligned.wav` (time-aligned audio)
- **Final Video**: `Movie_Night_1985_final.mkv` (muxed output)
- **Metadata**: `Movie_Night_1985.json` (capture metadata)

### Directory Structure
```
ddd-capture-toolkit/
├── config.json                        # User configuration
├── config/                           # System configuration
│   ├── job_queue.json               # Persistent job queue
│   └── processing_locations.json    # Directory scan locations
├── logs/                             # System logs
├── external/                         # Git submodules
│   ├── ld-decode/
│   ├── vhs-decode/
│   ├── tbc-video-export/
│   └── DomesdayDuplicator/
├── build-scripts/                    # Build automation
├── tools/                           # Utility tools
├── shared/                          # Shared utilities
└── Documents/                       # Documentation
```

## Data Persistence & State Management

### Configuration Files
- **`config.json`**: User preferences, capture directory, performance settings
- **`config/processing_locations.json`**: Processing directory configuration
- **`config/job_queue.json`**: Persistent job queue state

### State Synchronisation
- **File System Scanning**: Regular scans to detect new files
- **Job Queue Persistence**: Queue survives system restarts
- **Real-Time Updates**: UI updates without blocking operations
- **Cross-Process Communication**: Shared state between UI and background jobs

## Error Handling & Recovery

### Graceful Degradation
- **Missing Dependencies**: Clear error messages with resolution steps
- **File Access Issues**: Fallback to alternative locations
- **Tool Failures**: Automatic retry with different parameters
- **UI Freezing**: Non-blocking operations with timeouts

### Recovery Mechanisms
- **Job Queue Recovery**: Resume interrupted jobs after restart
- **Lock Contention**: Timeout-based lock acquisition
- **Process Cleanup**: Automatic cleanup of orphaned processes
- **User Data Protection**: Never modify user files without confirmation

## Security & Isolation Considerations

### Environment Isolation
- **Conda Environment**: Complete isolation from system tools
- **Path Management**: Tools only available when environment active
- **Clean Uninstall**: Complete removal without system impact
- **Version Coexistence**: Multiple toolkit versions possible

### User Data Safety
- **Read-Only Scanning**: Project discovery never modifies files
- **Explicit User Consent**: All destructive operations require confirmation
- **Backup Recommendations**: Clear guidance on data protection
- **Process Safety**: Graceful handling of interrupted operations

## Performance Optimisation

### CPU Optimisation
- **Native Compilation**: CPU-specific optimisation flags
- **Parallel Processing**: Multi-core utilisation for encoding
- **Efficient Algorithms**: Optimised signal processing routines
- **Memory Management**: Large file processing without memory issues

### I/O Optimisation
- **Chunked Processing**: Large files processed in chunks
- **Asynchronous Operations**: Non-blocking file operations
- **Progress Tracking**: Minimal overhead progress monitoring
- **Efficient File Scanning**: Smart directory traversal

### UI Responsiveness
- **Non-Blocking Interface**: UI remains responsive during operations
- **Timeout-Based Operations**: Prevent UI freezing
- **Efficient Updates**: Minimal screen refreshes
- **Background Processing**: Heavy work in separate threads

## Integration Points & APIs

### External Tool Integration
- **Command Line Interface**: Standardised parameter passing
- **Progress Parsing**: Real-time progress extraction from tool output
- **Error Handling**: Robust error detection and reporting
- **Process Management**: Clean process lifecycle management

### File System Integration
- **Cross-Platform Paths**: Handles Windows/Unix path differences
- **Permission Handling**: Proper file permission management
- **Large File Support**: Handles multi-GB VHS captures
- **Metadata Extraction**: JSON metadata parsing and validation

### Hardware Integration
- **Domesday Duplicator**: Hardware control and status monitoring
- **Audio Interfaces**: Multi-channel audio capture support
- **Storage Management**: Disk space monitoring and warnings

## Progress Tracking & Frame Count Extraction

### Frame Count Extraction Methods

#### VHS Decode Progress Tracking
The VHS decode step uses the Domesday Duplicator JSON metadata file to extract total frame counts:
```python
# From ParallelVHSDecoder.get_frame_count_from_json()
duration_ms = data['captureInfo']['durationInMilliseconds']
duration_seconds = duration_ms / 1000.0
if video_standard.lower() == 'pal':
    frames = int(duration_seconds * 25.0)  # PAL: 25fps
else:  # NTSC
    frames = int(duration_seconds * 29.97)  # NTSC: 29.97fps
```

#### TBC Export Progress Tracking (Enhanced Implementation)
The TBC export step now uses a consistent approach by reading the `.tbc.json` metadata file:
```python
# From JobQueueManager._get_total_frames_from_tbc_json()
with open(tbc_json_file, 'r') as f:
    data = json.load(f)
# Count fields and divide by 2 to get frames (interlaced video has 2 fields per frame)
if 'fields' in data:
    field_count = len(data['fields'])
    frame_count = int(field_count / 2)
```

### Progress Tracking Architecture

#### Consistent Frame Count Methodology
- **VHS Decode**: Extracts frame count from Domesday Duplicator JSON using duration and frame rate
- **TBC Export**: Extracts frame count from TBC JSON by counting fields and dividing by 2
- **Both methods**: Provide reliable total frame counts for accurate progress calculation
- **Fallback mechanisms**: Parse tool output when JSON metadata unavailable

#### Real-Time Progress Updates
- **Frame-level tracking**: Progress updated per processed frame
- **Progress calculation**: `(current_frame / total_frames) * 100`
- **ETA estimation**: Based on processing speed and remaining frames
- **Thread-safe updates**: Progress shared between job execution and UI threads

### Job Execution Architecture

#### Job Processing Pipeline
1. **Metadata Analysis**: Extract frame counts from JSON files before job start
2. **Process Execution**: Start external tools (vhs-decode, tbc-video-export)
3. **Progress Monitoring**: Parse tool output for current frame progress
4. **Status Updates**: Update job progress, current FPS, and ETA
5. **Completion Validation**: Verify output files exist and have expected size

#### Error Handling & Recovery
- **Process monitoring**: Track external tool processes for termination/cleanup
- **Output validation**: Verify expected output files are created successfully
- **Graceful failure**: Capture error messages and provide debugging information
- **Job restart capability**: Allow retry of failed jobs with same or modified parameters

## Future Extensibility

### Plugin Architecture Considerations
- **Modular Design**: Clean separation of concerns
- **Configuration-Driven**: Easy addition of new tools
- **Standard Interfaces**: Consistent API patterns
- **Error Handling**: Robust failure recovery

### Planned Enhancements
- **GPU Acceleration**: CUDA/OpenCL support for compatible operations
- **Cloud Integration**: Remote processing capabilities
- **Advanced Analytics**: Performance analysis and optimisation suggestions
- **Automated Quality Control**: Built-in quality assessment tools

---

This comprehensive architecture document reflects the current state of the DDD Capture Toolkit as a mature, production-ready VHS archival system with sophisticated workflow management, real-time progress tracking, and robust error handling. The modular design supports both ease of use for beginners and advanced functionality for power users, while maintaining complete isolation from existing system installations.

The system has evolved significantly beyond its original build-tool concept into a complete workflow management platform, making it essential to understand both the high-level architecture and the detailed inter-module relationships when making modifications.

<citations>
<document>
<document_type>RULE</document_type>
<document_id>MAF3R53JqKUM8aHBDHBnkU</document_id>
</document>
<document>
<document_type>RULE</document_type>
<document_id>XEmyGLEUhn1hY1pn7BPxEa</document_id>
</document>
</citations>
