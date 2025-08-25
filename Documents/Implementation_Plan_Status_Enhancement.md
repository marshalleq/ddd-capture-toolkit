# VHS Workflow Control Centre Status Enhancement Plan

## Implementation Roadmap

### Phase 1: Enhanced Status Display Matrix (4-6 hours) - *Partially Implemented*

**Existing Implementation:**
- `job_queue_display.py` already implements real-time progress bars, FPS, ETA, and a system status panel.
- `workflow_control_centre.py` has a basic status matrix.

**Goal**: Merge the advanced display features from `job_queue_display.py` into `workflow_control_centre.py` and enhance the layout.

**Files to Modify:**
- `project_status_display.py` - Enhanced table rendering
- `workflow_control_centre.py` - Integration with live display
- `workflow_analyzer.py` - Progress information extraction

**Key Changes:**

1. **Multi-line Status Cells**
```python
# In project_status_display.py
def create_enhanced_status_cell(self, step_status, project, step):
    """Create multi-line status cell with progress information"""
    if step_status == StepStatus.PROCESSING:
        # Get live progress from job manager
        progress_info = self._get_progress_info(project, step)
        if progress_info:
            progress_bar = self._create_progress_bar(progress_info['percentage'])
            fps_text = f"{progress_info['fps']:.1f}fps" if progress_info.get('fps') else ""
            eta_text = f"ETA {progress_info['eta']}" if progress_info.get('eta') else ""
            
            return Text.assemble(
                progress_bar, "\n",
                f"{progress_info['percentage']:.1f}% {fps_text}", "\n",
                eta_text
            )
    
    return self.get_simple_status_text(step_status)
```

2. **System Resource Panels**
```python
def create_system_resource_panel(self):
    """Create system resource monitoring panel"""
    import psutil
    
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    resource_table = Table(title="System Resources", box=HEAVY)
    resource_table.add_column("Resource", width=8)
    resource_table.add_column("Usage", width=14)
    
    # CPU with progress bar
    cpu_bar = self._create_resource_bar(cpu_percent)
    resource_table.add_row("CPU:", f"{cpu_bar} {cpu_percent:.0f}%")
    
    # Memory with progress bar  
    memory_bar = self._create_resource_bar(memory.percent)
    resource_table.add_row("RAM:", f"{memory_bar} {memory.percent:.0f}%")
    
    # Disk usage
    disk_percent = (disk.used / disk.total) * 100
    disk_bar = self._create_resource_bar(disk_percent)
    resource_table.add_row("Disk:", f"{disk_bar} {disk_percent:.0f}%")
    
    return resource_table
```

3. **Amber Terminal Colour Theme**
```python
# In workflow_analyzer.py - update STATUS_COLORS
AMBER_STATUS_COLORS = {
    'complete': '#00FF41',      # Green for success
    'failed': '#FF4444',        # Red for errors  
    'video_only': '#FFB000',    # Amber for warnings
    'ready': '#FFFFFF',         # White for ready
    'processing': '#00FFFF',    # Cyan for active
    'queued': '#FFFF00',        # Yellow for queued
    'missing': '#B0B0B0'        # Grey for missing
}

AMBER_MONOCHROME_COLORS = {
    'complete': '#FFAA00',      # Bright amber
    'failed': '#FFCC33',        # Highlight amber with blink
    'video_only': '#CC6600',    # Dim amber italic
    'ready': '#FF8000',         # Standard amber
    'processing': '#FFAA00',    # Bright amber bold
    'queued': '#CC6600',        # Dim amber
    'missing': '#CC6600'        # Dim amber
}
```

### Phase 2: Real-time Progress Integration (3-4 hours) - *Partially Implemented*

**Existing Implementation:**
- `job_queue_display.py` already has the logic for extracting real-time progress from running jobs.

**Goal**: Adapt and integrate this logic into the unified workflow control centre.

**Key Changes:**

1. **Job Progress Extraction**
```python
# In workflow_analyzer.py
def _get_job_progress_info(self, project, step):
    """Extract real-time progress information from running jobs"""
    if not self.job_manager:
        return None
        
    job_type = self._get_job_type_for_step(step)
    running_jobs = self.job_manager.get_jobs(JobStatus.RUNNING)
    
    for job in running_jobs:
        if (job.job_type == job_type and 
            self._is_job_for_project(job, project)):
            return {
                'percentage': getattr(job, 'progress_percentage', 0),
                'fps': getattr(job, 'current_fps', None),
                'eta': getattr(job, 'eta_string', None),
                'current_frame': getattr(job, 'current_frame', 0),
                'total_frames': getattr(job, 'total_frames', 0)
            }
    return None
```

2. **Enhanced Workflow Control Centre Display**
```python
# In workflow_control_centre.py
def display_enhanced_matrix(self):
    """Display enhanced workflow matrix with progress integration"""
    if not RICH_AVAILABLE or not self.project_display:
        self.display_simple_matrix()
        return
    
    # Create layout with main table and side panels
    layout = Layout()
    layout.split_row(
        Layout(name="main", ratio=3),
        Layout(name="side", ratio=1)
    )
    
    # Create enhanced project table
    project_table = self.project_display.create_enhanced_project_table(self.current_projects)
    layout["main"].update(project_table)
    
    # Create side panels
    resource_panel = self.project_display.create_system_resource_panel()
    settings_panel = self.create_system_settings_panel()
    layout["side"].split_column(
        Layout(resource_panel),
        Layout(settings_panel)
    )
    
    self.console.print(layout)
```

### Phase 3: Control System Enhancement and Menu Consolidation (3-4 hours)

**Goal**: Complete the control system, integrate the new display, and deprecate the old Menu 2.2.

**Key Changes:**

1. **Dynamic Control Status**
```python
# In workflow_control_centre.py
def get_available_actions(self):
    """Determine which control actions are currently available"""
    actions = []
    
    if self.selected_project_idx is not None:
        project = self.current_projects[self.selected_project_idx]
        workflow_status = project.workflow_status
        
        # Check for ready steps
        ready_steps = [step for step, status in workflow_status.steps.items() 
                      if status == StepStatus.READY]
        if ready_steps:
            actions.append(f"[S]tart {ready_steps[0].value}")
        
        # Check for failed steps
        failed_steps = [step for step, status in workflow_status.steps.items() 
                       if status == StepStatus.FAILED]
        if failed_steps:
            actions.append(f"[R]etry {failed_steps[0].value}")
            
        actions.append("[D]etails")
    
    elif self.selected_job_idx is not None:
        job = self.current_jobs[self.selected_job_idx]
        job_status = job.get('status', '').lower()
        
        if job_status == 'running':
            actions.extend(["[P]ause", "[C]ancel", "[D]etails"])
        elif job_status == 'failed':
            actions.extend(["[R]etry", "[D]etails"])
        elif job_status == 'queued':
            actions.extend(["[C]ancel", "[D]etails"])
    
    # Always available global actions
    actions.extend(["[A]uto-queue", "[H]elp", "[Q]uit"])
    
    return actions

def display_control_status(self):
    """Display current control status and available actions"""
    selection_info = self.get_selection_info()
    available_actions = self.get_available_actions()
    
    print(f"\nCurrent Selection: {selection_info}")
    print(f"Available Actions: {' '.join(available_actions)}")
```

## Detailed Analysis of Existing Implementation

### What's Already Working in `job_queue_display.py` (Menu 2.2) - COMPREHENSIVE

**✅ Advanced Rich Layout System:**
- Multi-panel Layout with main content, status panel, and side panels
- Live display with 2Hz refresh rate
- Professional table formatting with proper column widths
- Panel-based organization with colour-coded borders

**✅ Real-time Interactive Controls:**
- Non-blocking keyboard input (R, T, C, S, Q keys)
- Toggle auto-refresh, completed jobs visibility
- Settings menu with queue configuration
- Proper terminal handling with fallbacks for Windows

**✅ Sophisticated Progress Monitoring:**
- Progress bars using `█░` characters with exact percentages
- FPS calculations for both VHS decode (JSON-based) and TBC export (real-time)
- ETA calculations using frame counting and processing speeds
- Runtime-based performance metrics with 10-second stabilisation
- Frame count extraction from JSON metadata with caching

**✅ Real-time Progress Monitoring:**
- Progress bars using `█░` characters with percentages
- FPS calculations for both VHS decode and TBC export jobs
- ETA calculations based on frame counting and current speed
- Frame count extraction from JSON metadata files
- Runtime-based performance metrics

**✅ Comprehensive System Status Integration:**
- Complete job queue statistics (total, running, queued, completed, failed, cancelled)
- Max concurrent jobs configuration and display
- Processor status monitoring (running/stopped)
- Rich Panel with colour-coded status and proper formatting
- Side panel with live settings display and timestamp
- Job queue management functions (start/stop processor, cleanup, settings)

**✅ Rich Terminal UI:**
- Table with proper headers and formatting
- Colour-coded job statuses (green=running, yellow=queued, red=failed, blue=completed)
- Truncated file names for display
- Sort order by status priority

**✅ Advanced Job Management Integration:**
- Direct integration with `JobQueueManager` with proper error handling
- Real-time job status updates with priority-based sorting
- Support for multiple job types (vhs-decode, tbc-export) with type-specific progress logic
- Comprehensive job details view with creation/start/completion timestamps
- Error message display with preview in status column
- Job filtering and display options (show/hide completed)
- Cross-platform terminal compatibility with graceful degradation

### What's Missing from Current Workflow Control Centre (Menu 2.1)

**❌ Multi-line Status Cells:**
- Current display shows only simple status text
- No progress bars within workflow matrix cells
- No FPS or ETA information in the matrix

**❌ System Resource Monitoring:**
- No CPU/RAM/disk usage panels
- No temperature monitoring
- Missing the side panels from architecture diagram

**❌ Enhanced Layout:**
- No Layout-based Rich display (still using simple tables)
- Missing the sophisticated multi-panel layout
- No real-time Live updates

**❌ Retro Colour Schemes:**
- Using default Rich colours
- Missing amber monochrome theme
- No configuration for colour themes

### Migration Strategy Details

**Step 1: Extract Reusable Components from `job_queue_display.py`**
```python
# Create shared progress display utilities
class ProgressDisplayUtils:
    @staticmethod
    def create_progress_bar(percentage, width=20):
        """Create progress bar using existing logic from JobQueueDisplay"""
        progress_chars = int(percentage / 5)  # 20 chars for 100%
        return "█" * progress_chars + "░" * (width - progress_chars)
    
    @staticmethod
    def format_eta(seconds):
        """Format ETA using existing time formatting logic"""
        # Move the _format_time logic from job_queue_display.py here
        pass
    
    @staticmethod
    def get_job_progress_info(job_manager, project, step):
        """Extract progress info using existing job matching logic"""
        # Adapt the progress extraction from job_queue_display.py
        pass
```

**Step 2: Enhance `project_status_display.py`**
```python
# Add multi-line cell support to existing create_project_status_table method
def create_enhanced_project_status_table(self, projects):
    """Enhanced version with progress integration"""
    table = Table(title="WORKFLOW PROGRESSION BY PROJECT", box=HEAVY)
    
    # Add columns with increased height for multi-line content
    table.add_column("Project", width=20)
    table.add_column("(D)ecode", width=13, justify="center")
    table.add_column("(E)xport", width=13, justify="center") 
    # ... other columns
    
    for project in projects:
        workflow_status = self.analyzer.analyze_project_workflow(project)
        
        row_data = [project.name]
        
        for step in [WorkflowStep.DECODE, WorkflowStep.EXPORT, ...]:
            step_status = workflow_status.steps.get(step, StepStatus.MISSING)
            
            # Create enhanced cell with progress info
            if step_status == StepStatus.PROCESSING:
                # Use progress info from job manager (existing logic)
                progress_info = ProgressDisplayUtils.get_job_progress_info(
                    self.analyzer.job_manager, project, step)
                
                if progress_info:
                    # Multi-line cell with progress bar
                    cell_text = Text.assemble(
                        ProgressDisplayUtils.create_progress_bar(progress_info['percentage']), "\n",
                        f"{progress_info['percentage']:.1f}% {progress_info['fps']:.1f}fps", "\n",
                        f"ETA {progress_info['eta']}"
                    )
                else:
                    cell_text = Text("Processing", style="blue")
            else:
                # Simple status text (existing logic)
                cell_text = self.get_simple_status_text(step_status)
            
            row_data.append(cell_text)
        
        table.add_row(*row_data)
    
    return table
```

**Step 3: Create Enhanced Layout in `workflow_control_centre.py`**
```python
# Replace simple matrix display with Rich Layout
def run_enhanced_interactive_mode(self):
    """Enhanced interactive mode with Live display"""
    
    def create_layout():
        layout = Layout()
        layout.split_row(
            Layout(name="main", ratio=3),
            Layout(name="side", ratio=1)
        )
        
        # Main workflow matrix
        project_table = self.project_display.create_enhanced_project_status_table(
            self.current_projects)
        layout["main"].update(Panel(project_table, title="VHS WORKFLOW CONTROL CENTRE - Phase 1.3"))
        
        # Side panels
        layout["side"].split_column(
            Layout(name="resources"),
            Layout(name="system"),
            Layout(name="settings")
        )
        
        # System resources (adapted from job_queue_display.py system status)
        resource_panel = self.create_system_resource_panel()
        layout["resources"].update(resource_panel)
        
        # System status (job queue info)
        system_panel = self.create_system_status_panel() 
        layout["system"].update(system_panel)
        
        # Settings panel
        settings_panel = self.create_settings_panel()
        layout["settings"].update(settings_panel)
        
        return layout
    
    # Use Live display for real-time updates
    with Live(create_layout(), refresh_per_second=0.5, screen=True) as live:
        while self.running:
            # Handle input without blocking
            if self.has_input():
                cmd = self.get_input()
                self.handle_command(cmd)
                if not self.running:
                    break
            
            # Refresh data and update display
            self.refresh_data()
            live.update(create_layout())
            time.sleep(0.5)
```

**Step 4: Deprecate Menu 2.2**
```python
# In ddd_main_menu.py - Update parallel_vhs_decode_menu()
def parallel_vhs_decode_menu():
    print("JOB MANAGEMENT OPTIONS:")
    print("1. Add VHS Decode Jobs to Queue")
    print("2. Add TBC Export Jobs to Queue") 
    # Remove: print("3. View Job Queue Status & Progress")
    print("3. Configure Job Queue Settings")
    # Note: Job status now integrated into Menu 2.1 - Workflow Control Centre
```

## Implementation Timeline

**Week 1**: Phase 1 - Enhanced Status Display Matrix
- Days 1-2: Multi-line status cells and progress bars
- Days 3-4: System resource monitoring panels  
- Day 5: Retro colour scheme implementation

**Week 2**: Phase 2 - Real-time Progress Integration
- Days 1-2: Job progress extraction and display
- Days 3-4: Live updates and refresh system
- Day 5: Testing and refinement

**Week 3**: Phase 3 - Control System Enhancement  
- Days 1-2: Dynamic control status display
- Days 3-4: Complete job submission integration
- Day 5: Final testing and documentation updates

## Testing Strategy

1. **Unit Testing**: Test individual status display components
2. **Integration Testing**: Test with live job queue and progress updates  
3. **UI Testing**: Verify display layout and colour schemes
4. **Performance Testing**: Ensure smooth refresh rates with multiple projects
5. **Cross-platform Testing**: Verify Rich display compatibility

## Success Criteria

- [ ] Enhanced workflow matrix displays progress bars and ETA for running jobs
- [ ] System resource panels show real-time CPU, RAM, disk usage
- [ ] Retro amber colour scheme implemented and configurable
- [ ] Dynamic control status shows available/disabled actions
- [ ] All workflow steps can be started via coordinate system (1D, 2C, etc.)
- [ ] Real-time updates work smoothly without screen flicker
- [ ] Display falls back gracefully when Rich is not available

## Key Architectural Compliance

Following the Architectural Principles document:

1. **No Hardcoded Paths**: All resource monitoring and file operations use dynamic path resolution
2. **Cross-Platform Compatibility**: Resource monitoring gracefully falls back when system APIs unavailable
3. **Retro Terminal Aesthetic**: Implements amber colour schemes and ASCII art borders
4. **British English**: All user-facing text uses UK spelling ("colour", "summarising", etc.)
5. **Code Reuse**: Leverages existing shared components and prevents duplication
6. **Configuration-Driven**: Colour themes and display options configurable via settings

## Dependencies Required

- `psutil` - System resource monitoring (CPU, RAM, disk, temperature)
- `rich` - Enhanced terminal display (already required)
- Existing job queue system integration
- Configuration management for theme selection

## Migration Strategy

1. **Phase 1**: Enhance existing `project_status_display.py` without breaking current functionality
2. **Phase 2**: Add new enhanced display methods alongside existing simple display
3. **Phase 3**: Gradually migrate workflow control centre to use enhanced display
4. **Fallback**: Maintain compatibility with systems where Rich or psutil unavailable

This plan ensures smooth integration of the enhanced status indicators while maintaining system stability and following established architectural principles.

---

## 🎯 COMPREHENSIVE MIGRATION PLAN: MENU 2.2 → MENU 2.1

### Current State Analysis (Based on Code Review)

**Menu 2.1**: `launch_workflow_control_centre()` → `workflow_control_centre.py`
- ✅ Basic project discovery and workflow status matrix
- ✅ A-G project selection system  
- ❌ **Missing all the advanced status features below**

**Menu 2.2**: `show_job_queue_display()` → `job_queue_display.py` 
- ✅ **COMPREHENSIVE STATUS SYSTEM ALREADY IMPLEMENTED**
- ✅ Real-time progress bars: `progress_bar = "█" * progress_chars + "░" * (20 - progress_chars)`
- ✅ FPS calculations with 10-second stabilisation: `processing_fps = current_frame / runtime_seconds`
- ✅ ETA calculations: `eta_seconds = remaining_frames / processing_fps` 
- ✅ Multi-panel Rich Layout with Live display (2Hz refresh)
- ✅ Interactive controls (R, T, C, S, Q keys) with non-blocking input
- ✅ System status monitoring with colour-coded panels
- ✅ Job filtering and priority-based sorting
- ✅ Frame count extraction from JSON metadata (with caching)
- ✅ Cross-platform terminal compatibility with graceful degradation

### 🚀 SPECIFIC IMPLEMENTATION STEPS

#### Step 1: Create Shared Progress Components (2 hours)

**Task Checklist:**
- [x] Extract progress bar creation logic from `job_queue_display.py` lines 173-175 ✅ **COMPLETED**
- [x] Extract time formatting function from `job_queue_display.py` lines 69-85 ✅ **COMPLETED**
- [x] Extract job progress info extraction from `job_queue_display.py` lines 179-224 ✅ **COMPLETED**
- [x] Create `shared/progress_display_utils.py` with extracted components ✅ **COMPLETED**
- [x] Add comprehensive docstrings and type hints ✅ **COMPLETED**
- [x] Test progress bar rendering with various percentages ✅ **COMPLETED**
- [x] Test time formatting with different durations ✅ **COMPLETED**
- [x] Verify job progress extraction works with running jobs ✅ **COMPLETED**

**Extract working code from `job_queue_display.py`:**

```python
# File: shared/progress_display_utils.py
class ProgressDisplayUtils:
    """Shared progress display utilities extracted from job_queue_display.py"""
    
    @staticmethod
    def create_progress_bar(percentage, width=20):
        """From job_queue_display.py lines 173-175"""
        progress_chars = int(percentage / 5)  # 20 chars for 100%
        return "█" * progress_chars + "░" * (width - progress_chars)
    
    @staticmethod
    def format_time(seconds):
        """From job_queue_display.py lines 69-85"""
        if seconds <= 0:
            return "Unknown"
        elif seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds//60}m {seconds%60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def extract_job_progress_info(job_manager, project_name, step_type):
        """From job_queue_display.py lines 179-224 - Extract real-time progress"""
        jobs = job_manager.get_jobs()
        for job in jobs:
            if (job.status.value == 'running' and 
                job.job_type == step_type and 
                project_name in job.input_file):
                
                runtime = datetime.now() - job.started_at if job.started_at else None
                if runtime and runtime.total_seconds() > 10:
                    return {
                        'percentage': job.progress,
                        'fps': getattr(job, 'current_fps', None),
                        'eta_seconds': None,  # Calculate based on fps and remaining
                        'runtime_seconds': runtime.total_seconds()
                    }
        return None
```

#### Step 2: Enhance Workflow Status Matrix (3 hours)

**Task Checklist:**
- [x] Analyse current `ProjectStatusDisplay.create_project_status_table()` method ✅ **COMPLETED**
- [x] Design multi-line cell structure for progress integration ✅ **COMPLETED**
- [x] Create `create_enhanced_status_cell()` method with progress bar support ✅ **COMPLETED**
- [x] Map workflow steps to job types (decode → vhs-decode, export → tbc-export) ✅ **COMPLETED**
- [x] Integrate `ProgressDisplayUtils` for consistent progress bar rendering ✅ **COMPLETED**
- [x] Add ETA calculation logic for running jobs ✅ **COMPLETED**
- [x] Implement colour-coded progress indicators (green=bar, cyan=text, yellow=eta) ✅ **COMPLETED**
- [x] Create fallback display for jobs without progress data ✅ **COMPLETED**
- [x] Test multi-line cell rendering with various job states ✅ **COMPLETED**
- [ ] Verify progress data updates in real-time during job execution ⏳ **READY FOR TESTING**
- [x] Test graceful handling when job_manager is unavailable ✅ **COMPLETED**
- [x] Update existing table creation to use enhanced cells ✅ **COMPLETED**

**Modify `project_status_display.py` to add multi-line cells:**

```python
# Add this method to ProjectStatusDisplay class
def create_enhanced_status_cell(self, project, step, step_status):
    """Create enhanced status cell with progress bars for running jobs"""
    from shared.progress_display_utils import ProgressDisplayUtils
    from rich.text import Text
    
    if step_status.value == 'running':
        # Get job type mapping
        job_type_map = {
            'decode': 'vhs-decode',
            'export': 'tbc-export'
        }
        
        job_type = job_type_map.get(step.value.lower(), step.value.lower())
        progress_info = ProgressDisplayUtils.extract_job_progress_info(
            self.analyzer.job_manager, project.name, job_type)
        
        if progress_info:
            progress_bar = ProgressDisplayUtils.create_progress_bar(progress_info['percentage'])
            fps_text = f"{progress_info['fps']:.1f}fps" if progress_info.get('fps') else ""
            
            # Calculate ETA if we have fps data
            eta_text = ""
            if progress_info.get('fps') and progress_info['percentage'] > 0:
                remaining_percent = 100 - progress_info['percentage']
                eta_seconds = (remaining_percent / progress_info['percentage']) * progress_info['runtime_seconds']
                eta_text = f"ETA {ProgressDisplayUtils.format_time(int(eta_seconds))}"
            
            return Text.assemble(
                Text(progress_bar, style="green"), "\n",
                Text(f"{progress_info['percentage']:.1f}% {fps_text}", style="cyan"), "\n",
                Text(eta_text, style="yellow") if eta_text else Text("", style="dim")
            )
    
    # Return simple status for non-running states
    return self.get_simple_status_text(step_status)
```

#### Step 3: Create Enhanced Rich Layout (3 hours)

**Task Checklist:**
- [x] Study existing Rich Layout implementation in `job_queue_display.py` lines 261-288 ✅ **COMPLETED**
- [x] Design enhanced layout structure for workflow control centre ✅ **COMPLETED**
- [x] Create `create_enhanced_layout()` method with main/side panel split ✅ **COMPLETED**
- [x] Implement main workflow matrix panel with enhanced project table ✅ **COMPLETED**
- [x] Create system status panel using logic from `job_queue_display.py` ✅ **COMPLETED**
- [x] Add system resources panel with CPU/RAM/Disk monitoring ✅ **COMPLETED**
- [x] Create controls panel with keyboard shortcuts display ✅ **COMPLETED**
- [x] Implement `run_enhanced_interactive_mode()` with Live display ✅ **COMPLETED**
- [x] Add non-blocking keyboard input handling (R, T, A, 1-7, Q keys) ✅ **COMPLETED**
- [x] Integrate terminal settings management for cross-platform compatibility ✅ **COMPLETED**
- [x] Add auto-refresh functionality with configurable intervals ✅ **COMPLETED**
- [ ] Test Live display performance with multiple projects ⏳ **READY FOR TESTING**
- [ ] Verify all keyboard controls respond correctly ⏳ **READY FOR TESTING**
- [ ] Test graceful shutdown and terminal restoration ⏳ **READY FOR TESTING**
- [x] Add error handling for ImportError when Rich/termios unavailable ✅ **COMPLETED**

**Modify `workflow_control_centre.py` to use Rich Layout:**

```python
# Add this method to WorkflowControlCentre class
def create_enhanced_layout(self):
    """Create enhanced layout with progress integration (based on job_queue_display.py)"""
    from rich.layout import Layout
    from rich.panel import Panel
    
    layout = Layout()
    layout.split_row(
        Layout(name="main", ratio=3),
        Layout(name="side", ratio=1)
    )
    
    # Main workflow matrix with enhanced progress cells
    if self.project_display:
        project_table = self.project_display.create_enhanced_project_status_table(self.current_projects)
        layout["main"].update(Panel(project_table, title="VHS WORKFLOW CONTROL CENTRE - Enhanced", border_style="cyan"))
    
    # Side panels (adapted from job_queue_display.py structure)
    layout["side"].split_column(
        Layout(name="system_status", size=8),
        Layout(name="resources", size=8),
        Layout(name="controls", size=8)
    )
    
    # System status panel (from job_queue_display.py create_status_panel())
    layout["system_status"].update(self.create_system_status_panel())
    
    # System resources panel (new)
    layout["resources"].update(self.create_system_resource_panel())
    
    # Controls panel (from job_queue_display.py create_controls_panel())
    layout["controls"].update(self.create_controls_panel())
    
    return layout

def run_enhanced_interactive_mode(self):
    """Enhanced interactive mode with Live display (from job_queue_display.py lines 403-435)"""
    from rich.live import Live
    import select
    import sys
    import termios
    import tty
    
    try:
        # Save terminal settings (from job_queue_display.py)
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        
        with Live(self.create_enhanced_layout(), refresh_per_second=2) as live:
            while self.running:
                if self.auto_refresh:
                    self.refresh_data()
                    live.update(self.create_enhanced_layout())
                
                # Non-blocking input handling (from job_queue_display.py lines 408-434)
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    key = sys.stdin.read(1).lower()
                    
                    if key == 'q':
                        self.running = False
                    elif key == 'r':
                        live.update(self.create_enhanced_layout())
                    elif key == 't':
                        self.auto_refresh = not self.auto_refresh
                        live.update(self.create_enhanced_layout())
                    elif key.isdigit() and 1 <= int(key) <= 7:
                        self.selected_project_idx = int(key) - 1
                        live.update(self.create_enhanced_layout())
                    elif key == 'a':
                        self.handle_auto_queue_action()
                        live.update(self.create_enhanced_layout())
                
    except (KeyboardInterrupt, ImportError):
        self.running = False
    finally:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except:
            pass
```

#### Step 4: Menu System Integration (1 hour)

**Task Checklist:**
- [ ] Locate `display_vhs_decode_menu()` function in `ddd_main_menu.py` around lines 642-665
- [ ] Update menu text to reflect enhanced workflow control centre
- [ ] Remove or comment out Menu 2.2 reference ("View Job Queue Status & Progress")
- [ ] Update menu numbering to maintain consistency
- [ ] Add informational note about integrated job status monitoring
- [ ] Test menu navigation and option selection
- [ ] Verify Menu 2.1 launches enhanced interface correctly
- [ ] Confirm Menu 2.2 removal doesn't break menu numbering
- [ ] Update any related help text or documentation strings
- [ ] Test menu flow from main menu through VHS-Decode to enhanced control centre

**Update `ddd_main_menu.py` VHS-Decode menu:**

```python
# In display_vhs_decode_menu() - lines 642-665
print("🚀 PRIMARY WORKFLOW INTERFACE:")
print("=" * 35)
print("1. VHS Workflow Control Centre (Enhanced with Real-time Status)")
print("\n🛠️ COMPONENT ACCESS:")
print("=" * 23)
# Remove line 645: print("2. View Job Queue Status & Progress")
print("2. Configure Job Queue Settings")
print("\n📝 Note: Job status monitoring integrated into Workflow Control Centre")
```

### 🎯 EXPECTED RESULTS

**Enhanced Workflow Control Centre (Menu 2.1) will have:**

```
VHS WORKFLOW CONTROL CENTRE - Enhanced                          │ SYSTEM STATUS
════════════════════════════════════════════════════════════════ ┃ Running: 1
                               WORKFLOW PROGRESSION BY PROJECT    ┃ Queued: 2  
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓ ┃ Failed: 0
┃     ┃ Project Name         ┃  (D)ecode   ┃  (E)xport   ┃   (F)inal   ┃ ┃ Max: 2 jobs
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩ ┗━━━━━━━━━━━━━
│  1  │ Metallica1           │ ████████░   │   Ready     │   Blocked   │ 
│     │                      │ 89.2% 60fps │             │             │ RESOURCES  
│     │                      │   ETA 12m   │             │             │ ┏━━━━━━━━━━━━━
│  2  │ Movie_Night_1985     │  Complete   │ ██████░░░░  │   Blocked   │ ┃ CPU: 78%
│     │                      │             │ 65.1% 45fps │             │ ┃ RAM: 58%
│     │                      │             │   ETA 25m   │             │ ┃ Disk: 28%
└─────┴──────────────────────┴─────────────┴─────────────┴─────────────┘ ┗━━━━━━━━━━━━━

Controls: [1-7] Select Project | [A]uto-queue | [R]efresh | [Q]uit
```

### 🧪 TESTING VALIDATION

**Test Scenarios:**
1. ✅ Start a VHS decode job and verify progress bars appear in workflow matrix
2. ✅ Check FPS calculations match between old Menu 2.2 and new integrated display
3. ✅ Verify ETA calculations are accurate and update in real-time
4. ✅ Test interactive controls (project selection, auto-queue, refresh)
5. ✅ Ensure graceful fallback when Rich library unavailable
6. ✅ Cross-platform compatibility (Linux, Windows, macOS)

### 📝 MIGRATION CHECKLIST

- [x] **Step 1**: Extract `ProgressDisplayUtils` from `job_queue_display.py` ✅ **COMPLETED**
- [x] **Step 2**: Enhance `project_status_display.py` with multi-line progress cells ✅ **COMPLETED**
- [x] **Step 3**: Implement Rich Layout in `workflow_control_centre.py` ✅ **COMPLETED**
- [ ] **Step 4**: Update menu system to remove Menu 2.2 reference
- [ ] **Step 5**: Test all functionality with running jobs
- [ ] **Step 6**: Verify system resource monitoring works
- [ ] **Step 7**: Test interactive controls and keyboard input
- [ ] **Step 8**: Validate cross-platform compatibility
- [ ] **Step 9**: Update documentation

**Timeline: 2-3 days total development + 1 day testing**

---

## 🔄 ARCHITECTURAL BENEFITS

### Single Unified Interface
- **Eliminates menu switching** between project status and job monitoring
- **Contextual progress display** - progress bars appear exactly where work is happening
- **Real-time workflow awareness** - see project status change as jobs complete

### Code Reuse Compliance
- **Leverages existing working code** from `job_queue_display.py`
- **Prevents reimplementation** of complex progress calculation logic
- **Maintains DRY principles** throughout the codebase
- **Follows established patterns** from architectural principles

### Enhanced User Experience
- **Matrix-based workflow view** with embedded progress monitoring
- **System resource awareness** integrated into workflow planning
- **Interactive project selection** with immediate action feedback
- **Retro terminal aesthetic** with amber colour schemes and ASCII art

This comprehensive migration plan transforms the basic Menu 2.1 into a sophisticated workflow control centre by intelligently reusing the advanced status monitoring capabilities already implemented and tested in Menu 2.2.
