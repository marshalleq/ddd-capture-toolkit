# Job Management System Architecture

## System Overview

The Job Management System serves as the **primary and unified interface** for all post-capture VHS workflow management. This system has evolved from a simple parallel decode tool into a comprehensive workflow control centre that manages complete project workflows from captured files through to final output.

**Key Principles:**
- Single unified interface for all post-capture VHS processing
- Project-centric workflow management with dependency-aware task scheduling
- Real-time progress monitoring and system resource oversight
- Prevention of invalid operations through dependency enforcement

**Migration Status:** The Workflow Status Browser has been deprecated; its functionality has been absorbed into this unified architecture as the foundation for Phase 1.1-1.2 features.

---

## 🚀 Implementation Plan - Unified Workflow Control Centre

### Phase 1: Core MVP Implementation (Immediate Priority)

#### **1.1 Project Discovery & Grouping**
- [✅] **File Scanner Module**: Auto-detect captured files (.lds, .wav, .json) in configured directories
  - *Implementation available: `project_discovery.py` from Workflow Status Browser*
- [✅] **Project Grouping Logic**: Group files by base filename (e.g., "Movie_Night_1985.lds", "Movie_Night_1985.wav", "Movie_Night_1985.json")
  - *Implementation available: Project class and discovery logic*
- [✅] **File Validation**: Verify file existence and basic integrity checks
  - *Implementation available: ProjectValidation system with size/corruption detection*
- [✅] **Metadata Parsing**: Extract frame counts and video standards from .json files
  - *Implementation available: Basic metadata parsing in project discovery*

#### **1.2 Workflow Status Detection**
- [✅] **Dependency Chain Implementation**: Capture → Decode → Compress → Export → Align → Final workflow rules
  - *Implementation available: `workflow_analyzer.py` with complete 6-stage workflow dependencies*
- [✅] **Status Detection Algorithm**: Determine Ready/Blocked/Running/Complete/Failed for each step
  - *Implementation available: StepStatus enum with priority-ordered detection algorithm*
- [✅] **File Output Validation**: Check for .tbc, .mkv, aligned audio, final output files
  - *Implementation available: File size validation and corruption detection*
- [✅] **Active Job Integration**: Connect current job status to workflow progression
  - *Implementation available: Job queue integration with duplicate prevention*

#### **1.3 Integrated UI Enhancement** 
- [🔄] **Project Status Matrix**: Horizontal workflow view with A-G project labels
  - *PARTIAL: Basic A-G matrix implemented but missing rich styling and system resource panels*
- [🔄] **Enhanced Progress Integration**: Real-time progress bars, FPS, and ETA within workflow status columns
  - *PLANNED: Integrate detailed job progress from Menu 2.2 into workflow status display*
- [❌] **Dynamic Control Status**: Show available/disabled actions based on selection and state
  - *MISSING: Control status feedback not fully integrated with workflow analyzer*

#### **1.4 Selection & Targeting System**
- [✅] **Keyboard Input Handling**: Capture A-G (projects) and 1-9 (jobs) key presses
  - *COMPLETED: Input handling implemented using input() method*
- [🔄] **Selection State Management**: Track current project and job selections
  - *PARTIAL: Basic state tracking implemented but selection persistence needs improvement*

#### **1.5 Dependency-Aware Task Activation**
- [🔄] **Pre-flight Validation**: Check dependencies before allowing job submission
  - *PARTIAL: Workflow dependency logic exists but not integrated with control actions*
- [❌] **Smart Job Creation**: Auto-populate job parameters based on project files and status
  - *MISSING: Job creation actions show "not fully implemented yet"*
- [❌] **Error Prevention**: Block invalid operations with clear user messaging
  - *MISSING: Actions don't validate dependencies before attempting operations*
- [❌] **Batch Operation Support**: "Progress all ready decodes through to final state" type functionality
  - *MISSING: Auto-queue shows "not fully implemented yet"*

### 🔄 **Phase 1 Core MVP Implementation - SUBSTANTIAL PROGRESS**

**Status**: Core foundation is solid and working well. The basic Workflow Control Centre is functional with good visual design, but some control actions need completion.

**Current Reality vs. Architecture:**

**✅ What's Working Well:**
- Project discovery automatically finds 6 projects from configured processing locations
- A-G project selection system
- Rich terminal interface with professional table styling and colours
- Workflow status analysis showing Complete/Ready/Failed/Missing states correctly
- System status integration showing job processor status and queue stats
- Project and job selection
- Details views for both projects and jobs
- Help system with current implementation status

**🔄 Partially Implemented:**
- Retry functionality exists but needs connection to actual job resubmission

**❌ Missing from Architecture:**
- System resource panels (CPU/RAM/Disk usage monitoring) not implemented
- Dynamic control status feedback (showing which actions are available/disabled)
- Real job submission integration (Start action doesn't actually submit jobs yet)
- System resource monitoring integration
- Advanced styling matching the full architecture diagrams
- Colour scheme missing - should use retro amber terminal styling matching vintage computer displays from the VHS era

### Phase 2: Enhanced Control & User Experience (Short-term)

#### **2.1 Intelligent Suggestions System**
- [ ] **Next Action Recommendations**: "Start VHS-Decode (2 projects ready)" suggestions
- [ ] **Problem Detection**: Alert for missing files, failed jobs, dependency issues
- [ ] **Optimization Hints**: Resource utilization and load balancing suggestions
- [ ] **Workflow Guidance**: Help users understand next logical steps

#### **2.2 Enhanced Job Management**
- [ ] **Job Details View**: Comprehensive job information with logs and parameters
- [ ] **Retry with Options**: Allow parameter changes when retrying failed jobs
- [ ] **Pause/Resume Logic**: Graceful job suspension and continuation
- [ ] **Job History Tracking**: Record of all attempts, failures, and successes per project

#### **2.3 Resource Monitoring Integration**
- [ ] **Job Scheduling Logic**: Factor system resources into job queuing decisions
- [ ] **Resource Conflict Prevention**: Avoid overwhelming system with too many concurrent jobs
- [ ] **Performance Tracking**: Monitor job throughput and system efficiency
- [ ] **Alert System**: Notify when system resources are constrained

#### **2.4 Configuration & Settings**
- [ ] **Settings Persistence**: Save user preferences and system configuration
- [✅] **Directory Configuration**: Allow multiple capture/output directory management
  - *Implementation available: `directory_manager.py` with processing locations management*
  - *Implementation available: Processing locations configuration UI*
- [ ] **Testing Panel**: Customise one off decode/export parameter combinations combined with limiting the capture to specific timeframe / constant frame sections for quick turnaround
- [ ] **Job Parameter Presets**: Save customised decode/export parameter combinations
- [✅] **UI Customization**: Adjustable refresh rates, display options, keyboard shortcuts
  - *Implementation available: Display configuration interface (legend, colours, auto-refresh)*

### Phase 3: Advanced Features & Polish (Medium-term)

#### **3.1 Advanced UI Features**
- [ ] **Filtering & Search**: Show/hide projects by status, name, date, etc.
- [ ] **Project Organization**: Sorting, grouping, and categorization options
- [ ] **Keyboard Navigation**: Arrow key navigation through projects and jobs
- [ ] **Help System**: Integrated help with context-sensitive guidance

#### **3.2 Error Handling & Recovery**
- [ ] **Comprehensive Error Reporting**: Detailed failure analysis and troubleshooting
- [ ] **Automatic Recovery**: Smart retry logic with progressive fallback strategies
- [ ] **Log Management**: Persistent logging with rotation and analysis capabilities
- [ ] **Debug Mode**: Enhanced debugging output for troubleshooting issues

#### **3.3 Performance Optimization**
- [ ] **Large Project Set Handling**: Efficient UI updates for 50+ projects
- [ ] **Memory Management**: Optimize for long-running sessions
- [ ] **UI Responsiveness**: Non-blocking updates and smooth user interaction
- [ ] **Background Processing**: Prepare foundation for daemon architecture

#### **3.4 Testing & Validation**
- [ ] **Unit Test Suite**: Comprehensive testing for all major components
- [ ] **Integration Testing**: End-to-end workflow validation
- [ ] **Performance Benchmarking**: Measure and optimize system performance
- [ ] **User Acceptance Testing**: Validate user experience and workflow efficiency

#### **3.5 API for Remote Management Web GUI**
- [ ] **API**: Ability to connect to system from web application
- [ ] **Web Application**: Web Application to remote manage from browser

#### **3.6 Dockerise**
- [ ] **Run completely as a service**: Modify code to run completely as a background service
- [ ] **Dockerise**: Create Docker Application Option

### Implementation Strategy

#### **Incremental Development Approach**
1. **Build on Existing Foundation**: Extend current `parallel_vhs_decode.py` rather than rewrite
2. **Leverage Workflow Status Browser Code**: Use existing implementation as foundation for Phases 1.1-1.2
3. **Maintain Backward Compatibility**: Existing job processing must continue to work
4. **Iterative UI Enhancement**: Add new interface components alongside existing progress display
5. **Progressive Feature Addition**: Each checkpoint provides usable functionality

#### **Available Implementation Resources**
**From Workflow Status Browser (completed and tested):**
- ✅ **Project Discovery System**: `project_discovery.py` - Complete file scanning and grouping
- ✅ **Workflow Analysis**: `workflow_analyzer.py` - Status detection with 6-stage dependencies
- ✅ **Rich Display Components**: `project_status_display.py` - Coloured status tables
- ✅ **Multi-Directory Support**: `directory_manager.py` - Processing locations management
- ✅ **Job Integration**: Job queue integration with duplicate prevention
- ✅ **Batch Operations**: Working batch decode/export job queueing

**Unique Features to Integrate:**
- ✅ **Processing Locations UI**: Add/remove/configure multiple scan directories
- ✅ **JSON Status Export**: Export project data for external analysis
- ✅ **Display Configuration**: Toggle legend, colours, auto-refresh settings

#### **Development Milestones**
- **✅ Milestone 1** (Phase 1.1-1.2): Project discovery and status detection working
  - *COMPLETED: Available from Workflow Status Browser implementation*
- **Milestone 2** (Phase 1.3-1.4): Basic UI with selection system functional  
  - *IN PROGRESS: Rich display available, need A-G selection system*
- **Milestone 3** (Phase 1.5): Dependency-aware job submission complete
  - *PARTIALLY COMPLETE: Batch operations working, need smart parameter population*
- **Milestone 4** (Phase 2.1-2.2): Enhanced control and job management
- **Milestone 5** (Phase 2.3-2.4): Resource integration and configuration
  - *PARTIALLY COMPLETE: Directory configuration UI available*
- **Milestone 6** (Phase 3.x): Advanced features and optimization

#### **Success Criteria**
- ✅ **Single interface** manages complete VHS workflow from discovery to final output
- ✅ **Visual clarity** shows exactly what actions are available and what they will do
- ✅ **Error prevention** blocks invalid operations before they can cause problems
- ✅ **Efficient batch processing** handles multiple projects with minimal user interaction
- ✅ **Real-time feedback** provides accurate progress and time estimates
- ✅ **Robust error handling** gracefully manages failures with clear recovery paths

### Future Enhancements

**Planned Features:**
- **Manual Job Configuration**: Select specific RF files instead of auto-detection
- **Advanced Parameter Presets**: Save/load common decode parameter sets
- **Resume Capability**: Continue interrupted decode jobs
- **Performance Monitoring**: System resource usage during parallel processing
- **Log File Generation**: Persistent decode logs for troubleshooting

**Performance Optimizations:**
- **Dynamic Worker Scaling**: Adjust concurrency based on system load
- **Priority Queuing**: Process smaller files first for faster feedback
- **Memory Management**: Monitor and limit memory usage per worker process
- **Disk I/O Optimization**: Coordinate file access to prevent bottlenecks


### 🚀 Background Job Queue System
**Vision**: Transform from interactive script into persistent background service.

**Daemon-Based Architecture**:
```
Current: Script → Multiprocess Jobs (dies with script)
Future:  Script → Daemon → Multiprocess Jobs (daemon survives)
         Script → Connect to Daemon → View Status → Disconnect
```

**Core Components**:
1. **Job Manager Daemon**: Runs independently, manages job queue, persists state
2. **Status Monitor Client**: Reconnectable Rich UI (current interface)
3. **Job Queue API**: Add jobs, check status, cancel jobs via IPC
4. **State Persistence**: Jobs survive system reboots (optional)

**Implementation Approaches**:
- **Unix sockets** or **named pipes** for IPC communication
- **SQLite database** for persistent job queue and status
- **systemd service** or **screen/tmux sessions** for daemon persistence
- **JSON files** in `~/.ddd-jobs/` for simple status sharing

**User Experience**:
```bash
# Terminal 1: Queue jobs and exit
./start_jobs.sh  # Queues decode jobs, starts daemon, exits

# Terminal 2: Later, check status  
./job_status.sh  # Connects to daemon, shows progress, exits

# Terminal 3: Even later, add more jobs
./add_jobs.sh    # Adds TBC export jobs to running queue
```

**Advanced Capabilities**:
- **Web dashboard**: Browser-based progress monitoring
- **Remote monitoring**: Check progress from another machine  
- **Mobile app integration**: iOS/Android progress viewing
- **Email notifications**: Alerts when large batches complete
- **Job prioritization**: High-priority jobs jump the queue
- **Automatic restart**: Failed jobs retry with different parameters
- **Dependency chains**: Job B starts when Job A completes

### 💾 Multi-Disk Storage Support 
**Vision**: Optimize I/O performance by distributing jobs across multiple storage devices.

**Configuration Structure**:
```json
{
  "capture_directories": [
    {
      "name": "Primary SSD",
      "input_path": "/media/ssd1/captures",
      "output_path": "/media/ssd1/outputs",
      "priority": 1,
      "max_concurrent_jobs": 2,
      "disk_type": "ssd"
    },
    {
      "name": "Secondary NVMe", 
      "input_path": "/media/nvme2/captures",
      "output_path": "/media/nvme2/outputs",
      "priority": 2,
      "max_concurrent_jobs": 1,
      "disk_type": "nvme"
    },
    {
      "name": "Archive HDD",
      "input_path": "/media/hdd3/captures",
      "output_path": "/media/hdd3/outputs", 
      "priority": 3,
      "max_concurrent_jobs": 1,
      "disk_type": "hdd"
    }
  ]
}
```

**Job Distribution Strategies**:
1. **Automatic Load Balancing**: Most free space gets next job
2. **I/O Load Monitoring**: Least busy disk gets priority
3. **Round-Robin Distribution**: Simple rotation across available disks
4. **Same-Disk Preference**: Keep input/output on same physical drive
5. **Cross-Disk Optimization**: Read from Disk A, write to Disk B for maximum throughput
6. **SSD vs HDD Awareness**: Prioritize SSDs for temporary files, HDDs for archival

**Smart Scheduling Algorithm**:
```python
def select_optimal_disk(job_type, input_file_size):
    """Select best disk based on current load and available space"""
    candidates = []
    for disk in capture_directories:
        # Check available space
        free_space = get_disk_space(disk.output_path)
        if free_space < (input_file_size * 2):  # Need 2x space for safety
            continue
            
        # Check current load
        active_jobs = count_active_jobs_on_disk(disk)
        if active_jobs >= disk.max_concurrent_jobs:
            continue
            
        # Calculate score (space + performance + load)
        score = calculate_disk_score(disk, active_jobs, free_space)
        candidates.append((disk, score))
    
    return max(candidates, key=lambda x: x[1])[0]
```

---

## Project Naming Conventions

**Critical Design Principle**: The project base name remains consistent throughout the entire VHS processing pipeline. Only file extensions change to indicate processing stages and file types.

### Base Name Consistency
- **Project Name**: User-provided name at capture time (e.g., "Metallica1")
- **Name Preservation**: The base name "Metallica1" appears in all related files
- **Extension Variation**: Only extensions change to indicate file purpose

### File Naming Patterns

**Capture Stage Files**:
- `Metallica1.lds` - Raw RF capture data
- `Metallica1.flac` - Audio capture  
- `Metallica1.json` - General capture metadata

**Decode Stage Files**:
- `Metallica1.tbc` - Time Base Corrector video data
- `Metallica1.tbc.json` - TBC-specific metadata with videoParameters

**Export Stage Files**:
- `Metallica1_ffv1.mkv` - Exported video file

**Final Stage Files**:
- `Metallica1_aligned.wav` - Audio aligned to video timing
- `Metallica1_final.mkv` - Final output muxed from _ffv1.mkv file and _aligned.wav file


### Critical Implementation Details

**TBC JSON File Requirements**:
- **Required File**: `Metallica1.tbc.json` (exactly matching .tbc basename)
- **Contents**: Must contain `videoParameters` section with video system info
- **Purpose**: Provides PAL/NTSC and widescreen settings to tbc-video-export
- **NOT Interchangeable**: Cannot substitute general capture JSON (`Metallica1.json`)

**Workflow Tool Dependencies**:
- `vhs-decode` produces: `ProjectName.tbc` + `ProjectName.tbc.json` + `ProjectName.log`
- `vhs-decode` requires: `ProjectName.lds` OR `ProjectName.ldf` + `ProjectName.json`
- `tbc-video-export` requires: `ProjectName.tbc` + `ProjectName.tbc.json`
- `tbc-video-export` produces: `ProjectName-ffv1.mkv`
- Audio alignment uses: `ProjectName.flac` and produces `ProjectName_aligned.wav`
- Final muxing requires `ProjectName_ffv1.mkv` `ProjectName_aligned.wav` and produces `ProjectName_final.mkv`

**Cases Plus Exceptions**:
1. **All Files**: Maintain exact base name with appropriate extensions
2. **Export Video**: Appends `_ffv1` before `.mkv` extension
3. **Final Output**: Appends `_final` before `.mkv` extension
4. **Aligned Audio**: Appends `_aligned` before `.wav` extension


## Detailed Architecture Components

### Current Implementation: VHS Workflow Control Centre Phase 1.3

**Implementation Status**: ✅ **FUNCTIONAL** - Core workflow management system operational

**Current Interface Display:**

```
**Technical Integration**:
- Leverage existing job queue progress monitoring from `job_queue_display.py`
- Integrate FPS and ETA calculations into workflow status detection
- Use Rich library's multi-line cell support for detailed progress display
- Maintain real-time updates with 2-second refresh interval

**Enhanced Workflow Display Example**:

VHS WORKFLOW CONTROL CENTRE - Phase 1.3
=============================================
Unified workflow management for VHS archival processing

                               WORKFLOW PROGRESSION BY PROJECT                               │ SYSTEM RESOURCES
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓ ┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃     ┃ Project Name         ┃ (C)ompress  ┃  (D)ecode   ┃  (E)xport   ┃   (A)lign   ┃   (F)inal   ┃ ┃ CPU: ████████░░ 78%    ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩ ┃ RAM: ██████░░░░ 58%    ┃
│  1  │ Metallica1           │    Ready    │  Complete   │ ████████░   │   Ready     │   Blocked   │ ┃ Disk: ███░░░░░░░ 28%   ┃
│     │                      │             │             │ 89.2% 60fps │             │             │ ┃ Temp: 45°C             ┃
│     │                      │             │             │   ETA 12m   │             │             │ ┗━━━━━━━━━━━━━━━━━━━━━━━━┛
│  2  │ Metallica2           │    Ready    │  █████░░░░  │  Blocked    │  Complete   │   Blocked   │ 
│     │                      │             │ 62.4% 10fps │             │             │             │ 
│     │                      │             │  ETA 8h12m  │             │             │             │
│  2  │ Metallica3           │    Ready    │  Complete   │  Complete   │  Complete   │   Complete  │ 
│  3  │ ---                  │     ---     │     ---     │     ---     │     ---     │     ---     │ SYSTEM SETTINGS
│  4  │ ---                  │     ---     │     ---     │     ---     │     ---     │     ---     │ ┏━━━━━━━━━━━━━━━━━━━━━━━━┓
│  5  │ ---                  │     ---     │     ---     │     ---     │     ---     │     ---     │ ┃ Max Concurrent: 4      ┃
│  6  │ ---                  │     ---     │     ---     │     ---     │     ---     │     ---     │ ┃ Selection: None        ┃
│  7  │ ---                  │     ---     │     ---     │     ---     │     ---     │     ---     │ ┗━━━━━━━━━━━━━━━━━━━━━━━━┛
└─────┴──────────────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

ACTIVE JOBS:
======================================================================
No active jobs in queue.

SYSTEM STATUS:
==============================
Job Processor: Running
Queue Status: 0 running, 0 queued, 5 failed
Processing Locations: 2 configured
Projects Discovered: 2

Current Selection: None - Use 1D, 2C, etc. for direct actions

CONTROLS:
Coordinate System: 1D=Project1 Decode, 2C=Project2 Compress, etc.
Project Selection: 1-7 | Job Selection: J1-J9
Global: [Auto]=Queue All, [H]elp, [Q]uit
```

**Implementation Benefits**:
- **Single Screen Interface**: No need to switch between Menu 2.1 and 2.2
- **Contextual Progress**: Progress information appears exactly where the work is happening
- **Space Efficient**: Uses existing column space with multi-line cells
- **Real-time Updates**: Live progress monitoring integrated with workflow status
- **DRY Principle**: Eliminates duplicate progress monitoring implementations

### Selection and Targeting System

The control system uses a **dual-targeting approach** to handle both project-level and job-level operations:

#### **Project Selection (Letters A-G)**
- **Selection Method**: Letter keys (A, B, C...) or arrow key navigation
- **Visual Indicator**: Selected project highlighted in workflow matrix
- **Current Selection Display**: Shows "Selection: Project A" in system settings panel
- **Actions Available**: Start next workflow step, view project details, batch operations

#### **Job Selection (Numbers 1-9)** 
- **Selection Method**: Number keys (1, 2, 3...) corresponding to Active Jobs table
- **Visual Indicator**: Selected job highlighted in Active Jobs Detail table
- **Actions Available**: Pause, cancel, view details, retry (for running/queued jobs)

#### **Target Resolution Logic**
```python
class SelectionManager:
    def __init__(self):
        self.selected_project = None     # Project A-G from workflow matrix
        self.selected_job = None         # Job 1-9 from active jobs table
        self.current_target = None       # Resolved target for control actions
    
    def resolve_control_target(self, control_action: str) -> ControlTarget:
        """Determine what the control action should target"""
        
        # Job-specific controls (require active job selection)
        if control_action in ['pause', 'cancel', 'details']:
            if self.selected_job:
                return ControlTarget.JOB
            else:
                return ControlTarget.NONE  # Show "Select job first" message
        
        # Project-specific controls  
        elif control_action in ['start', 'retry']:
            if self.selected_project:
                return ControlTarget.PROJECT
            elif self.selected_job:
                return ControlTarget.JOB  # Can retry failed job
            else:
                return ControlTarget.NONE
        
        # Global controls (no selection required)
        elif control_action in ['auto_queue', 'filter', 'settings']:
            return ControlTarget.GLOBAL
        
        return ControlTarget.NONE
```

#### **Control Action Mapping**

**Project-Level Controls** (Requires Project A-G selection):
- **[S]tart**: Start next available workflow step for selected project
- **[R]etry**: Restart failed workflow step for selected project
- **[D]etails**: Show project workflow history and file details

**Job-Level Controls** (Requires Job 1-9 selection):
- **[P]ause**: Gracefully pause selected running job
- **[C]ancel**: Terminate selected job (running or queued)
- **[D]etails**: Show job logs and process details
- **[R]etry**: Restart selected failed job

**Global Controls** (No selection required):
- **[A]uto-Queue**: Automatically queue all ready workflow steps
- **[F]ilter**: Show/hide projects by status
- **[Settings]**: Configure system parameters
- **[Help]**: Show keyboard shortcuts and help
- **[Q]uit**: Exit the control centre

#### **Selection State Management**
```python
class UIStateManager:
    def update_selection_display(self):
        """Update the selection indicator in system settings panel"""
        if self.selected_project and self.selected_job:
            return f"Selection: Project {self.selected_project} + Job {self.selected_job}"
        elif self.selected_project:
            return f"Selection: Project {self.selected_project}"
        elif self.selected_job:
            return f"Selection: Job {self.selected_job}"
        else:
            return "Selection: None"
    
    def update_control_status(self):
        """Update the control status line to show valid actions"""
        available_actions = self.get_available_actions()
        if not available_actions:
            return "Current Target: None Selected - Use [A-G] for projects, [1-9] for jobs"
        else:
            return f"Current Target: {self.get_current_target_description()}"
```

```

### Class Structure

#### `WorkflowProject` (Enhanced Dataclass)
Represents a complete VHS project with:
- **Project Identity**: `project_name`, `base_directory`, `file_paths`
- **Workflow Status**: `decode_status`, `export_status`, `final_status`
- **Dependency Tracking**: `can_decode()`, `can_export()`, `can_finalise()`
- **Resource Requirements**: `estimated_decode_time`, `disk_space_needed`
- **Job Associations**: Links to active/completed jobs for this project

#### `WorkflowControlCentre` (Primary Interface Class)
Manages the unified interface with:
- **Project Discovery**: Scans directories, identifies projects and their states
- **Dependency Analysis**: Determines what actions are valid for each project
- **Resource Monitoring**: Tracks system resources and job performance
- **Action Orchestration**: Coordinates job submissions and status updates
- **UI Management**: Rich terminal interface with multi-panel layout

#### `DecodeJob` (Enhanced from Original)
Evolved job representation with:
- **Job identification**: `job_id`, file paths (`input_file`, `output_file`)
- **Job Type**: `job_type` ("Decode", "Compress", "Export", "Align", "Final")
- **Project Association**: `project_name` linking back to parent project
- **Progress tracking**: `total_frames`, `current_frame`, `current_fps`, `status`
- **Resource Usage**: `cpu_percent`, `memory_mb`, `disk_io_mbps`
- **Dependency Chain**: `depends_on`, `enables` for workflow orchestration

### Workflow Dependency Management

#### Dependency Chain Logic
```python
class WorkflowDependencies:
    WORKFLOW_STEPS = {
        'capture': {
            'requires': [],  # Initial step - RF capture hardware
            'produces': ['capture_files'],  # .lds/.ldf + .wav + .json files
            'enables': ['decode']
        },
        'decode': {
            'requires': ['capture_files'],  # .lds/.ldf + .json files
            'produces': ['tbc_file'],
            'enables': ['compress']
        },
        'compress': {
            'requires': ['tbc_file'],  # Output from Decode
            'produces': ['compressed_tbc'],
            'enables': ['export']
        },
        'export': {
            'requires': ['compressed_tbc'],  # Compressed .tbc file
            'produces': ['video_mkv'],
            'enables': ['align', 'final']  # Can enable both align and final
        },
        'align': {
            'requires': ['capture_audio'],  # Original .wav file from capture
            'produces': ['aligned_audio'],
            'enables': ['final'],
            'optional': True  # Can proceed without audio for video-only projects
        },
        'final': {
            'requires': ['video_mkv'],  # Always need video export
            'optional_requires': ['aligned_audio'],  # Audio only if available
            'produces': ['final_mkv'],
            'enables': []
        }
    }
```

#### Detailed Workflow Dependency Rules

**1. Capture Dependencies:**
- **Can Start When**: Manual initiation (hardware setup required)
- **Produces**: .lds/.ldf video files + .flac audio + .json metadata
- **Enables**: Decode step

**2. Decode Dependencies:**
- **Can Start When**: Capture video file (.lds/.ldf) + metadata (.json) exist
- **Parallel Capability**: Can run simultaneously with Align
- **Produces**: .tbc file for video processing

**3. Compress Dependencies:**
- **Can Start When**: Decode is complete (requires .tbc file)
- **Cannot Start**: Until Decode finishes
- **Produces**: Compressed .tbc file

**4. Export Dependencies:**
- **Can Start When**: Compress is complete (requires compressed .tbc file)
- **Cannot Start**: Until Compress finishes
- **Produces**: Video .mkv file

**5. Align Dependencies:**
- **Can Start When**: Original audio file (.wav) exists from capture
- **Parallel Capability**: Can run simultaneously with Decode/Compress/Export
- **Optional**: If no audio file exists, this step is marked "Video Only"
- **Produces**: Aligned audio file

**6. Final Dependencies:**
- **Always Requires**: Video .mkv file (from Export)
- **Conditionally Requires**: Aligned audio (only if original audio existed)
- **Can Start When**: 
  - **With Audio**: Export AND Align both complete
  - **Video Only**: Export complete AND no original audio file (marked "Video Only")
- **Produces**: Final .mkv with video and audio (if available)

#### Workflow State Logic
```python
def determine_workflow_state(project: WorkflowProject) -> Dict[str, StepStatus]:
    """Determine the current state of all workflow steps for a project"""
    
    # Check file existence
    has_video_capture = exists(project.video_file)  # .lds/.ldf
    has_audio_capture = exists(project.audio_file)  # .wav (optional)
    has_metadata = exists(project.json_file)       # .json
    has_tbc = exists(project.tbc_file)             # .tbc
    has_compressed_tbc = exists(project.compressed_tbc) # compressed .tbc
    has_video_export = exists(project.video_mkv)   # .mkv
    has_audio_aligned = exists(project.aligned_audio) # aligned .wav
    has_final = exists(project.final_mkv)          # final .mkv
    
    status = {}
    
    # Capture Status (usually complete when files exist)
    if has_video_capture and has_metadata:
        status['capture'] = StepStatus.COMPLETE
    else:
        status['capture'] = StepStatus.BLOCKED  # Need manual capture
    
    # Decode Status
    if has_final:
        status['decode'] = StepStatus.COMPLETE
    elif job_running(project, 'decode'):
        status['decode'] = StepStatus.RUNNING
    elif job_queued(project, 'decode'):
        status['decode'] = StepStatus.QUEUED
    elif job_failed(project, 'decode'):
        status['decode'] = StepStatus.FAILED
    elif has_video_capture and has_metadata:
        status['decode'] = StepStatus.READY
    else:
        status['decode'] = StepStatus.BLOCKED
    
    # Compress Status  
    if has_final:
        status['compress'] = StepStatus.COMPLETE
    elif job_running(project, 'compress'):
        status['compress'] = StepStatus.RUNNING
    elif job_queued(project, 'compress'):
        status['compress'] = StepStatus.QUEUED
    elif job_failed(project, 'compress'):
        status['compress'] = StepStatus.FAILED
    elif has_tbc:  # Decode must be complete
        status['compress'] = StepStatus.READY
    else:
        status['compress'] = StepStatus.BLOCKED
    
    # Export Status
    if has_final:
        status['export'] = StepStatus.COMPLETE
    elif job_running(project, 'export'):
        status['export'] = StepStatus.RUNNING
    elif job_queued(project, 'export'):
        status['export'] = StepStatus.QUEUED
    elif job_failed(project, 'export'):
        status['export'] = StepStatus.FAILED
    elif has_compressed_tbc:  # Compress must be complete
        status['export'] = StepStatus.READY
    else:
        status['export'] = StepStatus.BLOCKED
    
    # Align Status
    if not has_audio_capture:
        status['align'] = StepStatus.VIDEO_ONLY
    elif has_final:
        status['align'] = StepStatus.COMPLETE
    elif job_running(project, 'align'):
        status['align'] = StepStatus.RUNNING
    elif job_queued(project, 'align'):
        status['align'] = StepStatus.QUEUED
    elif job_failed(project, 'align'):
        status['align'] = StepStatus.FAILED
    elif has_audio_capture:  # Can start as soon as audio file exists
        status['align'] = StepStatus.READY
    else:
        status['align'] = StepStatus.BLOCKED
    
    # Final Status
    if has_final:
        status['final'] = StepStatus.COMPLETE
    elif job_running(project, 'final'):
        status['final'] = StepStatus.RUNNING
    elif job_queued(project, 'final'):
        status['final'] = StepStatus.QUEUED
    elif job_failed(project, 'final'):
        status['final'] = StepStatus.FAILED
    elif has_video_export:
        # Video export is done, check if audio is required
        if has_audio_capture:
            # Audio exists, need both video export AND audio align
            if has_audio_aligned:
                status['final'] = StepStatus.READY
            else:
                status['final'] = StepStatus.BLOCKED  # Waiting for audio align
        else:
            # No audio file, can proceed with video-only
            status['final'] = StepStatus.VIDEO_ONLY
    else:
        status['final'] = StepStatus.BLOCKED  # Need video export first
    
    return status
```

#### Status Detection Logic
```python
def determine_step_status(project: WorkflowProject, step: str) -> StepStatus:
    """Determine current status of workflow step"""
    # 1. Check active jobs first (highest priority)
    active_job = find_active_job(project.name, step)
    if active_job:
        return StepStatus.RUNNING if active_job.is_running else StepStatus.QUEUED
    
    # 2. Check for existing output files
    if output_file_exists_and_valid(project, step):
        return StepStatus.COMPLETE
    
    # 3. Check dependencies
    if not dependencies_satisfied(project, step):
        return StepStatus.BLOCKED
    
    # 4. Check for previous failures
    if has_recent_failure(project, step):
        return StepStatus.FAILED
        
    # 5. Default to ready
    return StepStatus.READY
```

### Key Features

#### 1. Auto-Detection System
- **RF File Discovery**: Scans configured capture directory for `.lds` files and / or `.ldf` files (`.ldf` is just a compressed but compatible format)
- **Metadata Validation**: Requires corresponding `.json` files for frame counting
- **Frame Calculation**: Uses JSON metadata to calculate total frames based on video standard
  - PAL: `duration_seconds * 25.0` fps
  - NTSC: `duration_seconds * 29.97` fps

#### 2. Real-Time Progress Display
- **Rich Terminal UI**: Professional progress bars, tables, and status panels
- **Live Updates**: 2Hz refresh rate for smooth progress visualization
- **Job Status Tracking**: Running, Completed, Failed states with detailed metrics
- **ETA Calculations**: Remaining time estimates based on current decode speed

#### 3. Batch Processing
- **Configurable Concurrency**: User-selectable max parallel jobs (1-8)
- **Resource Management**: Limits simultaneous processes to prevent system overload
- **Batch Queuing**: Processes jobs in batches when total exceeds max workers

#### 4. Error Handling & Debugging
- **Process Monitoring**: Captures stdout/stderr from vhs-decode processes
- **Failure Analysis**: Stores last 5 lines of output for debugging failed jobs
- **Graceful Degradation**: Falls back to simple text progress if Rich unavailable

## Implementation Details

### VHS-Decode Command Structure

After debugging and analysis, the typical `vhs-decode` parameters are:

For PAL
```bash
vhs-decode --tf vhs -t 3 --ts SP --no_resample --recheck_phase --ire0_adjust --pal input.lds output_basename
```
For NTSC
```bash
vhs-decode --tf vhs -t 3 --ts SP --no_resample --recheck_phase --ire0_adjust --ntsc input.lds output_basename
```

Note that:
-t 3 denotes the number of CPU threads assigned to the process which we will add logic to adjust later
-ts SP denotes short play, but we may also require LP (Long Play) or EP (Extended Play)
There may be a requirement to remove --no_resample --recheck_phase --ire0_adjust but this is an edge case


**Critical Parameter Corrections Made:**
- `--tf vhs` (format) instead of `--system pal`
- `-t 3` (threads) instead of `--threads 3`
- `--ts SP` (tape speed) instead of `--tape-speed SP`
- `--no_resample` (underscores) instead of `--no-resample` (hyphens)
- `--recheck_phase` (underscores) instead of `--recheck-phase`
- `--ire0_adjust` (underscores) instead of `--ire0-adjust`
- Separate `--pal`/`--ntsc` flag instead of combined system parameter
- **Output as base name without .tbc extension** (crucial fix)

### Progress Parsing Patterns

The system parses vhs-decode output using regex patterns:

```python
# Frame detection patterns
frame_match = re.search(r'(?:Processing frame|Frame)\s+(\d+)', line, re.IGNORECASE)
frame_ratio_match = re.search(r'(\d+)/(\d+)\s*\(([0-9.]+)%\)', line)

# FPS detection
fps_match = re.search(r'(?:at\s+)?([0-9.]+)\s*fps', line, re.IGNORECASE)

# Status detection
status_keywords = ['processing', 'decoding', 'writing', 'error', 'dropout', 'sync', 'completed']
```

### Multiprocessing Communication

**Queue-Based Status Updates:**
- Main process spawns worker processes for each decode job
- Worker processes send status updates via `multiprocessing.Queue`
- Status thread continuously processes queue messages
- Updates include: frame progress, fps, status text, completion signals

**Message Types:**
```python
# Progress update
{'job_id': 1, 'current_frame': 1234, 'fps': 24.5, 'status': 'Processing'}

# Completion
{'job_id': 1, 'completed': True, 'return_code': 0, 'end_time': datetime.now()}

# Error with debugging info
{'job_id': 1, 'error_details': 'Exit code 1: error messages', 'full_output': [...]}
```

## Integration Points

### Menu System Integration

**Location**: `ddd_main_menu.py` → Menu 2 (VHS-Decode) → Option 11 (Advanced) → Option 8 (Parallel)

**Menu Functions:**
- `parallel_vhs_decode_menu()` - Main parallel decode menu
- `start_auto_parallel_decode()` - Auto-detect and process RF files
- `configure_parallel_decode()` - Manual job configuration (future)
- `run_parallel_demo()` - Quick test mode
- `test_progress_display()` - UI testing

**Python Path Fix:**
Added path insertion to ensure module import works:
```python
if '.' not in sys.path:
    sys.path.insert(0, '.')
from parallel_vhs_decode import run_parallel_decode
```

### Wrapper Function

`run_parallel_decode(jobs_list, max_workers=2)` provides clean interface:

```python
jobs = [{
    'rf_file': '/path/to/input.lds',
    'video_standard': 'pal',
    'tape_speed': 'SP', 
    'additional_params': '--optional-flags'
}]
success = run_parallel_decode(jobs, max_workers=2)
```

## Dependencies

### Python Packages

**Required:**
- `rich` - Terminal UI framework
- Standard library: `multiprocessing`, `threading`, `subprocess`, `json`, `re`, `datetime`

**Installation:**
```bash
# Added to requirements.txt
rich

# Added to all environment-*.yml files under pip section
- pip:
  - rich
```

### System Requirements

**External Tools:**
- `vhs-decode` - Must be installed and available in conda environment PATH
- JSON metadata files from Domesday Duplicator captures

**Installation Notes:**
- VHS-decode should be installed as per `build.txt` instructions
- Requires conda environment activation: `conda activate ddd-capture-toolkit`
- Tool should be available as `vhs-decode` command (not just Python module)

## Current Status & Limitations

### Implemented Features
✅ **Auto-detection of RF files with JSON metadata**
✅ **Real-time progress monitoring with Rich UI**
✅ **Configurable concurrency (1-8 parallel jobs)**
✅ **Error capture and debugging output**
✅ **Graceful fallback for systems without Rich**
✅ **Integration with main menu system**
✅ **Correct vhs-decode parameter usage**
✅ **Frame-accurate progress based on JSON metadata**

### Known Issues & Debugging

**Previous Issues Resolved:**
1. ❌ **Import Error**: Fixed by adding current directory to Python path
2. ❌ **Wrong Tool**: Changed from `ld-decode` to `vhs-decode`
3. ❌ **Parameter Mismatch**: Fixed command-line parameters to match working single decode
4. ❌ **Output Path**: Fixed to use base name without .tbc extension

**Current Status:**
- System should now work correctly with proper vhs-decode parameters
- Progress display should show real frame counts and speeds
- Error messages should be captured and displayed for debugging



## Testing & Validation

### Test Scenarios

**Basic Functionality:**
1. Single RF file with JSON metadata
2. Multiple RF files (2-5) with varying sizes
3. Large RF files (>1GB) for memory/performance testing
4. Mixed PAL/NTSC files in same batch

**Error Conditions:**
1. Missing vhs-decode binary
2. Corrupted RF files
3. Insufficient disk space
4. Process interruption (Ctrl+C)
5. System resource exhaustion

**UI Testing:**
1. Rich library available vs. unavailable
2. Terminal resize during processing
3. Long filenames and progress display formatting
4. High frame count displays (>1M frames)

### Performance Benchmarks

**Expected Performance:**
- **Single Thread**: ~ (T)BC) fps decode speed (varies by system)
- **Parallel Benefit**: Near-linear scaling up to CPU core count
- **Memory Usage**: ~TBC per vhs-decode process
- **Disk I/O**: Sustained write speeds required for real-time processing

## Development Notes

### Code Quality

**Design Patterns:**
- **Dataclass Usage**: Clean job representation with automatic methods
- **Queue-Based Communication**: Thread-safe status updates
- **Context Managers**: Proper resource cleanup (Rich Live display)
- **Error Propagation**: Detailed error messages bubble up to UI

**Code Organization:**
- **Single Responsibility**: Each class has focused purpose
- **Separation of Concerns**: UI, processing, and communication isolated
- **Configuration Driven**: Parameters easily adjustable
- **Extensible Architecture**: Easy to add new decode tools or UI types

### Debugging Support

**Built-in Debugging:**
```python
# Enable detailed output capture
output_lines = []  # Stores all vhs-decode output
error_details = "Exit code X: last 5 output lines"  # Failure context
full_output = [...] # Complete process output for analysis
```

**Development Testing:**
```bash
# Direct module testing
python parallel_vhs_decode.py

# Menu system testing  
python ddd_main_menu.py
# Navigate to Menu 2 → 11 → 8 → 1
```

## File Structure

```
ddd-capture-toolkit/
├── parallel_vhs_decode.py           # Main parallel processing module
├── ddd_main_menu.py                 # Menu integration
├── requirements.txt                 # Python dependencies (includes rich)
├── environment-*.yml                # Conda environments (includes rich)
└── documents/
    └── parallel_vhs_decode_architecture.md  # This document
```
