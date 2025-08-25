#!/usr/bin/env python3
"""
VHS Workflow Control Centre - Phase 1.3 Implementation
Unified workflow management with project matrix A-G, selection system, and rich interface
"""

import os
import sys
import time
import select
from enum import Enum
from typing import Dict, List, Optional, Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
    from rich.live import Live
    from rich import print as rprint
    from rich.box import HEAVY
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Rich library not available. Install with: pip install rich")

# Try importing keyboard for interactive input
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Keyboard library not available. Install with: pip install keyboard")

# Project phase 1.1-1.2 components
try:
    from project_discovery import ProjectDiscovery
    from workflow_analyzer import WorkflowAnalyzer, WorkflowStep, StepStatus
    from directory_manager import DirectoryManager
    from job_queue_manager import get_job_queue_manager
    from project_status_display import ProjectStatusDisplay, DisplayConfig
    COMPONENTS_AVAILABLE = True
except ImportError:
    COMPONENTS_AVAILABLE = False
    print("Missing required component modules - check project setup")

# Enum for control targets
class ControlTarget(Enum):
    NONE = 0
    PROJECT = 1
    JOB = 2
    GLOBAL = 3

def run_workflow_control_centre():
    """Main entry point function for menu integration
    
    This launches the full Phase 1.3 Workflow Control Centre implementation.
    """
    print("Starting VHS Workflow Control Centre...")
    print("Loading unified workflow interface...")
    
    # Initialize and run the full workflow control centre
    control_centre = WorkflowControlCentre()
    control_centre.run()
    return True

class WorkflowControlCentre:
    """Workflow Control Centre for unified post-capture workflow management

    This implements the Phase 1.3 architecture with:
    - Project Status Matrix with A-G project labels
    - Selection System with visual indicators
    - Control Target Resolution 
    - Dynamic Control Status feedback
    """
    def __init__(self):
        # Initialize debug logging
        self.debug_log_file = 'workflow_debug.log'
        self._init_debug_logging()
        """Initialize the workflow control centre"""
        # Initialize components from existing modules
        self.project_discovery = ProjectDiscovery() if COMPONENTS_AVAILABLE else None
        self.dir_manager = DirectoryManager() if COMPONENTS_AVAILABLE else None
        self.job_manager = get_job_queue_manager() if COMPONENTS_AVAILABLE else None
        self.workflow_analyzer = WorkflowAnalyzer(self.job_manager) if COMPONENTS_AVAILABLE else None
        
        # Console setup
        self.console = Console() if RICH_AVAILABLE else None
        
        # Initialize project status display with rich formatting
        if COMPONENTS_AVAILABLE and self.project_discovery and self.workflow_analyzer:
            display_config = DisplayConfig(
                project_column_width=20,
                step_column_width=11,
                auto_refresh_seconds=5.0,
                show_legend=True,
                show_summary=True,
                color_enabled=True
            )
            self.project_display = ProjectStatusDisplay(self.project_discovery, self.workflow_analyzer, display_config)
        else:
            self.project_display = None
        
        # Selection state
        self.selected_project_idx = None  # A-G selection
        self.selected_job_idx = None      # 1-9 selection
        self.current_projects = []        # List of discovered projects
        self.current_jobs = []            # List of active jobs
        
        # Layout components
        self.layout = None
        
        # Control flags
        self.running = True
        self.refresh_interval = 2.0
        self.show_legend = True
        self.last_refresh = 0
        self.message = ""
        self.auto_refresh = True
        self.enhanced_mode = True  # Use enhanced Rich layout by default
        
        # Adaptive refresh settings
        self.base_refresh_interval = 10.0  # Base refresh interval in seconds
        self.active_refresh_interval = 3.0  # Faster refresh when jobs are active
        self.last_refresh_time = 0
        
        # Get all processing locations from config.json and capture directory
        self.directories = []
        directory_set = set()  # Use set to avoid duplicates
        
        try:
            from config import load_config
            config = load_config()
            
            # Add capture directory
            capture_dir = config.get('capture_directory')
            if capture_dir and os.path.exists(capture_dir) and os.path.isdir(capture_dir):
                directory_set.add(capture_dir)
            
            # Add all processing locations
            config_dirs = config.get('processing_locations', [])
            for directory in config_dirs:
                if os.path.exists(directory) and os.path.isdir(directory):
                    directory_set.add(directory)
                    
        except Exception as e:
            print(f"Warning: Could not load processing locations from config: {e}")
        
        # Convert set back to list
        self.directories = list(directory_set)
    
    def _init_debug_logging(self):
        """Initialize debug logging to file"""
        try:
            # Clear the log file at startup
            with open(self.debug_log_file, 'w') as f:
                f.write("=== Workflow Control Centre Debug Log ===\n")
                f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        except Exception:
            # If we can't write to log file, disable debug logging
            self.debug_log_file = None
    
    def _debug_log(self, message):
        """Write debug message to log file only"""
        if self.debug_log_file:
            try:
                with open(self.debug_log_file, 'a') as f:
                    timestamp = time.strftime('%H:%M:%S')
                    f.write(f"[{timestamp}] {message}\n")
                    f.flush()  # Ensure it's written immediately
            except Exception:
                # If logging fails, silently continue
                pass
    
    def run(self):
        """Run the workflow control centre"""
        print("\nVHS WORKFLOW CONTROL CENTRE")
        print("=" * 35)
        print("Phase 1.3 Implementation - Unified workflow management")
        print("\nThis interface provides:")
        print("• Project Status Matrix with A-G labels")
        print("• Visual selection system")
        print("• Dynamic control status feedback")
        print("• Integration with job queue management")
        print()
        
        if not COMPONENTS_AVAILABLE:
            print("Warning: Component modules not available.")
            print("Some features may be limited. Please check:")
            print("• project_discovery.py")
            print("• workflow_analyzer.py")
            print("• directory_manager.py")
            print("• job_queue_manager.py")
            print()
        
        if not self.directories:
            print("Warning: No processing locations configured.")
            print("Please configure processing locations first via:")
            print("   Main Menu → Configuration → Manage Processing Locations")
            input("\nPress Enter to return to menu...")
            return
        
        # Initial data refresh
        self.refresh_data()
        
        print(f"Scanning {len(self.directories)} processing locations...")
        print(f"Found {len(self.current_projects)} projects")
        print(f"Active jobs: {len(self.current_jobs)}")
        print()
        
        # Use enhanced Rich interactive mode
        self.run_enhanced_interactive_mode()
    
    def run_enhanced_interactive_mode(self):
        """Run enhanced interactive mode with Live display and visible command input"""
        try:
            import termios
            import tty
            
            # Initialize command input buffer
            self.current_input = ""
            self.input_cursor_blink = True
            
            # Save original terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
            with Live(self.create_enhanced_layout(), refresh_per_second=4) as live:  # Higher refresh for cursor blink
                while self.running:
                    if self.auto_refresh:
                        self.refresh_data()
                    
                    # Update cursor blink state
                    self.input_cursor_blink = not self.input_cursor_blink
                    live.update(self.create_enhanced_layout())
                    
                    # Non-blocking input check with multi-character support
                    if select.select([sys.stdin], [], [], 0.25)[0]:  # Shorter timeout for responsiveness
                        key = sys.stdin.read(1)
                        
                        if key == '\r' or key == '\n':  # Enter key
                            if self.current_input.strip():
                                # Process the complete command
                                cmd = self.current_input.strip().lower()
                                self.current_input = ""  # Clear input buffer
                                
                                if cmd == 'q':
                                    self.running = False
                                elif cmd == 'h':
                                    # Show help - temporarily stop live display
                                    live.stop()
                                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                                    self.show_help()
                                    tty.setcbreak(sys.stdin.fileno())
                                    live.start()
                                elif cmd == 'd':
                                    # Show details - temporarily stop live display
                                    live.stop()
                                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                                    self.show_details()
                                    tty.setcbreak(sys.stdin.fileno())
                                    live.start()
                                else:
                                    # Handle command through existing command handler
                                    self.handle_command(cmd)
                                
                                live.update(self.create_enhanced_layout())
                            else:
                                # Empty command - just clear input
                                self.current_input = ""
                                live.update(self.create_enhanced_layout())
                                
                        elif key == '\x7f' or key == '\x08':  # Backspace
                            if self.current_input:
                                self.current_input = self.current_input[:-1]
                                live.update(self.create_enhanced_layout())
                                
                        elif key == '\x03':  # Ctrl+C
                            self.running = False
                            
                        elif key == '\x1b':  # Escape key
                            self.current_input = ""
                            live.update(self.create_enhanced_layout())
                            
                        elif key.isprintable() and len(self.current_input) < 50:  # Limit input length
                            self.current_input += key
                            live.update(self.create_enhanced_layout())
                    
                    # Shorter sleep for better responsiveness
                    if not self.auto_refresh:
                        time.sleep(0.5)
                        
        except (KeyboardInterrupt, EOFError):
            self.running = False
        except ImportError:
            # Fallback if termios not available (Windows)
            print("\nAdvanced terminal controls not available on this system.")
            print("The rich interface requires advanced terminal controls.")
            print("Please install termios support or use a compatible terminal.")
            input("Press Enter to exit...")
            return
        finally:
            try:
                # Restore original terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass
    
    def create_enhanced_layout(self):
        """Create enhanced layout with progress integration and visible command input"""
        from rich.layout import Layout
        from rich.panel import Panel
        
        # Main layout with input panel at bottom
        layout = Layout()
        layout.split_column(
            Layout(name="top_section", ratio=5),
            Layout(name="command_input", size=6)
        )
        
        # Split top section into main content and side panel
        layout["top_section"].split_row(
            Layout(name="main", ratio=4),
            Layout(name="side", ratio=1)
        )
        
        # Main workflow matrix with enhanced progress cells
        if self.project_display:
            project_table = self.project_display.create_enhanced_project_status_table(self.current_projects)
            layout["main"].update(Panel(project_table, title="VHS WORKFLOW CONTROL CENTRE - Enhanced", border_style="cyan"))
        else:
            # Fallback if project display not available
            fallback_table = self._create_fallback_enhanced_table()
            layout["main"].update(Panel(fallback_table, title="VHS WORKFLOW CONTROL CENTRE - Basic", border_style="cyan"))
        
        # Side panels for status and controls
        layout["side"].split_column(
            Layout(name="system_status", size=8),
            Layout(name="resources", size=8),
            Layout(name="controls", size=20)
        )
        
        # System status panel
        layout["system_status"].update(self.create_system_status_panel())
        
        # System resources panel
        layout["resources"].update(self.create_system_resource_panel())
        
        # Controls panel
        layout["controls"].update(self.create_controls_panel())
        
        # Command input panel at bottom
        layout["command_input"].update(self.create_command_input_panel())
        
        return layout
    
    def _create_fallback_enhanced_table(self):
        """Create fallback table when project_display is not available"""
        from rich.table import Table
        from rich.text import Text
        
        table = Table(title="WORKFLOW PROGRESSION BY PROJECT", box=HEAVY, show_header=True)
        
        # Add columns
        table.add_column("Project", width=20, style="cyan", no_wrap=True)
        table.add_column("(C)apture", width=13, justify="center")
        table.add_column("(D)ecode", width=13, justify="center") 
        table.add_column("Co(m)press", width=13, justify="center")
        table.add_column("(E)xport", width=13, justify="center")
        table.add_column("(A)lign", width=13, justify="center")
        table.add_column("(F)inal", width=13, justify="center")
        
        # Add project rows (up to 7)
        for idx in range(7):
            project_num = idx + 1
            is_selected = self.selected_project_idx == idx
            
            if idx < len(self.current_projects):
                project = self.current_projects[idx]
                
                # Create label with selection indicator
                if is_selected:
                    project_name = f"►{project_num}. {project.name}"
                    project_style = "bold yellow"
                else:
                    project_name = f" {project_num}. {project.name}"
                    project_style = "white"
                
                # Simple status display
                table.add_row(
                    Text(project_name, style=project_style),
                    "Complete",
                    "Ready" if hasattr(project, 'workflow_status') else "Unknown",
                    "Missing",
                    "Missing",
                    "Missing",
                    "Missing"
                )
            else:
                # Empty row
                if is_selected:
                    project_name = f"►{project_num}. ---"
                    project_style = "bold yellow"
                else:
                    project_name = f" {project_num}. ---"
                    project_style = "dim"
                
                table.add_row(
                    Text(project_name, style=project_style),
                    "---", "---", "---", "---", "---", "---"
                )
        
        return table
    
    def create_system_status_panel(self):
        """Create system status panel (from job_queue_display.py create_status_panel())"""
        from rich.text import Text
        
        status_content = Text()
        
        if self.job_manager:
            try:
                status = self.job_manager.get_queue_status_nonblocking(timeout=0.1)
                
                if status is None:
                    status_content.append("Job Status: Unavailable (busy)", style="red")
                else:
                    # Queue statistics
                    status_content.append(f"Total Jobs: {status.get('total_jobs', 0)}", style="white")
                    status_content.append(" | ", style="dim")
                    status_content.append(f"Running: {status.get('running', 0)}", style="green")
                    status_content.append(" | ", style="dim")
                    status_content.append(f"Queued: {status.get('queued', 0)}", style="yellow")
                    
                    if status.get('failed', 0) > 0:
                        status_content.append(" | ", style="dim")
                        status_content.append(f"Failed: {status.get('failed', 0)}", style="red")
                    
                    status_content.append("\n")
                    processor_status = "Running" if status.get('processor_running', False) else "Stopped"
                    processor_style = "green" if status.get('processor_running', False) else "red"
                    status_content.append(f"Processor: {processor_status}", style=processor_style)
                    
            except Exception:
                status_content.append("Job Status: Check failed", style="red")
        else:
            status_content.append("Job Manager: Not available", style="red")
        
        status_content.append("\n")
        status_content.append(f"Projects: {len(self.current_projects)}", style="cyan")
        status_content.append(" | ", style="dim")
        status_content.append(f"Locations: {len(self.directories)}", style="cyan")
        
        return Panel(status_content, title="System Status", border_style="blue")
    
    def create_system_resource_panel(self):
        """Create system resource monitoring panel"""
        from rich.text import Text
        from rich.table import Table
        
        try:
            import psutil
            
            resource_table = Table(show_header=False, box=None, padding=(0, 0))
            resource_table.add_column("Resource", style="bold", width=5)
            resource_table.add_column("Usage", width=12)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_bar = self._create_resource_bar(cpu_percent, width=8)
            resource_table.add_row("CPU:", f"{cpu_bar} {cpu_percent:.0f}%")
            
            # Memory usage  
            memory = psutil.virtual_memory()
            memory_bar = self._create_resource_bar(memory.percent, width=8)
            resource_table.add_row("RAM:", f"{memory_bar} {memory.percent:.0f}%")
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_bar = self._create_resource_bar(disk_percent, width=8)
            resource_table.add_row("Disk:", f"{disk_bar} {disk_percent:.0f}%")
            
            return Panel(resource_table, title="Resources", border_style="green")
            
        except ImportError:
            # Fallback when psutil not available
            fallback_content = Text()
            fallback_content.append("System monitoring\n", style="dim")
            fallback_content.append("requires psutil\n", style="dim")
            fallback_content.append("pip install psutil", style="yellow")
            return Panel(fallback_content, title="Resources", border_style="green")
        except Exception as e:
            # Error getting system info
            error_content = Text()
            error_content.append("Resource info\n", style="red")
            error_content.append("unavailable", style="red")
            return Panel(error_content, title="Resources", border_style="green")
    
    def _create_resource_bar(self, percentage, width=8):
        """Create a resource usage bar"""
        filled_chars = int((percentage / 100.0) * width)
        empty_chars = width - filled_chars
        return "█" * filled_chars + "░" * empty_chars
    
    def create_controls_panel(self):
        """Create controls panel with keyboard shortcuts display"""
        from rich.text import Text
        
        controls = Text("Controls", style="bold green")
        controls.append("\n")
        controls.append("═" * 25, style="dim")
        controls.append("\n")
        controls.append("1-7", style="bold cyan")
        controls.append(" - Select Project\n", style="white")
        controls.append("1d, 2e", style="bold yellow")
        controls.append(" - Start Jobs\n", style="white")
        controls.append("stop 1d", style="bold red")
        controls.append(" - Stop Jobs\n", style="white")
        controls.append("force 1e", style="bold magenta")
        controls.append(" - Force Overwrite\n", style="white")
        controls.append("clean 1e", style="bold bright_blue")
        controls.append(" - Reset Progress\n", style="white")
        controls.append("auto", style="bold cyan")
        controls.append(" - Auto-queue\n", style="white")
        controls.append("cleanup", style="bold orange1")
        controls.append(" - Clean /tmp\n", style="white")
        controls.append("settemp", style="bold green")
        controls.append(" - Set temp dir\n", style="white")
        controls.append("\n")
        controls.append("d", style="bold cyan")
        controls.append(" - Details\n", style="white")
        controls.append("h", style="bold cyan")
        controls.append(" - Help\n", style="white")
        controls.append("q", style="bold red")
        controls.append(" - Quit & Exit\n", style="white")
        controls.append("\n")
        controls.append("═" * 25, style="dim")
        
        return Panel(controls, title="Controls", border_style="magenta")
    
    
    def create_command_input_panel(self):
        """Create command input panel with visible text input area"""
        from rich.text import Text
        from rich.table import Table
        
        # Create input display table
        input_table = Table(show_header=False, box=None, padding=(0, 1))
        input_table.add_column("Label", style="bold cyan", width=8)
        input_table.add_column("Input", style="yellow", width=25)
        input_table.add_column("Examples", style="dim", width=20)
        
        # Show current input buffer (if any) or prompt
        current_input = getattr(self, 'current_input', '')
        cursor_blink = getattr(self, 'input_cursor_blink', True)
        cursor = "█" if cursor_blink else " "  # Blinking cursor effect
        display_input = f"{current_input}{cursor}"
        
        input_table.add_row(
            "Command:",
            display_input,
            "1d, 2e, auto, h"
        )
        
        # Add status line
        status_text = Text()
        status_text.append("Type command and press Enter  ", style="white")
        status_text.append("| ", style="dim")
        status_text.append("Examples: 1d (decode proj 1), 2e (export proj 2), auto (queue all)", style="dim")
        
        # Create content with input area and status
        content = Text()
        content.append("Command Input\n", style="bold green")
        
        # Add the table content manually since we can't embed Table in Text
        content.append(f"Command: ", style="bold cyan")
        content.append(f"{display_input:<25}", style="yellow")
        content.append(f" Examples: 1d, 2e, auto\n", style="dim")
        content.append("\n")
        content.append("Type command and press Enter  ", style="white")
        content.append("| ", style="dim")
        content.append("Use coordinate system (1d, 2e) or actions (auto, h)", style="dim")
        
        return Panel(content, title="Command Input", border_style="yellow")
    
    def refresh_data(self):
        """Refresh project and job data (non-blocking)"""
        # Update project data
        if self.project_discovery and self.workflow_analyzer:
            try:
                # Discover projects with timeout to avoid blocking on slow filesystem
                self.current_projects = self.project_discovery.discover_projects(self.directories)
                
                # Analyze each project's workflow status with timeout protection
                for project in self.current_projects:
                    try:
                        project.workflow_status = self.workflow_analyzer.analyze_project_workflow(project)
                    except Exception as e:
                        # If analysis fails for one project, continue with others
                        # Create a basic workflow status to avoid UI errors
                        from workflow_analyzer import WorkflowStatus, WorkflowStep, StepStatus
                        project.workflow_status = WorkflowStatus(project_name=project.name)
                        for step in WorkflowStep:
                            project.workflow_status.steps[step] = StepStatus.MISSING
                        
            except Exception as e:
                # If project discovery fails entirely, continue with empty project list
                self.current_projects = []
        
        # Update job data with timeout to avoid blocking UI
        if self.job_manager:
            try:
                # Try to acquire jobs with a short timeout
                import threading
                jobs = None
                
                # Use non-blocking method instead of threading workaround
                jobs = self.job_manager.get_jobs_nonblocking(timeout=0.1)
                
                if jobs is None:
                    # Job manager is busy - skip refresh to avoid blocking UI
                    return
                
                if jobs is not None:
                    # Filter to only active jobs (running, queued, failed)
                    self.current_jobs = []
                    self._debug_log(f"Found {len(jobs)} total jobs from job manager")
                    for job_idx, job in enumerate(jobs):
                        if hasattr(job, 'status'):
                            status_str = str(job.status).lower()
                            self._debug_log(f"Job {job_idx} raw status: {job.status}, string: {status_str}")
                            
                            # Check if status contains running, queued, or failed
                            if any(active_status in status_str for active_status in ['running', 'queued', 'failed']):
                                # Convert job object to dict format for easier handling
                                job_dict = {
                                    'job_id': getattr(job, 'job_id', '?'),
                                    'project_name': getattr(job, 'project_name', 'Unknown'),
                                    'job_type': getattr(job, 'job_type', 'Unknown'),
                                    'status': getattr(job, 'status', 'Unknown'),
                                    'progress': getattr(job, 'progress', 0),
                                    'fps': getattr(job, 'fps', '-'),
                                    'eta_str': getattr(job, 'eta_str', '-')
                                }
                                self._debug_log(f"Job {job_idx}: ID={job_dict['job_id']}, Project={job_dict['project_name']}, Type={job_dict['job_type']}, Status={job_dict['status']}, Progress={job_dict['progress']}")
                                self.current_jobs.append(job_dict)
                            else:
                                self._debug_log(f"Skipping job {job_idx} with status: {status_str}")
                        else:
                            self._debug_log(f"Job {job_idx} has no status attribute")
            except Exception as e:
                # If job refresh fails, continue with UI - don't block
                pass
    
    
    def get_selection_info(self):
        """Get current selection information string"""
        if self.selected_project_idx is not None:
            project_num = self.selected_project_idx + 1
            if 0 <= self.selected_project_idx < len(self.current_projects):
                project_name = self.current_projects[self.selected_project_idx].name
                return f"Project {project_num} ({project_name})"
            else:
                return f"Project {project_num} (empty)"
        elif self.selected_job_idx is not None:
            job_num = self.selected_job_idx + 1
            if 0 <= self.selected_job_idx < len(self.current_jobs):
                job = self.current_jobs[self.selected_job_idx]
                project_name = job.get('project_name', 'Unknown')
                return f"Job J{job_num} ({project_name})"
            else:
                return f"Job J{job_num} (empty)"
        else:
            return "None - Use 1D, 2C, etc. for direct actions"
    
    def handle_command(self, cmd):
        """Handle user command input"""
        # Coordinate system commands (1D, 2C, etc.)
        if len(cmd) == 2 and cmd[0].isdigit() and cmd[1] in "dcaef":
            project_num = int(cmd[0])
            step_letter = cmd[1]
            self.handle_coordinate_command(project_num, step_letter)
        
        # Project selection (1-7)
        elif cmd in "1234567":
            idx = int(cmd) - 1
            if idx < len(self.current_projects):
                self.selected_project_idx = idx
                self.selected_job_idx = None  # Clear job selection
                project = self.current_projects[idx]
                self.message = f"Selected Project {cmd}: {project.name}"
            else:
                self.message = f"No project at position {cmd}"
        
        # Job selection (J1-J9)
        elif cmd.startswith('j') and len(cmd) == 2 and cmd[1] in "123456789":
            idx = int(cmd[1]) - 1
            if idx < len(self.current_jobs):
                self.selected_job_idx = idx
                self.selected_project_idx = None  # Clear project selection
                job = self.current_jobs[idx]
                self.message = f"Selected Job J{cmd[1]}: {job.get('project_name', 'Unknown')}"
            else:
                self.message = f"No job at position J{cmd[1]}"
        
        # Force command (force 1e, force 2d, etc.)
        elif cmd.startswith('force ') and len(cmd) >= 8:
            force_cmd = cmd[6:].strip()
            if len(force_cmd) == 2 and force_cmd[0].isdigit() and force_cmd[1] in "dcaef":
                project_num = int(force_cmd[0])
                step_letter = force_cmd[1]
                self.handle_force_command(project_num, step_letter)
            else:
                self.message = f"Invalid force command format. Use: force 1e, force 2d, etc."
        
        # Clean command to reset stuck progress displays
        elif cmd.startswith('clean ') and len(cmd) >= 8:
            clean_cmd = cmd[6:].strip()
            if len(clean_cmd) == 2 and clean_cmd[0].isdigit() and clean_cmd[1] in "dcaef":
                project_num = int(clean_cmd[0])
                step_letter = clean_cmd[1]
                self.handle_clean_command(project_num, step_letter)
            else:
                self.message = f"Invalid clean command format. Use: clean 1e, clean 2d, etc."
        
        # Stop command (stop 1e, stop 2d, etc.)
        elif cmd.startswith('stop ') and len(cmd) >= 7:
            stop_cmd = cmd[5:].strip()
            if len(stop_cmd) == 2 and stop_cmd[0].isdigit() and stop_cmd[1] in "dcaef":
                project_num = int(stop_cmd[0])
                step_letter = stop_cmd[1]
                self.handle_stop_command(project_num, step_letter)
            else:
                self.message = f"Invalid stop command format. Use: stop 1e, stop 2d, etc."
        
        # Action commands
        elif cmd == 'x':  # Stop
            self.stop_selected_item()
        elif cmd == 'r':  # Retry
            self.retry_selected_item()
        elif cmd == 'd':  # Details
            self.show_details()
        elif cmd == 'auto':  # Auto-queue
            self.auto_queue_jobs()
        elif cmd == 'h':  # Help
            self.show_help()
        elif cmd == 'cleanup':  # Cleanup temp files
            self.cleanup_temp_files()
        elif cmd == 'settemp':  # Set temp directory
            self.set_temp_directory()
        else:
            self.message = f"Unknown command: {cmd}"
    
    def handle_coordinate_command(self, project_num, step_letter):
        """Handle coordinate-based commands like 1D, 2C, etc."""
        project_idx = project_num - 1
        
        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        
        project = self.current_projects[project_idx]
        
        # Map step letters to workflow steps
        step_map = {
            'd': WorkflowStep.DECODE,
            'c': WorkflowStep.COMPRESS, 
            'e': WorkflowStep.EXPORT,
            'a': WorkflowStep.ALIGN,
            'f': WorkflowStep.FINAL
        }
        
        if step_letter not in step_map:
            self.message = f"Invalid step letter: {step_letter.upper()}"
            return
        
        workflow_step = step_map[step_letter]
        step_name = workflow_step.value.title()
        
        # Check workflow status
        if hasattr(project, 'workflow_status') and self.workflow_analyzer:
            step_status = project.workflow_status.steps.get(workflow_step, StepStatus.MISSING)
            
            if step_status == StepStatus.READY:
                # Start the job
                if self.job_manager:
                    try:
                        success = self._submit_workflow_job(project, workflow_step)
                        if success:
                            self.message = f"Started {step_name} for Project {project_num} ({project.name})"
                        else:
                            self.message = f"Failed to start {step_name} for Project {project_num}"
                    except Exception as e:
                        self.message = f"Error starting {step_name}: {str(e)}"
                else:
                    self.message = f"Job manager not available - cannot start {step_name}"
            elif step_status == StepStatus.FAILED:
                # Retry the failed job
                if self.job_manager:
                    try:
                        success = self._submit_workflow_job(project, workflow_step)
                        if success:
                            self.message = f"Retrying {step_name} for Project {project_num} ({project.name})"
                        else:
                            self.message = f"Failed to retry {step_name} for Project {project_num}"
                    except Exception as e:
                        self.message = f"Error retrying {step_name}: {str(e)}"
                else:
                    self.message = f"Job manager not available - cannot retry {step_name}"
            elif step_status == StepStatus.COMPLETE:
                # Check if output file actually exists before declaring it complete
                output_exists = self._check_step_output_exists(project, workflow_step)
                if not output_exists:
                    # Output file missing - warn user but don't auto-restart
                    self.message = f"Warning: {step_name} marked complete but output file missing for Project {project_num}. Use 'force {project_num}{step_letter}' to restart"
                else:
                    # Output exists, ask for confirmation to overwrite
                    self.message = f"Warning: {step_name} complete for Project {project_num}. Use 'force {project_num}{step_letter}' to overwrite"
            elif step_status == StepStatus.PROCESSING:
                self.message = f"{step_name} is already processing for Project {project_num} ({project.name})"
            elif step_status == StepStatus.MISSING:
                self.message = f"{step_name} is blocked (dependencies not met) for Project {project_num} ({project.name})"
            else:
                self.message = f"{step_name} is not available for Project {project_num} ({project.name})"
        else:
            self.message = f"Cannot determine workflow status for Project {project_num}"
    
    def start_selected_item(self):
        """Start the selected project's next workflow step"""
        if self.selected_project_idx is not None and 0 <= self.selected_project_idx < len(self.current_projects):
            project = self.current_projects[self.selected_project_idx]
            
            # Determine next ready step
            if hasattr(project, 'workflow_status') and self.workflow_analyzer:
                ready_steps = []
                for step, status in project.workflow_status.steps.items():
                    if status == StepStatus.READY:
                        ready_steps.append(step)
                
                if ready_steps:
                    # Start the first ready step
                    step_to_start = ready_steps[0]
                    step_name = step_to_start.value.title()
                    
                    # Try to submit job via job manager
                    if self.job_manager:
                        try:
                            # Create job based on step type
                            success = self._submit_workflow_job(project, step_to_start)
                            if success:
                                self.message = f"Started {step_name} job for {project.name}"
                            else:
                                self.message = f"Failed to start {step_name} job for {project.name}"
                        except Exception as e:
                            self.message = f"Error starting {step_name}: {str(e)}"
                    else:
                        self.message = f"Job manager not available - cannot start {step_name}"
                else:
                    self.message = f"No workflow steps ready for {project.name}"
            else:
                self.message = f"Cannot determine workflow status for {project.name}"
        else:
            self.message = "No project selected. Use A-G to select a project."
    
    def pause_selected_item(self):
        """Pause the selected job"""
        if self.selected_job_idx is not None and 0 <= self.selected_job_idx < len(self.current_jobs):
            job = self.current_jobs[self.selected_job_idx]
            self.message = f"Pause operation for job {job.get('job_id', '?')} - Feature not fully implemented yet"
        else:
            self.message = "No job selected. Use 1-9 to select a job."
    
    def retry_selected_item(self):
        """Retry the selected failed job or project step"""
        if self.selected_job_idx is not None and 0 <= self.selected_job_idx < len(self.current_jobs):
            job = self.current_jobs[self.selected_job_idx]
            self.message = f"Retry operation for job {job.get('job_id', '?')} - Feature not fully implemented yet"
        elif self.selected_project_idx is not None and 0 <= self.selected_project_idx < len(self.current_projects):
            project = self.current_projects[self.selected_project_idx]
            self.message = f"Retry operation for {project.name} - Feature not fully implemented yet"
        else:
            self.message = "No job or project selected. Use A-G or 1-9 to select."
    
    def stop_selected_item(self):
        """Stop the selected job"""
        if self.selected_job_idx is not None and 0 <= self.selected_job_idx < len(self.current_jobs):
            job = self.current_jobs[self.selected_job_idx]
            self.message = f"Stop operation for job {job.get('job_id', '?')} - Feature not fully implemented yet"
        else:
            self.message = "No job selected. Use J1-J9 to select a job."
    
    def cancel_selected_item(self):
        """Cancel the selected job"""
        if self.selected_job_idx is not None and 0 <= self.selected_job_idx < len(self.current_jobs):
            job = self.current_jobs[self.selected_job_idx]
            self.message = f"Cancel operation for job {job.get('job_id', '?')} - Feature not fully implemented yet"
        else:
            self.message = "No job selected. Use J1-J9 to select a job."
    
    def show_details(self):
        """Show details for the selected project or job"""
        if self.selected_job_idx is not None and 0 <= self.selected_job_idx < len(self.current_jobs):
            job = self.current_jobs[self.selected_job_idx]
            self._show_job_details(job)
        elif self.selected_project_idx is not None and 0 <= self.selected_project_idx < len(self.current_projects):
            project = self.current_projects[self.selected_project_idx]
            self._show_project_details(project)
        else:
            self.message = "No job or project selected. Use A-G or 1-9 to select."
    
    def _show_job_details(self, job):
        """Display detailed information about a job"""
        clear_screen()
        display_header()
        
        print("\nJOB DETAILS")
        print("=" * 40)
        
        job_id = job.get('job_id', 'Unknown')
        print(f"Job ID: {job_id}")
        print(f"Project: {job.get('project_name', 'Unknown')}")
        print(f"Type: {job.get('job_type', 'Unknown')}")
        print(f"Status: {job.get('status', 'Unknown')}")
        print(f"Progress: {job.get('progress', 0)}%")
        
        print("\nParameters:")
        for key, value in job.items():
            if key not in ['job_id', 'project_name', 'job_type', 'status', 'progress']:
                print(f"  {key}: {value}")
        
        input("\nPress Enter to return to control centre...")
    
    def _show_project_details(self, project):
        """Display detailed information about a project"""
        clear_screen()
        display_header()
        
        print("\nPROJECT DETAILS")
        print("=" * 40)
        
        print(f"Project Name: {project.name}")
        
        # Show file information
        print("\nFile Information:")
        if hasattr(project, 'rf_file') and project.rf_file:
            print(f"  RF File: {project.rf_file}")
            if os.path.exists(project.rf_file):
                size_mb = os.path.getsize(project.rf_file) / (1024 * 1024)
                print(f"    Size: {size_mb:.2f} MB")
        
        if hasattr(project, 'audio_file') and project.audio_file:
            print(f"  Audio File: {project.audio_file}")
            if os.path.exists(project.audio_file):
                size_mb = os.path.getsize(project.audio_file) / (1024 * 1024)
                print(f"    Size: {size_mb:.2f} MB")
        
        # Show workflow status
        if hasattr(project, 'workflow_status'):
            print("\nWorkflow Status:")
            for step, status in project.workflow_status.steps.items():
                print(f"  {step.name}: {status.name}")
        
        input("\nPress Enter to return to control centre...")
    
    def auto_queue_jobs(self):
        """Automatically queue all ready workflow steps for all projects"""
        if not self.job_manager:
            self.message = "Job manager not available - cannot auto-queue jobs"
            return
            
        jobs_queued = 0
        
        for project in self.current_projects:
            if hasattr(project, 'workflow_status') and self.workflow_analyzer:
                for step, status in project.workflow_status.steps.items():
                    if status == StepStatus.READY:
                        try:
                            success = self._submit_workflow_job(project, step)
                            if success:
                                jobs_queued += 1
                        except Exception as e:
                            # Continue with other jobs even if one fails
                            continue
        
        if jobs_queued > 0:
            self.message = f"Queued {jobs_queued} ready workflow jobs"
        else:
            self.message = "No ready workflow steps found to queue"
    
    def _submit_workflow_job(self, project, workflow_step, force_overwrite=False):
        """Submit a job for a specific workflow step
        
        Args:
            project: Project object
            workflow_step: WorkflowStep enum value
            force_overwrite: bool: Whether to force overwrite existing output files
            
        Returns:
            bool: True if job was successfully submitted
        """
        # Use a background thread to avoid blocking UI on slow filesystem operations
        import threading
        import queue as thread_queue
        
        result_queue = thread_queue.Queue()
        
        def background_job_submission():
            """Background thread function to handle filesystem operations and job submission"""
            try:
                self._submit_workflow_job_background(project, workflow_step, force_overwrite, result_queue)
            except Exception as e:
                result_queue.put((False, str(e)))
        
        # Start background thread
        thread = threading.Thread(target=background_job_submission, daemon=True)
        thread.start()
        
        # Wait for result with timeout to avoid blocking UI indefinitely
        try:
            success, message = result_queue.get(timeout=2.0)  # 2 second timeout
            if message and not success:
                self.message = message
            return success
        except thread_queue.Empty:
            self.message = f"Warning: Job submission taking too long - continuing in background"
            return True  # Assume success to avoid blocking UI
    
    def _submit_workflow_job_background(self, project, workflow_step, force_overwrite, result_queue):
        """Background thread implementation of job submission with filesystem operations"""
        try:
            # Import necessary functions
            from job_queue_manager import get_job_queue_manager
            
            job_manager = get_job_queue_manager()
            
            # Determine job type and parameters based on workflow step
            if workflow_step == WorkflowStep.DECODE:
                # Submit VHS decode job using job queue manager directly
                rf_file = None
                if hasattr(project, 'capture_files') and 'video' in project.capture_files:
                    rf_file = project.capture_files['video']
                elif hasattr(project, 'rf_file'):
                    rf_file = project.rf_file
                    
                if not rf_file or not os.path.exists(rf_file):
                    self.message = f"RF file not found for {project.name} (tried: {rf_file})"
                    return False
                
                # Handle both .lds and .ldf extensions
                if rf_file.endswith('.lds'):
                    tbc_file = rf_file.replace('.lds', '.tbc')
                elif rf_file.endswith('.ldf'):
                    tbc_file = rf_file.replace('.ldf', '.tbc')
                else:
                    tbc_file = rf_file + '.tbc'
                
                parameters = {
                    'video_standard': getattr(project, 'video_standard', 'pal'),
                    'tape_speed': getattr(project, 'tape_speed', 'SP'),
                    'additional_params': getattr(project, 'additional_params', '')
                }
                
                job_id = job_manager.add_job_nonblocking(
                    job_type="vhs-decode",
                    input_file=rf_file,
                    output_file=tbc_file,
                    parameters=parameters,
                    priority=5,  # Medium priority
                    timeout=0.5,  # 0.5 second timeout
                    project_name=project.name
                )
                
                if job_id:
                    result_queue.put((True, None))
                else:
                    result_queue.put((False, f"Job manager failed to create decode job"))
                
            elif workflow_step == WorkflowStep.EXPORT:
                # Submit TBC export job using job queue manager directly
                tbc_file = None
                
                # Try to get TBC file from project output files
                if hasattr(project, 'output_files') and 'decode' in project.output_files:
                    tbc_file = project.output_files['decode']
                elif hasattr(project, 'tbc_file'):
                    tbc_file = project.tbc_file
                elif hasattr(project, 'capture_files') and 'video' in project.capture_files:
                    # Try to find TBC file based on RF file name
                    rf_file = project.capture_files['video']
                    if rf_file.endswith('.lds'):
                        tbc_file = rf_file.replace('.lds', '.tbc')
                    elif rf_file.endswith('.ldf'):
                        tbc_file = rf_file.replace('.ldf', '.tbc')
                    else:
                        tbc_file = rf_file + '.tbc'
                elif hasattr(project, 'rf_file'):
                    rf_file = project.rf_file
                    if rf_file.endswith('.lds'):
                        tbc_file = rf_file.replace('.lds', '.tbc')
                    elif rf_file.endswith('.ldf'):
                        tbc_file = rf_file.replace('.ldf', '.tbc')
                    else:
                        tbc_file = rf_file + '.tbc'
                    
                if not tbc_file or not os.path.exists(tbc_file):
                    self.message = f"TBC file not found for {project.name} (tried: {tbc_file})"
                    return False
                
                # Generate video output filename
                base_name = os.path.splitext(os.path.basename(tbc_file))[0]
                video_file = os.path.join(os.path.dirname(tbc_file), f"{base_name}_ffv1.mkv")
                
                parameters = {
                    'profile': 'ffv1',
                    'threads': '0',
                    'overwrite': force_overwrite
                }
                
                job_id = job_manager.add_job_nonblocking(
                    job_type="tbc-export",
                    input_file=tbc_file,
                    output_file=video_file,
                    parameters=parameters,
                    priority=5,  # Medium priority
                    timeout=0.5,  # 0.5 second timeout
                    project_name=project.name
                )
                
                if job_id:
                    result_queue.put((True, None))
                else:
                    result_queue.put((False, f"Job manager failed to create export job"))
                
            elif workflow_step == WorkflowStep.ALIGN:
                # Submit audio alignment job using existing alignment functionality
                audio_file = None
                tbc_json_file = None
                
                # Try to find audio file from project capture files
                if hasattr(project, 'capture_files') and 'audio' in project.capture_files:
                    audio_file = project.capture_files['audio']
                elif hasattr(project, 'audio_file'):
                    audio_file = project.audio_file
                else:
                    # Look for audio files in project directory with matching base name
                    if hasattr(project, 'rf_file') and project.rf_file:
                        base_name = os.path.splitext(project.rf_file)[0]
                        for ext in ['.wav', '.flac']:
                            potential_audio = base_name + ext
                            if os.path.exists(potential_audio):
                                audio_file = potential_audio
                                break
                
                # Try to find TBC JSON file
                if hasattr(project, 'output_files') and 'decode' in project.output_files:
                    tbc_file = project.output_files['decode']
                    tbc_json_file = tbc_file + '.json'
                elif hasattr(project, 'tbc_file'):
                    tbc_json_file = project.tbc_file + '.json'
                elif hasattr(project, 'capture_files') and 'video' in project.capture_files:
                    # Try to find TBC JSON based on RF file name
                    rf_file = project.capture_files['video']
                    if rf_file.endswith('.lds'):
                        tbc_json_file = rf_file.replace('.lds', '.tbc.json')
                    elif rf_file.endswith('.ldf'):
                        tbc_json_file = rf_file.replace('.ldf', '.tbc.json')
                    else:
                        tbc_json_file = rf_file + '.tbc.json'
                
                if not audio_file or not os.path.exists(audio_file):
                    self.message = f"Audio file not found for {project.name} (tried: {audio_file})"
                    return False
                
                if not tbc_json_file or not os.path.exists(tbc_json_file):
                    self.message = f"TBC JSON file not found for {project.name} (tried: {tbc_json_file})"
                    return False
                
                # Generate aligned audio output filename
                audio_ext = os.path.splitext(audio_file)[1].lower()
                if audio_ext == '.wav':
                    aligned_audio_file = audio_file.replace('.wav', '_aligned.wav')
                elif audio_ext == '.flac':
                    aligned_audio_file = audio_file.replace('.flac', '_aligned.wav')  # Output as WAV
                else:
                    # Fallback for other extensions
                    aligned_audio_file = os.path.splitext(audio_file)[0] + '_aligned.wav'
                
                parameters = {
                    'audio_file': audio_file,
                    'tbc_json_file': tbc_json_file,
                    'aligned_output': aligned_audio_file,
                    'overwrite': force_overwrite
                }
                
                job_id = job_manager.add_job_nonblocking(
                    job_type="audio-align",
                    input_file=audio_file,
                    output_file=aligned_audio_file,
                    parameters=parameters,
                    priority=5,  # Medium priority
                    timeout=0.5  # 0.5 second timeout
                )
                
                if job_id:
                    result_queue.put((True, None))
                else:
                    result_queue.put((False, f"Job manager failed to create audio alignment job"))
                
            elif workflow_step == WorkflowStep.FINAL:
                # Submit final muxing job using existing muxing functionality
                video_file = None
                audio_file = None
                
                # Try to find video file (_ffv1.mkv) from project output files
                if hasattr(project, 'output_files') and 'export' in project.output_files:
                    video_file = project.output_files['export']
                elif hasattr(project, 'video_file'):
                    video_file = project.video_file
                else:
                    # Look for _ffv1.mkv files based on project base name
                    if hasattr(project, 'capture_files') and 'video' in project.capture_files:
                        rf_file = project.capture_files['video']
                        base_name = os.path.splitext(os.path.basename(rf_file))[0]
                        potential_video = os.path.join(os.path.dirname(rf_file), f"{base_name}_ffv1.mkv")
                        if os.path.exists(potential_video):
                            video_file = potential_video
                    elif hasattr(project, 'rf_file') and project.rf_file:
                        base_name = os.path.splitext(os.path.basename(project.rf_file))[0]
                        potential_video = os.path.join(os.path.dirname(project.rf_file), f"{base_name}_ffv1.mkv")
                        if os.path.exists(potential_video):
                            video_file = potential_video
                
                # Try to find aligned audio file (_aligned.wav)
                if hasattr(project, 'output_files') and 'align' in project.output_files:
                    audio_file = project.output_files['align']
                elif hasattr(project, 'aligned_audio_file'):
                    audio_file = project.aligned_audio_file
                else:
                    # Look for _aligned.wav files based on project base name
                    if hasattr(project, 'capture_files') and 'audio' in project.capture_files:
                        original_audio = project.capture_files['audio']
                        base_name = os.path.splitext(original_audio)[0]
                        potential_aligned = f"{base_name}_aligned.wav"
                        if os.path.exists(potential_aligned):
                            audio_file = potential_aligned
                    elif hasattr(project, 'audio_file') and project.audio_file:
                        base_name = os.path.splitext(project.audio_file)[0]
                        potential_aligned = f"{base_name}_aligned.wav"
                        if os.path.exists(potential_aligned):
                            audio_file = potential_aligned
                    
                    # If no aligned audio found, check for original audio (video-only case)
                    if not audio_file:
                        if hasattr(project, 'capture_files') and 'audio' in project.capture_files:
                            original_audio = project.capture_files['audio']
                            if os.path.exists(original_audio):
                                audio_file = original_audio
                        elif hasattr(project, 'audio_file') and project.audio_file:
                            if os.path.exists(project.audio_file):
                                audio_file = project.audio_file
                
                if not video_file or not os.path.exists(video_file):
                    self.message = f"Video file (_ffv1.mkv) not found for {project.name} (tried: {video_file})"
                    return False
                
                # Audio is optional - can create video-only final if no audio exists
                if not audio_file or not os.path.exists(audio_file):
                    # Check if this is intentionally a video-only project
                    self.message = f"Warning: No audio file found for {project.name} - proceeding with video-only final output"
                    audio_file = None
                
                # Generate final output filename
                video_basename = os.path.splitext(os.path.basename(video_file))[0]
                if video_basename.endswith('_ffv1'):
                    project_base_name = video_basename[:-5]  # Remove _ffv1 suffix
                else:
                    project_base_name = video_basename
                
                final_output_file = os.path.join(os.path.dirname(video_file), f"{project_base_name}_final.mkv")
                
                parameters = {
                    'video_file': video_file,
                    'audio_file': audio_file,  # Can be None for video-only
                    'final_output': final_output_file,
                    'overwrite': force_overwrite
                }
                
                job_id = job_manager.add_job_nonblocking(
                    job_type="final-mux",
                    input_file=video_file,
                    output_file=final_output_file,
                    parameters=parameters,
                    priority=5,  # Medium priority
                    timeout=0.5  # 0.5 second timeout
                )
                
                if job_id:
                    result_queue.put((True, None))
                else:
                    result_queue.put((False, f"Job manager failed to create final muxing job"))
                    
            elif workflow_step == WorkflowStep.COMPRESS:
                # This step will be implemented in future phases
                self.message = f"{workflow_step.name} workflow step not yet implemented"
                return False
                
            else:
                self.message = f"Unknown workflow step: {workflow_step}"
                return False
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.message = f"Error submitting job: {e}\nDetails: {error_details[:200]}..."
            return False
    
    def handle_force_command(self, project_num, step_letter):
        """Handle force commands like 'force 1e' to overwrite existing output"""
        project_idx = project_num - 1
        
        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        
        project = self.current_projects[project_idx]
        
        # Map step letters to workflow steps
        step_map = {
            'd': WorkflowStep.DECODE,
            'c': WorkflowStep.COMPRESS, 
            'e': WorkflowStep.EXPORT,
            'a': WorkflowStep.ALIGN,
            'f': WorkflowStep.FINAL
        }
        
        if step_letter not in step_map:
            self.message = f"Invalid step letter: {step_letter.upper()}"
            return
        
        workflow_step = step_map[step_letter]
        step_name = workflow_step.value.title()
        
        # Force submit the job regardless of current status
        if self.job_manager:
            try:
                success = self._submit_workflow_job(project, workflow_step, force_overwrite=True)
                if success:
                    self.message = f"Warning: Force overwriting {step_name} for Project {project_num} ({project.name})"
                else:
                    self.message = f"Failed to force {step_name} for Project {project_num}"
            except Exception as e:
                self.message = f"Error forcing {step_name}: {str(e)}"
        else:
            self.message = f"Job manager not available - cannot force {step_name}"
    
    def handle_stop_command(self, project_num, step_letter):
        """Handle stop commands like 'stop 1e' to terminate running jobs"""
        project_idx = project_num - 1
        
        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        
        project = self.current_projects[project_idx]
        
        # Map step letters to job types
        step_to_job_type = {
            'd': 'vhs-decode',
            'c': 'compress',  # Future implementation
            'e': 'tbc-export',
            'a': 'audio-align',
            'f': 'final-mux'
        }
        
        if step_letter not in step_to_job_type:
            self.message = f"Invalid step letter: {step_letter.upper()}"
            return
        
        job_type = step_to_job_type[step_letter]
        step_name = step_letter.upper()
        
        # Find running job for this project and step
        if self.job_manager:
            try:
                # Get current jobs with timeout to avoid blocking UI
                jobs = self.job_manager.get_jobs_nonblocking(timeout=0.5)
                
                if jobs is None:
                    self.message = f"Warning: Job manager busy - cannot check jobs for stop command"
                    return
                
                # Look for running job matching project and job type
                running_job = None
                for job in jobs:
                    if (hasattr(job, 'project_name') and hasattr(job, 'job_type') and hasattr(job, 'status') and
                        job.project_name == project.name and 
                        job.job_type == job_type and 
                        str(job.status) == 'JobStatus.RUNNING'):
                        running_job = job
                        break
                
                if running_job:
                    # Attempt to terminate the job
                    try:
                        job_id = getattr(running_job, 'job_id', None)
                        if job_id:
                            # Use the job queue manager's terminate method
                            success = self.job_manager._terminate_job_process(job_id)
                            
                            if success:
                                self.message = f"Stopped {step_name} job for Project {project_num} ({project.name})"
                            else:
                                self.message = f"Warning: Could not stop {step_name} job for Project {project_num} - process may have already ended"
                        else:
                            self.message = f"Error: Could not identify job ID for {step_name} job"
                            
                    except Exception as e:
                        self.message = f"Error stopping {step_name} job: {str(e)}"
                        
                else:
                    # No running job found - check if there are any jobs for this project/step at all
                    matching_jobs = []
                    for job in jobs:
                        if (hasattr(job, 'project_name') and hasattr(job, 'job_type') and
                            job.project_name == project.name and 
                            job.job_type == job_type):
                            matching_jobs.append(job)
                    
                    if matching_jobs:
                        # Found matching jobs but none are running
                        statuses = [getattr(job, 'status', 'Unknown') for job in matching_jobs]
                        self.message = f"No running {step_name} job found for Project {project_num}. Found jobs with status: {', '.join(statuses)}"
                    else:
                        # No jobs found at all
                        self.message = f"No {step_name} job found for Project {project_num} ({project.name})"
                        
            except Exception as e:
                self.message = f"Error checking jobs for stop command: {str(e)}"
        else:
            self.message = f"Job manager not available - cannot stop {step_name} job"
    
    def handle_clean_command(self, project_num, step_letter):
        """Handle clean commands like 'clean 1e' to reset stuck progress displays for failed jobs"""
        project_idx = project_num - 1
        
        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        
        project = self.current_projects[project_idx]
        
        # Map step letters to job types
        step_to_job_type = {
            'd': 'vhs-decode',
            'c': 'compress',  # Future implementation
            'e': 'tbc-export',
            'a': 'audio-align',
            'f': 'final-mux'
        }
        
        if step_letter not in step_to_job_type:
            self.message = f"Invalid step letter: {step_letter.upper()}"
            return
        
        job_type = step_to_job_type[step_letter]
        step_name = step_letter.upper()
        
        # Find failed or stuck jobs for this project and step
        if self.job_manager:
            try:
                # Get current jobs with timeout to avoid blocking UI
                jobs = self.job_manager.get_jobs_nonblocking(timeout=0.5)
                
                if jobs is None:
                    self.message = f"Warning: Job manager busy - cannot check jobs for clean command"
                    return
                
                # Look for failed/stuck jobs matching project and job type
                target_jobs = []
                all_matching_jobs = []
                all_type_matching_jobs = []  # Jobs that match type but not project
                
                for job in jobs:
                    if (hasattr(job, 'project_name') and hasattr(job, 'job_type') and hasattr(job, 'status')):
                        job_project = getattr(job, 'project_name', 'N/A')
                        job_type_attr = getattr(job, 'job_type', 'N/A')
                        
                        # Check for type match (for diagnostic purposes)
                        if job_type_attr == job_type:
                            all_type_matching_jobs.append(job)
                            
                            # Check for exact project + type match
                            if job_project == project.name:
                                all_matching_jobs.append(job)
                                job_status = str(job.status).lower()
                                # Target failed jobs or jobs with progress but not running
                                if ('failed' in job_status or 
                                    (hasattr(job, 'progress') and job.progress > 0 and 'running' not in job_status)):
                                    target_jobs.append(job)
                
                if target_jobs:
                    # Reset progress for found jobs
                    cleaned_count = 0
                    for job in target_jobs:
                        try:
                            job_id = getattr(job, 'job_id', None)
                            if job_id:
                                # Reset progress to 0 and clear any stuck states
                                success = self.job_manager._clean_job_progress(job_id)
                                
                                if success:
                                    cleaned_count += 1
                        except Exception as e:
                            # Continue with other jobs even if one fails
                            continue
                    
                    if cleaned_count > 0:
                        self.message = f"✓ Cleaned {cleaned_count} stuck {step_name} job(s) for Project {project_num} ({project.name})"
                    else:
                        self.message = f"Warning: Could not clean stuck progress for {step_name} jobs - try manual cleanup"
                        
                else:
                    # No target jobs found - provide better diagnostic info
                    if all_matching_jobs:
                        job_statuses = [f"{getattr(job, 'job_id', '?')}: {getattr(job, 'status', '?')} ({getattr(job, 'progress', 0)}%)" for job in all_matching_jobs]
                        self.message = f"No stuck/failed {step_name} jobs for Project {project_num}. Found jobs: {', '.join(job_statuses[:3])}"
                    elif all_type_matching_jobs:
                        # Found jobs of the right type but wrong project - help diagnose the issue
                        project_names = [getattr(job, 'project_name', '?') for job in all_type_matching_jobs[:5]]
                        unique_projects = list(set(project_names))
                        self.message = f"No {step_name} jobs for '{project.name}', but found {len(all_type_matching_jobs)} {step_name} jobs for: {', '.join(unique_projects)}"
                    else:
                        self.message = f"No {step_name} jobs found at all"
                    
            except Exception as e:
                self.message = f"Error cleaning {step_name} jobs: {str(e)}"
        else:
            self.message = f"Job manager not available - cannot clean {step_name} jobs"
    
    def _check_step_output_exists(self, project, workflow_step):
        """Check if the output file for a workflow step actually exists
        
        Args:
            project: Project object
            workflow_step: WorkflowStep enum value
            
        Returns:
            bool: True if output file exists, False otherwise
        """
        try:
            if workflow_step == WorkflowStep.DECODE:
                # Check for TBC file
                if hasattr(project, 'output_files') and 'decode' in project.output_files:
                    return os.path.exists(project.output_files['decode'])
                elif hasattr(project, 'capture_files') and 'video' in project.capture_files:
                    tbc_file = project.capture_files['video'].replace('.lds', '.tbc')
                    return os.path.exists(tbc_file)
                return False
                
            elif workflow_step == WorkflowStep.EXPORT:
                # Check for video export file
                if hasattr(project, 'output_files') and 'export' in project.output_files:
                    return os.path.exists(project.output_files['export'])
                # Try to find expected export file
                elif hasattr(project, 'output_files') and 'decode' in project.output_files:
                    tbc_file = project.output_files['decode']
                    base_name = os.path.splitext(os.path.basename(tbc_file))[0]
                    video_file = os.path.join(os.path.dirname(tbc_file), f"{base_name}_ffv1.mkv")
                    return os.path.exists(video_file)
                return False
                
            elif workflow_step == WorkflowStep.ALIGN:
                # Check for aligned audio file
                if hasattr(project, 'output_files') and 'align' in project.output_files:
                    return os.path.exists(project.output_files['align'])
                return False
                
            elif workflow_step == WorkflowStep.FINAL:
                # Check for final muxed file
                if hasattr(project, 'output_files') and 'final' in project.output_files:
                    return os.path.exists(project.output_files['final'])
                return False
                
            else:
                return False
                
        except Exception:
            return False
    
    def set_temp_directory(self):
        """Set temporary directory to a location with more space"""
        import psutil
        
        # Check available space on different drives
        available_dirs = [
            ('/mnt/nvme2tb', 'nvme2tb'),
            ('/mnt/intel1tb', 'intel1tb'), 
            ('/mnt/hdd1bpool', 'hdd1bpool'),
            ('/home', 'home partition'),
            ('/tmp', 'current /tmp (full!)')
        ]
        
        best_dir = None
        best_free = 0
        
        for temp_dir, desc in available_dirs:
            if os.path.exists(temp_dir):
                try:
                    usage = psutil.disk_usage(temp_dir)
                    free_gb = usage.free / (1024**3)
                    
                    if free_gb > best_free:
                        best_free = free_gb
                        best_dir = temp_dir
                        
                    self.message = f"Checking {desc}: {free_gb:.1f}GB free"
                    time.sleep(0.5)  # Brief pause to see each check
                except:
                    continue
        
        if best_dir and best_dir != '/tmp' and best_free > 50:  # At least 50GB free
            # Create temp directory in the best location
            new_tmp = os.path.join(best_dir, 'ddd_temp')
            try:
                os.makedirs(new_tmp, exist_ok=True)
                
                # Set environment variables to redirect all temp operations
                os.environ['TMPDIR'] = new_tmp
                os.environ['TMP'] = new_tmp
                os.environ['TEMP'] = new_tmp
                
                # Also set for Python's tempfile module
                import tempfile
                tempfile.tempdir = new_tmp
                
                self.message = f"✓ Temp directory set to {new_tmp} ({best_free:.1f}GB available)"
                
                return True
            except Exception as e:
                self.message = f"Failed to create temp directory: {e}"
                return False
        else:
            self.message = f"No suitable temp directory found with enough space (need >50GB, best has {best_free:.1f}GB)"
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary files to free disk space"""
        import subprocess
        import shutil
        
        # Check disk space first
        try:
            import psutil
            disk_usage = psutil.disk_usage('/tmp')
            total_gb = disk_usage.total / (1024**3)
            used_gb = disk_usage.used / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            used_percent = (disk_usage.used / disk_usage.total) * 100
            
            self.message = f"Starting cleanup - /tmp: {used_gb:.1f}GB/{total_gb:.1f}GB ({used_percent:.0f}% full)"
        except:
            self.message = "Starting temp file cleanup..."
        
        files_removed = 0
        space_freed = 0
        
        # Common temp file patterns to clean
        temp_patterns = [
            '/tmp/ffmpeg_*',
            '/tmp/tbc_*', 
            '/tmp/vhs_*',
            '/tmp/temp_*',
            '/tmp/*.tmp',
            '/tmp/python_*',
            '/tmp/tmp*',
        ]
        
        # Clean up temp files
        for pattern in temp_patterns:
            try:
                # Use shell globbing to find files
                result = subprocess.run(
                    f"find /tmp -maxdepth 1 -name '{pattern.split('/')[-1]}' -type f",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    files = result.stdout.strip().split('\n')
                    for file_path in files:
                        if file_path and os.path.exists(file_path):
                            try:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                files_removed += 1
                                space_freed += file_size
                            except (OSError, PermissionError):
                                # Skip files we can't remove
                                continue
                                
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                # Skip this pattern if find command fails
                continue
        
        # Try to clean empty temp directories
        try:
            result = subprocess.run(
                "find /tmp -maxdepth 2 -type d -empty -delete",
                shell=True,
                capture_output=True,
                timeout=5
            )
        except:
            pass
        
        # Calculate results
        space_freed_mb = space_freed / (1024 * 1024)
        
        if files_removed > 0:
            self.message = f"Cleanup complete: Removed {files_removed} files, freed {space_freed_mb:.1f}MB"
        else:
            self.message = "Cleanup complete: No temp files found to remove"
        
        # Check final disk space
        try:
            import psutil
            disk_usage = psutil.disk_usage('/tmp')
            final_used_percent = (disk_usage.used / disk_usage.total) * 100
            final_free_gb = disk_usage.free / (1024**3)
            
            self.message += f" | /tmp now {final_used_percent:.0f}% full ({final_free_gb:.1f}GB free)"
        except:
            pass
    
    def show_help(self):
        """Show help information"""
        clear_screen()
        display_header()
        
        print("\nWORKFLOW CONTROL CENTRE HELP")
        print("=" * 40)
        
        print("\nCoordinate System (Direct Actions):")
        print("  1D - Start Decode for Project 1")
        print("  2C - Start Compress for Project 2")
        print("  3E - Start Export for Project 3")
        print("  1A - Start Align for Project 1")
        print("  2F - Start Final for Project 2")
        
        print("\nProject Selection:")
        print("  1-7 - Select a project from the workflow matrix")
        
        print("\nJob Selection:")
        print("  J1-J9 - Select a job from the active jobs list")
        
        print("\nAction Commands:")
        print("  X - Stop selected job")
        print("  R - Retry failed job or project step")
        print("  D - Show details for selected project or job")
        print("  Auto - Queue all ready workflow steps for all projects")
        print("  force 1e - Force overwrite existing output (e.g., force 1e, force 2d)")
        print("  stop 1e - Stop running job (e.g., stop 1d, stop 2e)")
        print("  clean 1e - Reset stuck progress displays for failed jobs")
        print("  H - Show this help")
        print("  Q - Quit the Workflow Control Centre")
        
        print("\nStep Letters:")
        print("  D = (D)ecode, C = (C)ompress, E = (E)xport")
        print("  A = (A)lign, F = (F)inal")
        
        print("\nTips:")
        print("  • Use coordinate system for direct actions: 1D, 2C, etc.")
        print("  • Select projects (1-7) or jobs (J1-J9) for multi-step operations")
        print("  • 'Auto' will queue all ready steps across all projects")
        print("  • Coordinate commands work on any step status (Ready/Failed/etc.)")
        print("  • Completed jobs with missing files require 'force' to restart")
        print("  • No automatic restarts to prevent continuous fail loops")
        
        print("\nImplementation Status:")
        print("  [DONE] Project discovery and status detection")
        print("  [DONE] Coordinate system with numbered projects")
        print("  [DONE] Rich terminal interface with workflow matrix")
        print("  [IN PROGRESS] Job submission integration")
        print("  [PLANNED] System resource monitoring")
        
        input("\nPress Enter to return to control centre...")

def simple_workflow_interface():
    """Simple workflow interface that doesn't get stuck"""
    while True:
        try:
            clear_screen()
            display_header()
            print("\nVHS WORKFLOW CONTROL CENTRE")
            print("=" * 35)
            print("Unified workflow management for VHS archival processing")
            print("Queue jobs for processing while you continue using the menu system.")
            print()
            
            # Try to show some basic status information
            try:
                sys.path.append('.')
                from job_queue_manager import get_job_queue_manager
                from config import get_capture_directory
                
                job_manager = get_job_queue_manager()
                status = job_manager.get_queue_status()
                capture_dir = get_capture_directory()
                
                print("SYSTEM STATUS:")
                print("=" * 20)
                print(f"Capture Directory: {capture_dir}")
                print(f"Job Processor: {'Running' if status['processor_running'] else 'Stopped'}")
                print(f"Total Jobs: {status['total_jobs']}")
                print(f"  Running: {status['running']}")
                print(f"  Queued: {status['queued']}")
                print(f"  Completed: {status['completed']}")
                print(f"  Failed: {status['failed']}")
                
                # Show some recent files if available
                if os.path.exists(capture_dir):
                    try:
                        files = os.listdir(capture_dir)
                        rf_files = [f for f in files if f.lower().endswith(('.lds', '.ldf'))]
                        tbc_files = [f for f in files if f.lower().endswith('.tbc')]
                        audio_files = [f for f in files if f.lower().endswith(('.wav', '.flac'))]
                        
                        print(f"\nFILE COUNTS:")
                        print(f"  RF Files: {len(rf_files)}")
                        print(f"  TBC Files: {len(tbc_files)}")
                        print(f"  Audio Files: {len(audio_files)}")
                        
                    except Exception:
                        pass
                
            except Exception as e:
                print(f"Status information unavailable: {e}")
            
            print("\nWORKFLOW OPTIONS:")
            print("=" * 25)
            print("1. Add VHS Decode Jobs to Queue")
            print("2. Add TBC Export Jobs to Queue")
            print("3. View Job Queue Status & Progress")
            print("4. Configure Job Queue Settings")
            print("5. Manual Audio Alignment")
            print("6. Mux Video + Audio (Create Final MKV)")
            print("7. Return to VHS-Decode Menu")
            
            choice = input("\nSelect workflow option (1-7): ").strip()
            
            if choice == '1':
                add_vhs_decode_jobs_to_queue()
            elif choice == '2':
                add_tbc_export_jobs_to_queue()
            elif choice == '3':
                show_job_queue_display()
            elif choice == '4':
                configure_job_queue_settings()
            elif choice == '5':
                manual_audio_alignment()
                break  # Return to main menu after alignment
            elif choice == '6':
                mux_video_audio()
                break  # Return to main menu after muxing
            elif choice == '7':
                break  # Return to VHS-Decode menu
            else:
                print("\nInvalid selection. Please enter 1-7.")
                time.sleep(1)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError in workflow interface: {e}")
            input("Press Enter to continue...")

def show_basic_workflow_menu():
    """Basic workflow menu fallback"""
    print("\nBASIC WORKFLOW MENU")
    print("=" * 25)
    print("The full workflow control centre is not available.")
    print("Please use the individual menu options:")
    print()
    print("• Menu 2 → Add VHS Decode Jobs to Queue")
    print("• Menu 2 → Add TBC Export Jobs to Queue")
    print("• Menu 2 → View Job Queue Status & Progress")
    print("• Menu 2 → Manual Audio Alignment")
    print("• Menu 2 → Mux Video + Audio")
    print()
    input("Press Enter to return to menu...")

# Import the necessary functions from main menu
def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header():
    """Display the project header"""
    print("=" * 60)
    print("    DdD Sync Capture - Complete Workflow System")
    print("=" * 60)
    print("  VHS Archival with Domesday Duplicator")
    print("  + Clockgen Lite + Automated Audio/Video Sync")
    print("=" * 60)

# Import the menu functions we need
def add_vhs_decode_jobs_to_queue():
    """Add VHS decode jobs to the background queue"""
    try:
        # Import the function from the main menu
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.add_vhs_decode_jobs_to_queue()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")

def add_tbc_export_jobs_to_queue():
    """Add TBC export jobs to the background queue"""
    try:
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.add_tbc_export_jobs_to_queue()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")

def show_job_queue_display():
    """Show the job queue status display"""
    try:
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.show_job_queue_display()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")

def configure_job_queue_settings():
    """Configure job queue settings"""
    try:
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.configure_job_queue_settings()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")

def manual_audio_alignment():
    """Run manual audio alignment"""
    try:
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.manual_audio_alignment()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")

def mux_video_audio():
    """Mux video and audio"""
    try:
        sys.path.append('.')
        import ddd_main_menu
        ddd_main_menu.mux_video_audio()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")      

def main():
    """Main entry point"""
    run_workflow_control_centre()

if __name__ == '__main__':
    main()
