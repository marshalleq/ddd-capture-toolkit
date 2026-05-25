#!/usr/bin/env python3
"""
VHS Workflow Control Centre - Phase 1.3 Implementation
Unified workflow management with project matrix A-G, selection system, and rich interface
"""

import os
import re
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
    from project_flags import ProjectFlagsManager, DECODE_FLAGS, EXPORT_FLAGS, AUDIO_FLAGS, COMPRESS_FLAGS, get_flag_definitions
    from segment_config import load_segment_config, save_segment_config, toggle_segment_enabled, clear_segment_config, has_segment_config
    COMPONENTS_AVAILABLE = True
    SEGMENT_AVAILABLE = True
except ImportError as e:
    COMPONENTS_AVAILABLE = False
    SEGMENT_AVAILABLE = False
    print(f"Missing required component modules - check project setup: {e}")

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
        """Run enhanced interactive mode with Live display and visible command input.

        Loop design (after the May 2026 input-lag fix):

          * **Input is drained per tick.** Every iteration that has data on
            stdin consumes *all* queued characters, not just one. Previously
            a single read per tick meant fast typing (or any tick that took
            longer than ~50 ms — common when many jobs are running and
            refresh_data is heavy) coalesced multiple keystrokes into a
            visible burst the next render or two later.

          * **Data refresh is decoupled from the render loop.** The expensive
            refresh_data() call (project discovery + job queue queries)
            now runs on its own ~500 ms cadence, while the tick wakeup is
            kept fast (~65 ms) for responsive input handling and a steady
            cursor blink. Render cost stops dragging on input throughput.

          * **Cursor blink is wall-clock driven**, not toggled per-iteration.
            int(time.time() * 2) % 2 gives a 2 Hz cadence (0.25 s on, 0.25 s
            off) regardless of how long any given iteration took or whether
            the user just pressed a key — so the blink no longer betrays
            load or typing rhythm.

          * **Rich Live runs at 15 Hz** so the worst-case visible lag between
            a state change and the redraw is ~65 ms.
        """
        try:
            import termios
            import tty

            # Initialize command input buffer
            self.current_input = ""
            self.input_cursor_blink = True

            # Save original terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            # Cadences:
            #   tick_timeout — how long select() blocks each iteration. Drives
            #     responsiveness and the cursor-blink resolution. Short.
            #   refresh_interval — how often refresh_data() is allowed to run.
            #     Independent of tick_timeout. The expensive scan only fires
            #     this often even if the tick loop spins much faster.
            tick_timeout = 0.066          # ~15 Hz tick
            refresh_interval = 0.5
            last_refresh = 0.0

            def _drain_stdin_to_keys():
                """Read every character currently available on stdin, returning
                them in order. The first read uses tick_timeout (so an idle
                loop doesn't busy-spin); subsequent reads are non-blocking and
                stop as soon as the kernel input buffer is empty. This is the
                fix for the "press one key, two come up together" symptom — a
                fast typist queues several characters during a slow render
                tick and we now consume them all instead of one per tick.
                """
                ready, _, _ = select.select([sys.stdin], [], [], tick_timeout)
                if not ready:
                    return []
                chars = [sys.stdin.read(1)]
                while True:
                    more, _, _ = select.select([sys.stdin], [], [], 0)
                    if not more:
                        break
                    chars.append(sys.stdin.read(1))
                return chars

            def _handle_key(key, live):
                """Process one keystroke. Returns True if the caller should
                bail out of the rest of this tick (e.g. self.running became
                False, or a live.stop()/live.start() cycle was performed and
                a fresh render is already in flight)."""
                if key == '\r' or key == '\n':  # Enter
                    if self.current_input.strip():
                        cmd = self.current_input.strip().lower()
                        self.current_input = ""
                        if cmd == 'q':
                            self.running = False
                            return True
                        elif cmd == 'h':
                            live.stop()
                            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                            self.show_help()
                            tty.setcbreak(sys.stdin.fileno())
                            live.start()
                            return True
                        elif cmd == 'd':
                            live.stop()
                            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                            self.show_details()
                            tty.setcbreak(sys.stdin.fileno())
                            live.start()
                            return True
                        elif (flags_match := re.match(r'^(\d+)x$', cmd)):
                            live.stop()
                            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                            self.show_flags_dialog(int(flags_match.group(1)))
                            tty.setcbreak(sys.stdin.fileno())
                            live.start()
                            return True
                        else:
                            self.handle_command(cmd)
                    else:
                        self.current_input = ""
                elif key == '\x7f' or key == '\x08':  # Backspace
                    if self.current_input:
                        self.current_input = self.current_input[:-1]
                elif key == '\x03':                  # Ctrl+C
                    self.running = False
                    return True
                elif key == '\x1b':                  # Escape
                    self.current_input = ""
                elif key.isprintable() and len(self.current_input) < 50:
                    self.current_input += key
                return False

            with Live(self.create_enhanced_layout(), refresh_per_second=15) as live:
                while self.running:
                    now = time.time()

                    # Refresh project / job state on its own cadence, not
                    # every tick — refresh_data() can take a long time when
                    # many jobs are running, and dragging it through the
                    # input loop is what was throttling keystrokes before.
                    if self.auto_refresh and (now - last_refresh) >= refresh_interval:
                        self.refresh_data()
                        last_refresh = now

                    # Cursor blink: pure function of wall-clock time. 2 Hz
                    # means on for the first half of every second, off for
                    # the second half. Independent of how long this tick
                    # took or how recently a key was pressed.
                    self.input_cursor_blink = int(now * 2) % 2 == 0

                    live.update(self.create_enhanced_layout())

                    # Drain ALL queued input this tick. _drain_stdin_to_keys
                    # blocks up to tick_timeout for the first character so
                    # an idle loop doesn't spin; subsequent reads are
                    # non-blocking and stop when the buffer is empty.
                    keys = _drain_stdin_to_keys()
                    if keys:
                        bail = False
                        for key in keys:
                            if _handle_key(key, live):
                                bail = True
                                break
                        if bail:
                            continue
                        # One immediate re-render so the user sees their
                        # typing reflected in the input bar without
                        # waiting up to ~65 ms for the next tick.
                        live.update(self.create_enhanced_layout())

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
        
        # Main layout with input panel at bottom. command_input is sized so
        # that even when the terminal is narrow and panel content wraps, the
        # Status line still has room to render. The bottom panel also surfaces
        # the most-recent message in its title so even if the body is clipped
        # the status is still visible.
        layout = Layout()
        layout.split_column(
            Layout(name="top_section", ratio=5),
            Layout(name="command_input", size=9)
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
                    # Current activity
                    active = status.get('running', 0) + status.get('queued', 0)
                    status_content.append(f"Active: {active}", style="white")
                    status_content.append(" | ", style="dim")
                    status_content.append(f"Running: {status.get('running', 0)}", style="green")
                    status_content.append(" | ", style="dim")
                    status_content.append(f"Queued: {status.get('queued', 0)}", style="yellow")

                    if status.get('failed', 0) > 0:
                        status_content.append(" | ", style="dim")
                        status_content.append(f"Failed: {status.get('failed', 0)}", style="red")

                    # Lifetime counter (cumulative; reset via 'clean history')
                    status_content.append("\n")
                    status_content.append(
                        f"Lifetime: {status.get('total_jobs', 0)}",
                        style="dim",
                    )
                    status_content.append(" | ", style="dim")
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

        # Show default video format
        try:
            from config import get_preferred_video_format
            default_format = get_preferred_video_format().upper()
        except ImportError:
            default_format = "PAL"
        status_content.append("\n")
        status_content.append(f"Default: {default_format}", style="yellow")
        status_content.append(" (1dp=PAL, 1dn=NTSC)", style="dim")

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

            # GPU + VRAM (NVIDIA only — silently skipped if nvidia-smi
            # isn't available; cached at 0.5 s TTL so the 4 Hz UI refresh
            # doesn't translate into 4 subprocesses per second).
            gpu_pct, vram_pct = self._get_gpu_utilization()
            if gpu_pct is not None:
                gpu_bar = self._create_resource_bar(gpu_pct, width=8)
                resource_table.add_row("GPU:", f"{gpu_bar} {gpu_pct:.0f}%")
            if vram_pct is not None:
                vram_bar = self._create_resource_bar(vram_pct, width=8)
                resource_table.add_row("VRAM:", f"{vram_bar} {vram_pct:.0f}%")

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

    def _get_gpu_utilization(self):
        """Return (gpu_percent, vram_percent) for the primary NVIDIA GPU,
        or (None, None) if nvidia-smi isn't available.

        Cached with a 0.5 s TTL so the WCC's 4 Hz UI refresh doesn't
        spawn four nvidia-smi subprocesses per second. The availability
        probe runs once (shutil.which) and is then cached for the
        session — non-NVIDIA systems pay only that one-time check cost.
        """
        import time
        now = time.time()

        # One-time availability probe
        if not hasattr(self, '_gpu_available'):
            try:
                import shutil
                self._gpu_available = shutil.which('nvidia-smi') is not None
            except Exception:
                self._gpu_available = False
            self._gpu_cache = (None, None)
            self._gpu_cache_at = 0.0

        if not self._gpu_available:
            return (None, None)

        # TTL cache
        if now - self._gpu_cache_at < 0.5:
            return self._gpu_cache

        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=utilization.gpu,memory.used,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=2.0,
            )
            if result.returncode == 0 and result.stdout.strip():
                # First line = primary GPU (sufficient for the panel).
                line = result.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    gpu_pct = float(parts[0])
                    mem_used = float(parts[1])
                    mem_total = float(parts[2])
                    vram_pct = (mem_used / mem_total) * 100.0 if mem_total > 0 else None
                    self._gpu_cache = (gpu_pct, vram_pct)
                    self._gpu_cache_at = now
                    return self._gpu_cache
        except Exception:
            # Subprocess failure (driver hiccup, etc.) — silently return
            # cached last-known value rather than blanking the row.
            pass
        return self._gpu_cache
    
    def create_controls_panel(self):
        """Create controls panel with keyboard shortcuts display.

        Compact one-line-per-command layout. Important commands appear first
        so they remain visible when the terminal is half-width and the panel
        gets vertically squeezed. Press `h` for the full command reference.
        """
        from rich.text import Text

        # Each tuple: (command_text, command_style, description)
        # Order matters — first lines are most likely to be visible when the
        # panel is height-constrained.
        rows = [
            ("h",         "bold cyan",        "Full help"),
            ("1-7",       "bold cyan",        "Select"),
            ("1d 1m 1e",  "bold yellow",      "Dec/cMp/Exp"),
            ("1a 1f",     "bold yellow",      "Algn/Final"),
            ("1mv",       "bold green",       "Validate .ldf"),
            ("hash 1",    "bold green",       "Hash project files"),
            ("check 1",   "bold green",       "Re-check hashes"),
            ("stage 1",   "bold green",       "Stage archive"),
            ("unstage 1", "bold green",       "Undo stage"),
            ("1x",        "bold cyan",        "Flags page"),
            ("1dp 1dn",   "bold yellow",      "PAL / NTSC"),
            ("auto",      "bold cyan",        "Queue ready"),
            ("stop 1d",   "bold red",         "Stop one"),
            ("stop all",  "bold red",         "Stop all"),
            ("cancel q",  "bold red",         "Cancel queued"),
            ("force 1e",  "bold magenta",     "Overwrite"),
            ("clean 1e",  "bold bright_blue", "Reset stuck"),
            ("clean failed", "bold bright_blue", "Wipe failed"),
            ("clean history", "bold bright_blue", "Wipe finished"),
            ("cleanup",   "bold orange1",     "Clear /tmp"),
            ("settemp",   "bold orange1",     "Set tmp dir"),
            ("r",         "bold cyan",        "Retry"),
            ("d",         "bold cyan",        "Details"),
            ("q",         "bold red",         "Quit"),
        ]

        controls = Text()
        for cmd, style, desc in rows:
            controls.append(f"{cmd:<14}", style=style)
            controls.append(f" {desc}\n", style="white")

        return Panel(controls, title="Controls (h=help)", border_style="magenta")
    
    
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
        content.append("Use coordinate system (1d, 2e) or actions (auto, h)\n", style="dim")

        # Show the most recent status message (from command results, validation
        # outcomes, etc.) so background results like 1mv are visible.
        last_message = getattr(self, 'message', '') or ''
        # Pick a style based on outcome keywords
        if last_message.startswith('✗') or 'FAIL' in last_message or 'DO NOT DELETE' in last_message:
            msg_style = "bold red"
            border_style = "red"
        elif last_message.startswith('✓') or 'PASS' in last_message:
            msg_style = "bold green"
            border_style = "green"
        elif 'Warning' in last_message or 'Invalid' in last_message:
            msg_style = "bold yellow"
            border_style = "yellow"
        else:
            msg_style = "white"
            border_style = "yellow"

        if last_message:
            content.append("\n")
            content.append("Status: ", style="bold cyan")
            content.append(last_message, style=msg_style)

        # Always put the most-recent message in the panel TITLE too. Panel
        # titles render on the border and are never clipped by panel-height
        # constraints, so even when the terminal is narrow and the body
        # content wraps off-screen the user can still see what happened.
        if last_message:
            # Title is a single line. Truncate aggressively to fit a typical
            # narrow terminal (~30-50 cols) — full text is still in the body
            # at wider widths.
            short = last_message
            if len(short) > 60:
                short = short[:57] + "..."
            title = f"Command Input — {short}"
        else:
            title = "Command Input"

        return Panel(content, title=title, border_style=border_style)
    
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
            return "None - Use 1D, 2M, etc. for direct actions"
    
    def handle_command(self, cmd):
        """Handle user command input"""
        # Coordinate system commands (1D, 2M, 11D, 23M, etc.)
        # Also supports format modifiers for decode: 1dp (PAL), 1dn (NTSC)
        # Also supports flags: 1x (flags for project 1)
        coord_match = re.match(r'^(\d+)([dmaefx])$', cmd)
        coord_format_match = re.match(r'^(\d+)d([pn])$', cmd)
        # Nmv: project N, compress (m), validate (v) — full .ldf integrity check
        compress_validate_match = re.match(r'^(\d+)mv$', cmd)
        # 'hash N' / 'check N' — checksum operations on a whole project.
        # 'verify N' is accepted as a backwards-compatible alias for 'check N'.
        # 'check N --all' (or 'check N all') forces a full re-hash; the default
        # narrows to files that actually need re-checking (touched / changed /
        # invalid), since hashing every file when the cheap state check already
        # says everything is VALIDATED is wasted I/O.
        hash_match = re.match(r'^hash\s+(\d+)$', cmd)
        check_match = re.match(r'^(?:check|verify)\s+(\d+)(\s+(?:--all|all))?$', cmd)
        # 'stage N' / 'unstage N' — archive staging (move intermediates into
        # <basename>.intermediate/ subfolder, or restore them).
        stage_match = re.match(r'^stage\s+(\d+)$', cmd)
        unstage_match = re.match(r'^unstage\s+(\d+)$', cmd)
        job_match = re.match(r'^j(\d+)$', cmd)
        if coord_match:
            project_num = int(coord_match.group(1))
            step_letter = coord_match.group(2)
            if step_letter == 'x':
                self.show_flags_dialog(project_num)
            else:
                self.handle_coordinate_command(project_num, step_letter)
        elif coord_format_match:
            # Decode with format specifier: 1dp = PAL, 1dn = NTSC
            project_num = int(coord_format_match.group(1))
            format_override = 'pal' if coord_format_match.group(2) == 'p' else 'ntsc'
            self.handle_coordinate_command(project_num, 'd', video_format=format_override)
        elif compress_validate_match:
            project_num = int(compress_validate_match.group(1))
            self.handle_compress_validate(project_num)
        elif hash_match:
            self.handle_hash_project(int(hash_match.group(1)))
        elif check_match:
            project_num = int(check_match.group(1))
            check_all = check_match.group(2) is not None
            self.handle_check_project(project_num, check_all=check_all)
        elif stage_match:
            self.handle_stage_project(int(stage_match.group(1)))
        elif unstage_match:
            self.handle_unstage_project(int(unstage_match.group(1)))

        # Project selection (any positive integer)
        elif cmd.isdigit() and int(cmd) >= 1:
            idx = int(cmd) - 1
            if idx < len(self.current_projects):
                self.selected_project_idx = idx
                self.selected_job_idx = None  # Clear job selection
                project = self.current_projects[idx]
                self.message = f"Selected Project {cmd}: {project.name}"
            else:
                self.message = f"No project at position {cmd}"

        # Job selection (J1, J2, ..., J10, J11, ...)
        elif job_match:
            job_num = int(job_match.group(1))
            if 1 <= job_num <= len(self.current_jobs):
                idx = job_num - 1
                self.selected_job_idx = idx
                self.selected_project_idx = None  # Clear project selection
                job = self.current_jobs[idx]
                self.message = f"Selected Job J{job_num}: {job.get('project_name', 'Unknown')}"
            else:
                self.message = f"No job at position J{job_num}"

        # Force command (force 1e, force 11e, etc.)
        elif cmd.startswith('force '):
            force_cmd = cmd[6:].strip()
            force_match = re.match(r'^(\d+)([dmaef])$', force_cmd)
            if force_match:
                self.handle_force_command(int(force_match.group(1)), force_match.group(2))
            else:
                self.message = f"Invalid force command format. Use: force 1e, force 2d, etc."

        # Clean command to reset stuck progress displays or bulk-clear history
        elif cmd.startswith('clean '):
            clean_cmd = cmd[6:].strip()
            clean_match = re.match(r'^(\d+)([dmaef])$', clean_cmd)
            if clean_match:
                self.handle_clean_command(int(clean_match.group(1)), clean_match.group(2))
            elif clean_cmd == 'failed':
                self.handle_clean_history(['failed'])
            elif clean_cmd == 'cancelled':
                self.handle_clean_history(['cancelled'])
            elif clean_cmd == 'history':
                self.handle_clean_history(['failed', 'cancelled', 'completed'])
            else:
                self.message = (
                    "Invalid clean command. Use: 'clean 1e' (per-step), "
                    "'clean failed', 'clean cancelled', or 'clean history'."
                )

        # Bulk stop / cancel commands. Must match before the generic 'stop '
        # prefix so 'stop all' doesn't fall into the regex path.
        elif cmd == 'stop all':
            self.handle_stop_all()
        elif cmd == 'cancel queue':
            self.handle_cancel_queue()

        # Stop command (stop 1e, stop 11e, etc.)
        elif cmd.startswith('stop '):
            stop_cmd = cmd[5:].strip()
            stop_match = re.match(r'^(\d+)([dmaef])$', stop_cmd)
            if stop_match:
                self.handle_stop_command(int(stop_match.group(1)), stop_match.group(2))
            else:
                self.message = f"Invalid stop command format. Use: stop 1e, stop 2d, stop all"
        
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
    
    def handle_coordinate_command(self, project_num, step_letter, video_format=None):
        """Handle coordinate-based commands like 1D, 2M, 1DP (PAL), 1DN (NTSC), etc."""
        project_idx = project_num - 1
        
        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        
        project = self.current_projects[project_idx]
        
        # Map step letters to workflow steps
        step_map = {
            'd': WorkflowStep.DECODE,
            'm': WorkflowStep.COMPRESS,
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
                        success = self._submit_workflow_job(project, workflow_step, video_format=video_format)
                        if success:
                            format_info = f" ({video_format.upper()})" if video_format and workflow_step == WorkflowStep.DECODE else ""
                            self.message = f"Started {step_name}{format_info} for Project {project_num} ({project.name})"
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
                        success = self._submit_workflow_job(project, workflow_step, video_format=video_format)
                        if success:
                            format_info = f" ({video_format.upper()})" if video_format and workflow_step == WorkflowStep.DECODE else ""
                            self.message = f"Retrying {step_name}{format_info} for Project {project_num} ({project.name})"
                        else:
                            self.message = f"Failed to retry {step_name} for Project {project_num}"
                    except Exception as e:
                        self.message = f"Error retrying {step_name}: {str(e)}"
                else:
                    self.message = f"Job manager not available - cannot retry {step_name}"
            elif step_status in (StepStatus.COMPLETE, StepStatus.VALIDATED,
                                  StepStatus.TOUCHED, StepStatus.CHANGED,
                                  StepStatus.INVALID, StepStatus.HASHING):
                # Step has finished (one way or another). Don't auto-restart;
                # require 'force' to overwrite.
                output_exists = self._check_step_output_exists(project, workflow_step)
                state_label = step_status.value
                if not output_exists:
                    self.message = (f"Warning: {step_name} marked {state_label} but output file missing "
                                    f"for Project {project_num}. Use 'force {project_num}{step_letter}' to restart")
                else:
                    self.message = (f"Warning: {step_name} {state_label} for Project {project_num}. "
                                    f"Use 'force {project_num}{step_letter}' to overwrite")
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

    def show_flags_dialog(self, project_num):
        """Show flags dialog with Decode and Export pages using Rich formatting"""
        import termios
        import tty
        import fcntl
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich.console import Console
        from rich.box import ROUNDED, HEAVY

        console = Console()
        project_idx = project_num - 1

        # Check if project exists
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return

        project = self.current_projects[project_idx]

        # Initialize flags manager
        flags_manager = ProjectFlagsManager()

        # Page definitions
        pages = [
            {'type': 'decode', 'title': 'DECODE FLAGS', 'subtitle': 'vhs-decode options'},
            {'type': 'export', 'title': 'EXPORT FLAGS', 'subtitle': 'tbc-video-export options'},
            {'type': 'audio', 'title': 'AUDIO FLAGS', 'subtitle': 'final mux audio options'},
            {'type': 'compress', 'title': 'COMPRESS FLAGS', 'subtitle': 'lds-compress validation options'},
            {'type': 'segment', 'title': 'SEGMENT CONFIG', 'subtitle': 'test range for decode/export'},
        ]
        current_page = 0

        # Load flags for all types
        decode_flags = flags_manager.get_project_flags(project.name, 'decode')
        export_flags = flags_manager.get_project_flags(project.name, 'export')
        audio_flags = flags_manager.get_project_flags(project.name, 'audio')
        compress_flags = flags_manager.get_project_flags(project.name, 'compress')
        current_flags = {
            'decode': decode_flags,
            'export': export_flags,
            'audio': audio_flags,
            'compress': compress_flags,
        }

        # Segment presets
        segment_presets = [
            {'id': 'toggle', 'label': 'Enable/Disable Segment', 'start': None, 'duration': None},
            {'id': '30s', 'label': 'First 30 seconds', 'start': '00:00', 'duration': '00:30'},
            {'id': '1m', 'label': 'First 1 minute', 'start': '00:00', 'duration': '01:00'},
            {'id': '2m', 'label': 'First 2 minutes', 'start': '00:00', 'duration': '02:00'},
            {'id': '5m', 'label': 'First 5 minutes', 'start': '00:00', 'duration': '05:00'},
            {'id': 'custom', 'label': 'Custom time range...', 'start': None, 'duration': None},
            {'id': 'clear', 'label': 'Clear segment config', 'start': None, 'duration': None},
        ]
        segment_selected_idx = 0

        # Selection state per page
        selected_idx = 0

        def get_current_flag_defs():
            if pages[current_page]['type'] == 'segment':
                return {}  # Segment page doesn't use flag definitions
            return get_flag_definitions(pages[current_page]['type'])

        def get_current_flags():
            if pages[current_page]['type'] == 'segment':
                return {}  # Segment page doesn't use flag definitions
            return current_flags[pages[current_page]['type']]

        def render_segment_screen():
            """Render the segment configuration screen"""
            nonlocal segment_selected_idx
            console.clear()

            page = pages[current_page]

            # Title panel with page indicator
            title = Text()
            title.append(page['title'], style="bold cyan")
            title.append(f"  -  {project.name}", style="bold white")
            title.append("    ", style="white")
            title.append(f"[Page {current_page + 1}/{len(pages)}: {page['subtitle']}]", style="dim")
            console.print(Panel(title, box=HEAVY, style="cyan"))

            # Instructions panel
            instructions = Text()
            instructions.append("↑↓", style="bold yellow")
            instructions.append(" Navigate", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("←→", style="bold magenta")
            instructions.append(" Page", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("Space/Enter", style="bold yellow")
            instructions.append(" Apply", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("Esc", style="bold red")
            instructions.append(" Back", style="white")
            console.print(Panel(instructions, box=ROUNDED, style="dim"))
            console.print()

            # Load current segment config for this project
            current_segment = load_segment_config(project.name) if SEGMENT_AVAILABLE else None

            # Current segment status panel
            if current_segment and current_segment.get('enabled'):
                status_text = Text()
                status_text.append("SEGMENT ACTIVE", style="bold green")
                status_text.append(f"\nTime: {current_segment.get('start_time', '?')} → {current_segment.get('end_time', '?')}", style="white")
                status_text.append(f"\nDuration: {current_segment.get('duration', '?')}", style="white")
                status_text.append(f"\nPAL frames: {current_segment.get('start_frame_pal', 0)} - {current_segment.get('start_frame_pal', 0) + current_segment.get('frame_count_pal', 0)}", style="dim")
                console.print(Panel(status_text, title="Current Segment", box=HEAVY, style="green"))
            elif current_segment:
                status_text = Text()
                status_text.append("SEGMENT DISABLED", style="bold yellow")
                status_text.append(f"\nConfigured: {current_segment.get('start_time', '?')} → {current_segment.get('end_time', '?')}", style="dim")
                console.print(Panel(status_text, title="Current Segment", box=HEAVY, style="yellow"))
            else:
                status_text = Text("No segment configured", style="dim")
                console.print(Panel(status_text, title="Current Segment", box=HEAVY, style="dim"))
            console.print()

            # Segment presets table
            table = Table(
                title="Segment Options",
                box=HEAVY,
                show_header=True,
                header_style="bold cyan",
                title_style="bold white"
            )

            table.add_column(" ", width=2, justify="center")
            table.add_column("Status", width=8, justify="center")
            table.add_column("Option", width=30)
            table.add_column("Start", width=10, justify="center")
            table.add_column("Duration", width=10, justify="center")

            # Determine which preset matches current config (if any)
            current_start = current_segment.get('start_time', '') if current_segment else ''
            current_duration = current_segment.get('duration', '') if current_segment else ''
            segment_enabled = current_segment.get('enabled', False) if current_segment else False

            for idx, preset in enumerate(segment_presets):
                is_selected = (idx == segment_selected_idx)

                indicator = Text("▶", style="bold yellow") if is_selected else Text(" ")

                # Check if this preset is currently active
                is_active = False
                if preset['id'] == 'toggle':
                    status = Text(" ")
                elif preset['id'] == 'clear':
                    status = Text(" ")
                elif preset['start'] and preset['duration']:
                    # Compare with current config
                    if (current_start == preset['start'] and
                        current_duration == preset['duration'] and
                        segment_enabled):
                        is_active = True
                        status = Text("[X]", style="bold green")
                    else:
                        status = Text("[ ]", style="dim")
                else:
                    status = Text(" ")

                if is_selected:
                    label = Text(preset['label'], style="bold white on blue")
                elif is_active:
                    label = Text(preset['label'], style="bold green")
                else:
                    label = Text(preset['label'], style="white")

                start = preset['start'] if preset['start'] else "-"
                duration = preset['duration'] if preset['duration'] else "-"

                table.add_row(indicator, status, label, start, duration)

            console.print(table)
            console.print()

            # Info panel
            info = Text()
            info.append("Segment mode applies to DECODE jobs only.\n", style="white")
            info.append("Export will process the full TBC (which is already the segment).\n", style="white")
            info.append("PAL/NTSC frame rates are auto-detected from your files.", style="dim")
            console.print(Panel(info, title="Info", box=ROUNDED, style="dim"))

        def render_flags_screen():
            """Render the flags dialog screen with Rich components"""
            nonlocal selected_idx

            # Handle segment page separately
            if pages[current_page]['type'] == 'segment':
                render_segment_screen()
                return

            console.clear()

            page = pages[current_page]
            flag_defs = get_current_flag_defs()
            page_flags = get_current_flags()
            flag_keys = list(flag_defs.keys())

            # Ensure selected_idx is valid for current page
            if selected_idx >= len(flag_keys):
                selected_idx = 0

            # Title panel with page indicator
            title = Text()
            title.append(page['title'], style="bold cyan")
            title.append(f"  -  {project.name}", style="bold white")
            title.append("    ", style="white")
            title.append(f"[Page {current_page + 1}/{len(pages)}: {page['subtitle']}]", style="dim")
            console.print(Panel(title, box=HEAVY, style="cyan"))

            # Instructions panel
            instructions = Text()
            instructions.append("↑↓", style="bold yellow")
            instructions.append(" Navigate", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("←→", style="bold magenta")
            instructions.append(" Page", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("Space", style="bold yellow")
            instructions.append(" Toggle", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("Enter", style="bold green")
            instructions.append(" Save All", style="white")
            instructions.append("  |  ", style="dim")
            instructions.append("Esc", style="bold red")
            instructions.append(" Cancel", style="white")
            console.print(Panel(instructions, box=ROUNDED, style="dim"))
            console.print()

            # Create flags table
            table = Table(
                title=f"{page['title']} ({page['subtitle']})",
                box=HEAVY,
                show_header=True,
                header_style="bold cyan",
                title_style="bold white"
            )

            table.add_column(" ", width=2, justify="center")  # Selection indicator
            table.add_column("Status", width=8, justify="center")
            table.add_column("Flag", width=25)
            table.add_column("CLI Option", width=20, style="dim")
            table.add_column("Description", width=45)

            for idx, flag_key in enumerate(flag_keys):
                flag_def = flag_defs[flag_key]
                is_enabled = page_flags.get(flag_key, False)
                is_default_on = flag_def.get('default', False)
                is_selected = (idx == selected_idx)

                # Selection indicator
                if is_selected:
                    indicator = Text("▶", style="bold yellow")
                else:
                    indicator = Text(" ")

                # Checkbox with color - show differently for default-on flags
                if is_enabled:
                    if is_default_on:
                        checkbox = Text("[X]", style="cyan")  # Default-on, currently on
                    else:
                        checkbox = Text("[X]", style="bold green")  # Explicitly enabled
                else:
                    if is_default_on:
                        checkbox = Text("[ ]", style="bold yellow")  # Default-on but disabled!
                    else:
                        checkbox = Text("[ ]", style="dim")  # Default-off, currently off

                # Flag name - highlight if selected
                if is_selected:
                    flag_name = Text(flag_def['label'], style="bold white on blue")
                else:
                    flag_name = Text(flag_def['label'], style="white")

                # CLI option
                cli_opt = flag_def['cli_flag']

                # Description - add default indicator
                desc = Text()
                desc.append(flag_def['description'])
                if is_default_on:
                    desc.append(" (default: on)", style="cyan")

                table.add_row(indicator, checkbox, flag_name, cli_opt, desc)

            console.print(table)
            console.print()

            # Summary for current page - separate defaults from custom
            default_on_labels = []
            custom_on_labels = []
            custom_off_labels = []  # Default-on flags that were disabled
            for k in flag_keys:
                is_enabled = page_flags.get(k, False)
                is_default_on = flag_defs[k].get('default', False)
                if is_enabled:
                    if is_default_on:
                        default_on_labels.append(flag_defs[k]['label'])
                    else:
                        custom_on_labels.append(flag_defs[k]['label'])
                elif is_default_on:
                    # Default was disabled
                    custom_off_labels.append(flag_defs[k]['label'])

            summary = Text()
            if default_on_labels:
                summary.append("Defaults: ", style="cyan")
                summary.append(", ".join(default_on_labels), style="cyan")
            if custom_on_labels:
                if default_on_labels:
                    summary.append("  |  ", style="dim")
                summary.append("Custom: ", style="bold green")
                summary.append(", ".join(custom_on_labels), style="bold green")
            if custom_off_labels:
                if default_on_labels or custom_on_labels:
                    summary.append("  |  ", style="dim")
                summary.append("Disabled: ", style="bold yellow")
                summary.append(", ".join(custom_off_labels), style="yellow")
            if not default_on_labels and not custom_on_labels and not custom_off_labels:
                summary.append("No flags enabled on this page", style="dim")

            console.print(Panel(summary, title=f"{page['type'].title()} Summary", box=ROUNDED))

            # Overall summary - show only non-default (custom) settings
            custom_decode = []
            disabled_decode = []
            for k in current_flags['decode']:
                is_enabled = current_flags['decode'].get(k, False)
                is_default_on = DECODE_FLAGS.get(k, {}).get('default', False)
                if is_enabled and not is_default_on:
                    custom_decode.append(DECODE_FLAGS[k]['label'])
                elif not is_enabled and is_default_on:
                    disabled_decode.append(DECODE_FLAGS[k]['label'])

            custom_export = []
            disabled_export = []
            for k in current_flags['export']:
                is_enabled = current_flags['export'].get(k, False)
                is_default_on = EXPORT_FLAGS.get(k, {}).get('default', False)
                if is_enabled and not is_default_on:
                    custom_export.append(EXPORT_FLAGS[k]['label'])
                elif not is_enabled and is_default_on:
                    disabled_export.append(EXPORT_FLAGS[k]['label'])

            custom_audio = []
            disabled_audio = []
            for k in current_flags['audio']:
                is_enabled = current_flags['audio'].get(k, False)
                is_default_on = AUDIO_FLAGS.get(k, {}).get('default', False)
                if is_enabled and not is_default_on:
                    custom_audio.append(AUDIO_FLAGS[k]['label'])
                elif not is_enabled and is_default_on:
                    disabled_audio.append(AUDIO_FLAGS[k]['label'])

            has_changes = (custom_decode or custom_export or custom_audio or
                          disabled_decode or disabled_export or disabled_audio)
            if has_changes:
                overall = Text()
                parts = []
                if custom_decode:
                    parts.append(("Decode+: ", ", ".join(custom_decode), "green"))
                if disabled_decode:
                    parts.append(("Decode-: ", ", ".join(disabled_decode), "yellow"))
                if custom_export:
                    parts.append(("Export+: ", ", ".join(custom_export), "green"))
                if disabled_export:
                    parts.append(("Export-: ", ", ".join(disabled_export), "yellow"))
                if custom_audio:
                    parts.append(("Audio+: ", ", ".join(custom_audio), "green"))
                if disabled_audio:
                    parts.append(("Audio-: ", ", ".join(disabled_audio), "yellow"))

                for i, (label, values, color) in enumerate(parts):
                    if i > 0:
                        overall.append("  |  ", style="dim")
                    overall.append(label, style=f"bold {color}")
                    overall.append(values, style=color)
                console.print(Panel(overall, title="Non-Default Settings", box=ROUNDED, style="dim"))

        # Setup terminal for single keypress reading
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        def read_key():
            """Read a single keypress, handling escape sequences for arrow keys"""
            key = sys.stdin.read(1)

            if key == '\x1b':  # Escape character - could be arrow key or actual Esc
                # Set non-blocking temporarily to check for more chars
                old_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, old_fl | os.O_NONBLOCK)

                try:
                    next_char = sys.stdin.read(1)
                    if next_char == '[':
                        arrow = sys.stdin.read(1)
                        if arrow == 'A':
                            return 'UP'
                        elif arrow == 'B':
                            return 'DOWN'
                        elif arrow == 'C':
                            return 'RIGHT'
                        elif arrow == 'D':
                            return 'LEFT'
                    # If we got here, it wasn't an arrow key sequence
                    return 'ESC'
                except (IOError, TypeError):
                    # No more chars available - it was just Esc
                    return 'ESC'
                finally:
                    fcntl.fcntl(fd, fcntl.F_SETFL, old_fl)

            return key

        def apply_segment_preset(preset, fd, old_settings):
            """Apply a segment preset for this project"""
            if preset['id'] == 'toggle':
                # Toggle current segment for this project
                current = load_segment_config(project.name)
                if current:
                    new_state = toggle_segment_enabled(project.name)
                    return f"Segment {'enabled' if new_state else 'disabled'} for {project.name}"
                else:
                    return f"No segment configured for {project.name}"
            elif preset['id'] == 'clear':
                clear_segment_config(project.name)
                return f"Segment configuration cleared for {project.name}"
            elif preset['id'] == 'custom':
                # Custom time input - need to restore terminal temporarily
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                console.clear()
                console.print(Panel(f"CUSTOM SEGMENT - {project.name}", style="bold cyan"))
                console.print()
                console.print("Enter times in MM:SS or HH:MM:SS format")
                console.print()
                try:
                    start_time = input("Start time [00:00]: ").strip()
                    if not start_time:
                        start_time = "00:00"

                    duration = input("Duration (e.g., 01:00 for 1 minute): ").strip()
                    if not duration:
                        tty.setcbreak(fd)
                        return "Cancelled - no duration entered"

                    description = input("Description (optional): ").strip()
                    if not description:
                        description = f"Custom: {start_time} + {duration}"

                    # Restore cbreak mode
                    tty.setcbreak(fd)

                    if save_segment_config(project.name, start_time, duration, description):
                        return f"Custom segment set for {project.name}: {start_time} + {duration}"
                    else:
                        return "Failed to save segment - check time format"
                except (KeyboardInterrupt, EOFError):
                    tty.setcbreak(fd)
                    return "Cancelled"
            else:
                # Apply a preset with start/duration for this project
                if save_segment_config(project.name, preset['start'], preset['duration'], preset['label']):
                    return f"Segment set for {project.name}: {preset['label']}"
                else:
                    return "Failed to save segment"

        try:
            tty.setcbreak(fd)

            while True:
                render_flags_screen()

                page_type = pages[current_page]['type']

                # Read single keypress
                key = read_key()

                # Handle segment page differently
                if page_type == 'segment':
                    if key == 'UP':
                        segment_selected_idx = (segment_selected_idx - 1) % len(segment_presets)

                    elif key == 'DOWN':
                        segment_selected_idx = (segment_selected_idx + 1) % len(segment_presets)

                    elif key == 'LEFT':
                        current_page = (current_page - 1) % len(pages)
                        selected_idx = 0

                    elif key == 'RIGHT':
                        current_page = (current_page + 1) % len(pages)
                        selected_idx = 0

                    elif key in (' ', '\r', '\n'):  # Space or Enter - apply preset
                        preset = segment_presets[segment_selected_idx]
                        result = apply_segment_preset(preset, fd, old_settings)
                        self.message = result
                        # Don't return - stay on page to see result

                    elif key == 'ESC' or key.lower() == 'q':
                        self.message = "Segment config closed"
                        return

                    elif key == '\x03':  # Ctrl+C
                        return

                else:
                    # Normal flag pages
                    flag_defs = get_current_flag_defs()
                    flag_keys = list(flag_defs.keys())

                    if key == 'UP':
                        selected_idx = (selected_idx - 1) % len(flag_keys)

                    elif key == 'DOWN':
                        selected_idx = (selected_idx + 1) % len(flag_keys)

                    elif key == 'LEFT':
                        current_page = (current_page - 1) % len(pages)
                        selected_idx = 0  # Reset selection on page change

                    elif key == 'RIGHT':
                        current_page = (current_page + 1) % len(pages)
                        selected_idx = 0  # Reset selection on page change

                    elif key == '\t':  # Tab - move down
                        selected_idx = (selected_idx + 1) % len(flag_keys)

                    elif key == ' ':  # Space - toggle
                        flag_key = flag_keys[selected_idx]
                        current_flags[page_type][flag_key] = not current_flags[page_type].get(flag_key, False)

                    elif key in ('\r', '\n'):  # Enter - save all
                        # Save all flag types
                        flags_manager.set_project_flags(project.name, current_flags['decode'], 'decode')
                        flags_manager.set_project_flags(project.name, current_flags['export'], 'export')
                        flags_manager.set_project_flags(project.name, current_flags['audio'], 'audio')

                        # Build summary message
                        decode_labels = flags_manager.get_enabled_flag_labels(project.name, 'decode')
                        export_labels = flags_manager.get_enabled_flag_labels(project.name, 'export')
                        audio_labels = flags_manager.get_enabled_flag_labels(project.name, 'audio')

                        parts = []
                        if decode_labels:
                            parts.append(f"Decode: {', '.join(decode_labels)}")
                        if export_labels:
                            parts.append(f"Export: {', '.join(export_labels)}")
                        if audio_labels:
                            parts.append(f"Audio: {', '.join(audio_labels)}")

                        if parts:
                            self.message = f"Flags saved for {project.name} - {'; '.join(parts)}"
                        else:
                            self.message = f"All flags cleared for {project.name}"
                        return

                    elif key == 'ESC' or key.lower() == 'q':  # Esc or Q - cancel
                        self.message = "Flags edit cancelled"
                        return

                    elif key == '\x03':  # Ctrl+C
                        self.message = "Flags edit cancelled"
                        return

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

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
    
    def _submit_workflow_job(self, project, workflow_step, force_overwrite=False, video_format=None):
        """Submit a job for a specific workflow step

        Args:
            project: Project object
            workflow_step: WorkflowStep enum value
            force_overwrite: bool: Whether to force overwrite existing output files
            video_format: str: Optional video format override ('pal' or 'ntsc') for decode jobs

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
                self._submit_workflow_job_background(project, workflow_step, force_overwrite, result_queue, video_format)
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
    
    @staticmethod
    def _remove_decode_outputs(tbc_file: str) -> None:
        """Delete the files vhs-decode produces alongside a .tbc.

        Called by the force-decode path so the matrix doesn't keep showing
        a partial leftover as COMPLETE while the new vhs-decode is still
        starting up. Safe to call when some/all files are missing — silently
        skips them.
        """
        if not tbc_file.endswith('.tbc'):
            return
        base = tbc_file[:-len('.tbc')]
        candidates = [
            tbc_file,                  # Project.tbc
            base + '_chroma.tbc',      # Project_chroma.tbc
            base + '.tbc.json',        # Project.tbc.json
            base + '.log',             # Project.log (vhs-decode's own log)
        ]
        for p in candidates:
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                # Don't abort the force command on a delete failure;
                # vhs-decode will simply overwrite when it opens its outputs.
                pass

    def _submit_workflow_job_background(self, project, workflow_step, force_overwrite, result_queue, video_format=None):
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

                # On explicit overwrite, remove any leftover decode outputs from
                # prior runs BEFORE submitting the new job. Otherwise a partial
                # .tbc left behind by a crashed/cancelled decode keeps fooling
                # the matrix into showing COMPLETE during the brief window
                # before vhs-decode opens (and truncates) the new output.
                if force_overwrite:
                    self._remove_decode_outputs(tbc_file)

                # Determine video format: use override if provided, else config default
                if video_format:
                    selected_format = video_format
                else:
                    try:
                        from config import get_preferred_video_format
                        selected_format = getattr(project, 'video_standard', get_preferred_video_format())
                    except ImportError:
                        selected_format = getattr(project, 'video_standard', 'pal')

                parameters = {
                    'video_standard': selected_format,
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
                
                # Generate aligned audio output filename.
                # Output is always FLAC: lossless, compressed, no 4 GB limit (WAV
                # caps at ~4 GB which gets hit on tapes longer than ~2.5 h at
                # 24-bit/78125 Hz). final-mux accepts FLAC natively and Resolve
                # at 96 kHz reads it correctly.
                aligned_audio_file = os.path.splitext(audio_file)[0] + '_aligned.flac'
                
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
                
                # Try to find aligned audio file (_aligned.flac preferred,
                # _aligned.wav supported for legacy outputs)
                if hasattr(project, 'output_files') and 'align' in project.output_files:
                    audio_file = project.output_files['align']
                elif hasattr(project, 'aligned_audio_file'):
                    audio_file = project.aligned_audio_file
                else:
                    base_name = None
                    if hasattr(project, 'capture_files') and 'audio' in project.capture_files:
                        base_name = os.path.splitext(project.capture_files['audio'])[0]
                    elif hasattr(project, 'audio_file') and project.audio_file:
                        base_name = os.path.splitext(project.audio_file)[0]

                    if base_name:
                        for ext in ('.flac', '.wav'):
                            potential_aligned = f"{base_name}_aligned{ext}"
                            if os.path.exists(potential_aligned):
                                audio_file = potential_aligned
                                break
                    
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
                # Submit LDS compression job to convert .lds to .ldf
                lds_file = None

                # Try to find LDS file from project capture files
                if hasattr(project, 'capture_files') and 'video' in project.capture_files:
                    lds_file = project.capture_files['video']
                elif hasattr(project, 'rf_file'):
                    lds_file = project.rf_file

                if not lds_file or not os.path.exists(lds_file):
                    self.message = f"LDS file not found for {project.name} (tried: {lds_file})"
                    result_queue.put((False, self.message))
                    return

                # Only compress .lds files (not already compressed .ldf files)
                if not lds_file.endswith('.lds'):
                    self.message = f"File is not an .lds file (already compressed?): {lds_file}"
                    result_queue.put((False, self.message))
                    return

                # Generate output filename (.lds -> .ldf)
                ldf_file = lds_file.replace('.lds', '.ldf')

                # Read global GPU compress setting
                from config import get_compress_use_gpu
                gpu_enabled = get_compress_use_gpu()

                # GPU mode caps level at 11; CPU caps at 12. Use 11 either way.
                parameters = {
                    'compression_level': 11,
                    'show_progress': True,
                    'overwrite': force_overwrite,
                    'gpu': gpu_enabled,
                }

                job_id = job_manager.add_job_nonblocking(
                    job_type="lds-compress",
                    input_file=lds_file,
                    output_file=ldf_file,
                    parameters=parameters,
                    priority=5,  # Medium priority
                    timeout=0.5,  # 0.5 second timeout
                    project_name=project.name
                )

                if job_id:
                    result_queue.put((True, None))
                else:
                    result_queue.put((False, f"Job manager failed to create compression job"))
                
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
            'm': WorkflowStep.COMPRESS,
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
        """Handle stop commands like 'stop 1e' to cancel both RUNNING and QUEUED
        jobs for the given project+step. Running jobs are terminated; queued jobs
        are removed from the queue. All matching jobs are cancelled (not just one)
        so duplicates from auto-queue / restart races get cleaned up too."""
        project_idx = project_num - 1

        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return

        project = self.current_projects[project_idx]

        step_to_job_type = {
            'd': 'vhs-decode',
            'm': 'lds-compress',
            'e': 'tbc-export',
            'a': 'audio-align',
            'f': 'final-mux'
        }

        if step_letter not in step_to_job_type:
            self.message = f"Invalid step letter: {step_letter.upper()}"
            return

        job_type = step_to_job_type[step_letter]
        step_name = step_letter.upper()

        if not self.job_manager:
            self.message = f"Job manager not available - cannot stop {step_name} job"
            return

        try:
            jobs = self.job_manager.get_jobs_nonblocking(timeout=0.5)
            if jobs is None:
                self.message = f"Warning: Job manager busy - cannot check jobs for stop command"
                return

            ACTIVE = ('JobStatus.RUNNING', 'JobStatus.QUEUED')
            matching = [
                job for job in jobs
                if hasattr(job, 'project_name') and hasattr(job, 'job_type') and hasattr(job, 'status')
                and job.project_name == project.name
                and job.job_type == job_type
                and str(job.status) in ACTIVE
            ]

            if not matching:
                all_matching = [
                    j for j in jobs
                    if hasattr(j, 'project_name') and hasattr(j, 'job_type')
                    and j.project_name == project.name and j.job_type == job_type
                ]
                if all_matching:
                    statuses = [str(getattr(j, 'status', 'Unknown')) for j in all_matching]
                    self.message = f"No active {step_name} job for Project {project_num}. Found: {', '.join(statuses)}"
                else:
                    self.message = f"No {step_name} job found for Project {project_num} ({project.name})"
                return

            stopped = 0
            cancelled = 0
            for job in matching:
                was_running = str(job.status) == 'JobStatus.RUNNING'
                if self.job_manager.cancel_job(job.job_id):
                    if was_running:
                        stopped += 1
                    else:
                        cancelled += 1

            parts = []
            if stopped:
                parts.append(f"stopped {stopped} running")
            if cancelled:
                parts.append(f"cancelled {cancelled} queued")
            summary = ", ".join(parts) if parts else "no jobs affected"
            self.message = f"{step_name} for Project {project_num} ({project.name}): {summary}"
        except Exception as e:
            self.message = f"Error stopping {step_name} job: {str(e)}"

    def handle_stop_all(self):
        """Terminate every RUNNING job and cancel every QUEUED job. Used when
        the queue has run away (auto-queue race, restart leftovers) and the
        user wants a clean slate immediately."""
        if not self.job_manager:
            self.message = "Job manager not available"
            return
        try:
            jobs = self.job_manager.get_jobs_nonblocking(timeout=0.5)
            if jobs is None:
                self.message = "Warning: Job manager busy - try again"
                return

            running_ids = [j.job_id for j in jobs if str(j.status) == 'JobStatus.RUNNING']
            queued_ids = [j.job_id for j in jobs if str(j.status) == 'JobStatus.QUEUED']

            stopped = 0
            for jid in running_ids:
                if self.job_manager.cancel_job(jid):
                    stopped += 1
            cancelled = 0
            for jid in queued_ids:
                if self.job_manager.cancel_job(jid):
                    cancelled += 1

            self.message = f"stop all: stopped {stopped} running, cancelled {cancelled} queued"
        except Exception as e:
            self.message = f"Error in stop all: {str(e)}"

    def handle_cancel_queue(self):
        """Cancel every QUEUED job. Running jobs are left alone to finish.
        Use this to stop auto from feeding more work without disrupting
        in-flight encodes."""
        if not self.job_manager:
            self.message = "Job manager not available"
            return
        try:
            jobs = self.job_manager.get_jobs_nonblocking(timeout=0.5)
            if jobs is None:
                self.message = "Warning: Job manager busy - try again"
                return

            queued_ids = [j.job_id for j in jobs if str(j.status) == 'JobStatus.QUEUED']
            running_count = sum(1 for j in jobs if str(j.status) == 'JobStatus.RUNNING')

            cancelled = 0
            for jid in queued_ids:
                if self.job_manager.cancel_job(jid):
                    cancelled += 1

            if running_count > 0:
                self.message = f"cancel queue: cancelled {cancelled} queued, {running_count} running job(s) left to finish"
            else:
                self.message = f"cancel queue: cancelled {cancelled} queued"
        except Exception as e:
            self.message = f"Error in cancel queue: {str(e)}"

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
            'm': 'lds-compress',
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
                                # Target failed jobs, cancelled jobs, or stuck running jobs
                                # (the job manager will verify if running jobs are truly stuck)
                                if ('failed' in job_status or
                                    'cancelled' in job_status or
                                    'running' in job_status or
                                    (hasattr(job, 'progress') and job.progress > 0)):
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

    def handle_clean_history(self, status_names):
        """Bulk-remove finished jobs from the queue by status name.

        Accepted status names: 'failed', 'cancelled', 'completed'. Active jobs
        (queued, running) are never touched. Used by the 'clean failed',
        'clean cancelled', and 'clean history' commands to reset the lifetime
        counters in the System Status panel.
        """
        if not self.job_manager:
            self.message = "Job manager not available - cannot clean job history"
            return

        from job_queue_manager import JobStatus
        name_to_status = {
            'failed': JobStatus.FAILED,
            'cancelled': JobStatus.CANCELLED,
            'completed': JobStatus.COMPLETED,
        }
        statuses = [name_to_status[n] for n in status_names if n in name_to_status]
        if not statuses:
            self.message = "Nothing to clean — unknown status name(s)."
            return

        try:
            removed = self.job_manager.remove_jobs_by_status(statuses)
            label = "/".join(status_names)
            if removed:
                self.message = f"✓ Removed {removed} {label} job(s) from history"
            else:
                self.message = f"No {label} jobs to remove"
        except Exception as e:
            self.message = f"Error cleaning {','.join(status_names)} jobs: {e}"

    def _project_tracked_files(self, project):
        """Return a dict of {step_label: [file_paths]} for every tracked file
        in the project. Used by hash/check to know what to checksum."""
        files_by_step = {}

        # Capture originals (.lds + .flac + .json)
        capture_files = []
        if hasattr(project, 'capture_files'):
            for key in ('video', 'audio'):
                p = project.capture_files.get(key)
                if p and os.path.isfile(p):
                    capture_files.append(p)
            # Add the .json metadata
            if 'video' in project.capture_files:
                vp = project.capture_files['video']
                base = vp[:-4] if vp.endswith(('.lds', '.ldf')) else os.path.splitext(vp)[0]
                jp = base + '.json'
                if os.path.isfile(jp):
                    capture_files.append(jp)
        if capture_files:
            files_by_step['capture'] = capture_files

        # Downstream outputs
        if hasattr(project, 'output_files'):
            for key, step_label in (
                ('compress', 'compress'),
                ('align', 'align'),
                ('export', 'export'),
                ('final', 'final'),
            ):
                p = project.output_files.get(key)
                if p and os.path.isfile(p):
                    files_by_step[step_label] = [p]
        return files_by_step

    def handle_hash_project(self, project_num):
        """Queue checksum jobs for any of project N's files that lack a hash.

        Skips files already recorded with a current (matching size+mtime)
        hash — that's what 'check N' is for. The intent is "fill in the gaps
        for an existing project that was made before auto-checksum existed."
        """
        project_idx = project_num - 1
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        project = self.current_projects[project_idx]
        if not self.job_manager:
            self.message = "Job manager not available"
            return

        try:
            import validation_log
        except ImportError as e:
            self.message = f"validation_log not available: {e}"
            return

        files_by_step = self._project_tracked_files(project)
        if not files_by_step:
            self.message = f"No tracked files found for {project.name}"
            return

        queued = []
        skipped = []
        for step_label, paths in files_by_step.items():
            # Filter to files that don't already have a current hash
            needs_hash = []
            for p in paths:
                state = validation_log.file_state(p)
                if state == 'no-hash':
                    needs_hash.append(p)
                else:
                    skipped.append(f"{os.path.basename(p)} ({state})")
            if not needs_hash:
                continue
            try:
                job_id = self.job_manager.add_job_nonblocking(
                    job_type='checksum',
                    input_file=needs_hash[0],
                    output_file=needs_hash[0],
                    parameters={
                        'files': needs_hash, 'mode': 'hash', 'step': step_label,
                    },
                    priority=4,
                    project_name=project.name,
                    timeout=1.0,
                )
                if job_id:
                    queued.append(f"{step_label}: {len(needs_hash)} file(s)")
            except Exception as e:
                self.message = f"Failed to queue hash job for {step_label}: {e}"
                return

        if queued:
            queued_text = "; ".join(queued)
            skip_text = f" Skipped {len(skipped)} already-hashed file(s)." if skipped else ""
            self.message = (
                f"✓ Queued hash job(s) for {project.name}: {queued_text}.{skip_text}"
            )
        else:
            self.message = (
                f"All tracked files for {project.name} already have hashes. "
                f"Use 'check {project_num}' to re-check them."
            )

    def handle_check_project(self, project_num, check_all=False):
        """Queue a check-mode checksum job: re-hashes tracked files and
        compares against recorded hashes in the log.

        By default only files whose cached state is touched / changed / invalid
        are re-hashed — files already in VALIDATED state are skipped, because
        the cheap size+mtime check already confirms they haven't been disturbed
        and re-hashing them would waste minutes-to-hours of I/O on a large
        project. Pass check_all=True ('check N --all') to force a full re-hash
        of every tracked file regardless of state — useful for an annual
        archive integrity sweep or before a big move.

        Matches refresh the recorded identity (clearing any TOUCHED state).
        Mismatches are logged and surface as INVALID in the WCC matrix.
        """
        project_idx = project_num - 1
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        project = self.current_projects[project_idx]
        if not self.job_manager:
            self.message = "Job manager not available"
            return

        try:
            import validation_log
        except ImportError as e:
            self.message = f"validation_log not available: {e}"
            return

        files_by_step = self._project_tracked_files(project)
        if not files_by_step:
            self.message = f"No tracked files found for {project.name}"
            return

        # Flatten all files into a single check job so we get one PASS/FAIL
        # entry per run rather than per-step.
        all_files = []
        for paths in files_by_step.values():
            all_files.extend(paths)
        if not all_files:
            self.message = f"No files to check for {project.name}"
            return

        if check_all:
            files_to_check = all_files
            scope_desc = f"all {len(all_files)} tracked file(s)"
        else:
            # Narrow to files that the cheap state check says actually need
            # re-checking. Files in VALIDATED or NO-HASH state are skipped:
            # VALIDATED is already confirmed (re-hashing adds no info);
            # NO-HASH is the 'hash N' command's territory, not check.
            needs_check_states = ('touched', 'changed', 'invalid')
            files_to_check = [
                p for p in all_files
                if validation_log.file_state(p) in needs_check_states
            ]
            if not files_to_check:
                self.message = (
                    f"Nothing to re-check for {project.name}: every tracked "
                    f"file is already VALIDATED. Use 'check {project_num} --all' "
                    f"to force a full re-hash anyway."
                )
                return
            scope_desc = (
                f"{len(files_to_check)} of {len(all_files)} tracked file(s) "
                f"(only the touched / changed / invalid ones)"
            )

        try:
            job_id = self.job_manager.add_job_nonblocking(
                job_type='checksum',
                input_file=files_to_check[0],
                output_file=files_to_check[0],
                parameters={
                    'files': files_to_check, 'mode': 'check', 'step': 'check',
                },
                priority=4,
                project_name=project.name,
                timeout=1.0,
            )
            if job_id:
                self.message = (
                    f"✓ Queued check job for {project.name}: re-hashing "
                    f"{scope_desc}. Result will appear in the validation "
                    f"log; matches refresh the recorded identity (clearing "
                    f"TOUCHED), mismatches flip cells to INVALID."
                )
            else:
                self.message = f"Failed to queue check job for {project.name}"
        except Exception as e:
            self.message = f"Error queuing check job: {e}"

    # Backwards-compatible alias for the prior method name; some callers
    # outside this module may still reach for handle_verify_project.
    handle_verify_project = handle_check_project

    def handle_compress_validate(self, project_num):
        """Option C: Full structural validation of a project's .ldf master.

        Streams the .ldf through ld-ldf-reader, counts decoded bytes, compares
        to the expected count from the source .lds. SLOW (~10 min per hour of
        capture) but definitive — gives you confidence to delete the .lds.

        Triggered by typing e.g. '1mv' (project 1, compress, validate).
        """
        project_idx = project_num - 1
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        project = self.current_projects[project_idx]

        # Locate the .lds (or .ldf) source and the .ldf to validate
        lds_path = None
        ldf_path = None
        if hasattr(project, 'capture_files') and 'video' in project.capture_files:
            cap = project.capture_files['video']
            if cap.endswith('.lds'):
                lds_path = cap
                ldf_path = cap[:-4] + '.ldf'
            elif cap.endswith('.ldf'):
                ldf_path = cap

        if not ldf_path or not os.path.exists(ldf_path):
            self.message = f"No .ldf file found for {project.name}"
            return
        if not lds_path or not os.path.exists(lds_path):
            # Tier 3 is a comparison against the source .lds. Without it,
            # there is no comparison to perform — only the weaker FLAC-
            # integrity check, which Tier 2 already runs post-compress.
            # Refuse rather than waste 10+ minutes on a result that
            # cannot honestly claim "safe to delete the .lds".
            self.message = (
                f"Cannot run Tier 3 for {project.name}: source .lds is missing. "
                f"Tier 3 requires the .lds to compare decoded sample counts against."
            )
            return

        self.message = (
            f"Validating {os.path.basename(ldf_path)} — streaming full decode "
            f"and counting samples. This may take 10+ min per hour of capture…"
        )
        self._run_compress_validate_background(ldf_path, lds_path, project.name)

    def _run_compress_validate_background(self, ldf_path, lds_path, project_name):
        """Run the full ldf validation in a background thread so the UI stays
        responsive. Posts result via self.message when done.

        lds_path is required; handle_compress_validate refuses upfront when it
        is missing, since without the source .lds there is no Nmv comparison
        to perform (only the lighter FLAC integrity check, which the
        post-compress pipeline already runs).

        project_name is used to flag this project's COMPRESS row as
        VERIFYING in the matrix for the duration of the run.
        """
        import threading
        import shutil
        import subprocess

        analyzer = self.workflow_analyzer

        def worker():
            # Register so the matrix flips this project's COMPRESS row to
            # VERIFYING for the duration AND can render bar/percent/rate/ETA
            # from the same dict the job-queue progress path uses. Always
            # remove the entry in a finally so a crash mid-run doesn't leave
            # the row stuck in VERIFYING.
            if analyzer is not None:
                analyzer.ldf_validation_in_progress[project_name] = {
                    'percentage': 0.0,
                    'fps': 0.0,
                    'rate_unit_label': 'MB/s',
                    'runtime_seconds': 0.0,
                }
            try:
                tool = shutil.which('ld-ldf-reader')
                if not tool:
                    self.message = "ld-ldf-reader not on PATH — cannot validate"
                    return

                import time as _t

                # Precompute the expected decoded byte count so we can show
                # live progress against it (and reuse it for the pass/fail
                # comparison below).
                lds_size = os.path.getsize(lds_path)
                expected_bytes = lds_size * 4 // 5 * 2  # 16-bit samples
                basename = os.path.basename(ldf_path)

                start = _t.time()
                proc = subprocess.Popen(
                    [tool, ldf_path, '0'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )

                def _fmt_eta(s):
                    s = max(0, int(s))
                    if s < 60:
                        return f"{s}s"
                    if s < 3600:
                        return f"{s // 60}m{s % 60:02d}s"
                    return f"{s // 3600}h{(s % 3600) // 60:02d}m"

                # Stream and count bytes. Update self.message every ~2 s so
                # the status bar reflects live progress instead of going
                # silent for the 10–30 min the decode takes.
                total = 0
                last_msg_update = 0.0
                while True:
                    chunk = proc.stdout.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    now = _t.time()
                    if now - last_msg_update >= 2.0:
                        last_msg_update = now
                        elapsed_so_far = now - start
                        pct = (total / expected_bytes * 100) if expected_bytes else 0
                        rate_mbs = (total / elapsed_so_far / 1e6) if elapsed_so_far > 0 else 0
                        if rate_mbs > 0 and total < expected_bytes:
                            eta = (expected_bytes - total) / (rate_mbs * 1e6)
                            eta_str = _fmt_eta(eta)
                        else:
                            eta_str = "?"
                        self.message = (
                            f"Validating {basename}: {pct:5.1f}%  "
                            f"{total / 1e9:.1f}/{expected_bytes / 1e9:.1f} GB  "
                            f"{rate_mbs:.0f} MB/s  ETA {eta_str}"
                        )
                        # Also feed the matrix-cell progress renderer.
                        # 'fps' is bytes/sec; rate_unit_label='MB/s' makes
                        # the renderer convert and format correctly.
                        if analyzer is not None:
                            analyzer.ldf_validation_in_progress[project_name] = {
                                'percentage': pct,
                                'fps': rate_mbs * 1e6,
                                'rate_unit_label': 'MB/s',
                                'runtime_seconds': elapsed_so_far,
                            }
                proc.wait()
                elapsed = _t.time() - start

                # Tier 3 sample-count comparison. The only path to passed=True
                # is decoded-bytes vs expected-from-lds-size within slack;
                # any other outcome is a fail.
                ratio = total / expected_bytes if expected_bytes else 0
                # Allow up to 1 MB slack (FLAC frame boundary alignment)
                if abs(expected_bytes - total) <= 1_000_000:
                    passed = True
                    detail = (f"decoded {total:_} bytes (expected {expected_bytes:_}, "
                              f"{ratio*100:.4f}%) in {elapsed:.0f}s")
                    self.message = (
                        f"✓ Validate PASS for {os.path.basename(ldf_path)}: "
                        f"{detail}. Safe to delete .lds."
                    )
                else:
                    passed = False
                    detail = (f"decoded {total:_} bytes, expected {expected_bytes:_} "
                              f"({ratio*100:.2f}%)")
                    self.message = (
                        f"✗ Validate FAIL for {os.path.basename(ldf_path)}: "
                        f"{detail}. DO NOT DELETE .lds."
                    )

                # Compute checksums of the capture originals and write a
                # validation log entry. This is the user-requested permanent
                # record of "I validated this at time X and the files looked
                # like Y" — useful before any destructive action on the .lds.
                try:
                    self.message = (
                        f"Validation decode done — computing checksums of originals "
                        f"for the validation log (this can take a few minutes)…"
                    )
                    import validation_log
                    file_hashes = validation_log.hash_capture_originals(
                        ldf_path, skip_lds_hash=False,
                    )
                    validation_log.log_tier3(
                        ldf_path, passed, detail,
                        file_hashes=file_hashes,
                        elapsed_seconds=_t.time() - start,
                    )
                    log_path = validation_log.get_log_path(ldf_path)
                    # Re-state the pass/fail message now that the log is written
                    verdict_icon = "✓" if passed else "✗"
                    self.message = (
                        f"{verdict_icon} Validate {'PASS' if passed else 'FAIL'} — "
                        f"{detail}. Log: {os.path.basename(log_path)}"
                    )
                except Exception as log_err:
                    # Don't lose the validation result if logging fails
                    self.message += f" (validation log write failed: {log_err})"

                # Write the .ldf.validated sidecar on PASS; remove any prior
                # one on FAIL so it can't keep claiming a stale validation.
                try:
                    if passed:
                        sidecar_path = validation_log.write_validated_sidecar(
                            ldf_path,
                            lds_path=lds_path,
                            lds_size=lds_size,
                            lds_mtime=os.path.getmtime(lds_path),
                            ldf_size=os.path.getsize(ldf_path),
                            ldf_mtime=os.path.getmtime(ldf_path),
                            decoded_bytes=total,
                            expected_bytes=expected_bytes,
                            slack_bytes=1_000_000,
                            elapsed_seconds=elapsed,
                            file_hashes=file_hashes,
                        )
                        self.message += f"  Sidecar: {os.path.basename(sidecar_path)}"
                    else:
                        validation_log.remove_validated_sidecar(ldf_path)
                except Exception as sidecar_err:
                    # Don't lose the validation result if the sidecar fails
                    self.message += f" (sidecar write failed: {sidecar_err})"
            except Exception as e:
                self.message = f"Validate error: {e}"
            finally:
                # Clear the in-progress entry so the matrix's COMPRESS row
                # returns to its post-validation state (VALIDATED if the
                # hash log is happy, otherwise whatever the underlying
                # check resolves to). pop(..., None) so a duplicate clear
                # is harmless.
                if analyzer is not None:
                    analyzer.ldf_validation_in_progress.pop(project_name, None)

        threading.Thread(target=worker, daemon=True).start()

    # ----- Archive staging -----------------------------------------------
    #
    # 'stage N' moves a project's intermediate files into a <basename>.intermediate/
    # subfolder, leaving only the archive set (.ldf, .ldf.validated, .flac,
    # .json, .capture.log, _final.mkv, _validation.log, plus the portable
    # .sha256 sidecars) at the top level.
    # The move is non-destructive — nothing is deleted, and 'unstage N'
    # restores everything. The .ldf.validated sidecar is the gate: staging
    # is refused without it, so the Tier 3 round-trip has demonstrably
    # passed before any intermediate is set aside.

    # Filenames (relative to project source dir, given a base name) that
    # move out of the top level when a project is staged for archive.
    # Anything not in this list stays at the top level.
    _ARCHIVE_INTERMEDIATE_SUFFIXES = (
        '.lds',                          # raw RF capture (covered by .ldf+.validated)
        '.tbc',                          # decoded TBC (regenerable from .ldf)
        '.tbc.json',                     # TBC metadata
        '_chroma.tbc',                   # chroma plane
        '.log',                          # vhs-decode's own log
        '_ffv1.mkv',                     # intermediate export
        '_aligned.flac',                 # aligned audio
        '_aligned.flac.watchdog.log',    # align watchdog log
    )

    def _stage_intermediate_dir(self, project):
        """Return the path to this project's .intermediate/ subfolder."""
        source_dir = getattr(project, 'source_directory', None)
        name = getattr(project, 'name', None)
        if not source_dir or not name:
            return None
        return os.path.join(source_dir, name + '.intermediate')

    def _find_ldf_path(self, project):
        """Locate a project's .ldf path (compressed master), or None."""
        if hasattr(project, 'output_files') and 'compress' in project.output_files:
            return project.output_files['compress']
        if hasattr(project, 'capture_files') and 'video' in project.capture_files:
            cap = project.capture_files['video']
            if cap.endswith('.ldf'):
                return cap
            if cap.endswith('.lds'):
                return cap[:-4] + '.ldf'
        return None

    def handle_stage_project(self, project_num):
        """Move a project's intermediate files into <basename>.intermediate/.

        Refuses unless the .ldf.validated sidecar is present (the Tier 3
        gate). Non-destructive: every file is mv'd, not deleted, so a
        later 'unstage N' restores the original layout. The .lds moves
        too — once Tier 3 has passed it's safely droppable, but mv-not-rm
        defers the actual delete to the user's own schedule.
        """
        project_idx = project_num - 1
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        project = self.current_projects[project_idx]

        ldf_path = self._find_ldf_path(project)
        if not ldf_path or not os.path.exists(ldf_path):
            self.message = f"Cannot stage {project.name}: no .ldf file found."
            return

        sidecar = ldf_path + '.validated'
        if not os.path.isfile(sidecar):
            self.message = (
                f"Refusing to stage {project.name}: {os.path.basename(sidecar)} "
                f"missing. Run {project_num}mv first to validate the .ldf against "
                f"its source .lds."
            )
            return

        source_dir = os.path.dirname(ldf_path)
        base = project.name
        intermediate_dir = self._stage_intermediate_dir(project)
        if not intermediate_dir:
            self.message = f"Cannot stage {project.name}: source directory unknown."
            return

        # Build the move list — only files that actually exist
        to_move = []
        for suffix in self._ARCHIVE_INTERMEDIATE_SUFFIXES:
            candidate = os.path.join(source_dir, base + suffix)
            if os.path.isfile(candidate):
                to_move.append((base + suffix, candidate))

        if not to_move:
            self.message = f"No intermediate files to stage for {project.name}."
            return

        # Run in a background thread — moving the .lds is metadata-only on
        # the same filesystem but can be slow if mounts differ, and we
        # don't want to block the UI.
        import threading

        def worker():
            try:
                os.makedirs(intermediate_dir, exist_ok=True)
                moved = []
                failed = []
                for name, src in to_move:
                    dst = os.path.join(intermediate_dir, name)
                    try:
                        os.rename(src, dst)
                        moved.append(name)
                    except OSError as e:
                        failed.append((name, str(e)))
                if failed:
                    self.message = (
                        f"Staged {project.name}: moved {len(moved)}, "
                        f"failed {len(failed)} (first: {failed[0][0]} — {failed[0][1]})"
                    )
                else:
                    self.message = (
                        f"✓ Staged {project.name}: {len(moved)} files moved into "
                        f"{os.path.basename(intermediate_dir)}/"
                    )
            except OSError as e:
                self.message = f"Stage error for {project.name}: {e}"

        self.message = (
            f"Staging {project.name}: moving {len(to_move)} intermediate files…"
        )
        threading.Thread(target=worker, daemon=True).start()

    def handle_unstage_project(self, project_num):
        """Reverse of stage: move files back from <basename>.intermediate/
        into the project root and remove the (now empty) subfolder.

        Refuses to clobber a file that exists at the top level (e.g. a
        new run produced a fresh .tbc while the old one was staged) —
        that one stays in intermediate/ and gets reported.
        """
        project_idx = project_num - 1
        if project_idx >= len(self.current_projects):
            self.message = f"No project at position {project_num}"
            return
        project = self.current_projects[project_idx]

        intermediate_dir = self._stage_intermediate_dir(project)
        if not intermediate_dir or not os.path.isdir(intermediate_dir):
            self.message = f"No staging folder to undo for {project.name}."
            return

        source_dir = project.source_directory

        import threading

        def worker():
            try:
                entries = sorted(os.listdir(intermediate_dir))
                moved = []
                failed = []
                for name in entries:
                    src = os.path.join(intermediate_dir, name)
                    dst = os.path.join(source_dir, name)
                    if os.path.exists(dst):
                        failed.append((name, "top-level file with same name exists; not clobbering"))
                        continue
                    try:
                        os.rename(src, dst)
                        moved.append(name)
                    except OSError as e:
                        failed.append((name, str(e)))
                # Remove the subfolder if empty; leave it otherwise.
                try:
                    os.rmdir(intermediate_dir)
                    folder_gone = True
                except OSError:
                    folder_gone = False
                if failed:
                    self.message = (
                        f"Unstaged {project.name}: restored {len(moved)}, "
                        f"failed {len(failed)} (first: {failed[0][0]} — {failed[0][1]}). "
                        f"{os.path.basename(intermediate_dir)}/ still present."
                    )
                elif folder_gone:
                    self.message = (
                        f"✓ Unstaged {project.name}: {len(moved)} files restored, "
                        f"{os.path.basename(intermediate_dir)}/ removed."
                    )
                else:
                    self.message = (
                        f"✓ Unstaged {project.name}: {len(moved)} files restored; "
                        f"{os.path.basename(intermediate_dir)}/ kept (not empty)."
                    )
            except OSError as e:
                self.message = f"Unstage error for {project.name}: {e}"

        self.message = f"Unstaging {project.name}…"
        threading.Thread(target=worker, daemon=True).start()

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
        
        print("\nRun pipeline steps  (project number + step letter):")
        print("  1D            Start Decode for project 1 (uses config default PAL/NTSC)")
        print("  1DP / 1DN     Start Decode for project 1 forcing PAL / NTSC")
        print("  2M            Start Compress for project 2  (.lds -> .ldf)")
        print("  3E            Start Export for project 3    (.tbc -> _ffv1.mkv)")
        print("  1A            Start Audio align for project 1")
        print("  2F            Start Final mux for project 2")
        print("  1X            Open the per-project flags dialog (5 pages: decode,")
        print("                export, audio, compress, segment)")
        print("  auto          Queue every step that's currently READY across all projects")

        print("\nValidation, hashing, archive staging  (operate on a whole project):")
        print("  1mv           Tier 3 validation: decode the .ldf and compare byte count")
        print("                to the source .lds. On PASS writes <basename>.ldf.validated")
        print("                next to the .ldf (the gate for safely deleting the .lds).")
        print("  hash 1        Hash any of project 1's tracked files that don't yet")
        print("                have a recorded hash in <basename>_validation.log. Also")
        print("                writes a portable <file>.sha256 next to each hashed file.")
        print("  check 1       Re-hash project 1's TOUCHED / CHANGED / INVALID files and")
        print("                compare against the log. Skips files already VALIDATED so the")
        print("                check stays fast even on big projects. Matches refresh the")
        print("                recorded identity (clearing TOUCHED); mismatches flip matrix")
        print("                cells to INVALID. ('verify 1' is a backwards-compatible alias.)")
        print("  check 1 --all Force a full re-hash of every tracked file, including ones")
        print("                already VALIDATED. Use for a thorough integrity sweep.")
        print("  stage 1       Move project 1's intermediate files (.lds, .tbc, *_chroma.tbc,")
        print("                .tbc.json, decode .log, _ffv1.mkv, _aligned.flac, watchdog log)")
        print("                into a <basename>.intermediate/ subfolder. Matrix row flips to")
        print("                ARCH. Refuses unless .ldf.validated is present.")
        print("  unstage 1     Reverse of stage: move the intermediate files back to the")
        print("                top level and remove the (now-empty) subfolder.")

        print("\nRe-run, stop, clean:")
        print("  force 1e      Force-overwrite existing outputs and re-run the step.")
        print("                Required to re-run any step that's COMPLETE/VAL/TOUCHED/")
        print("                CHANGED/INVALID/HASH. For decode, also synchronously deletes")
        print("                any leftover .tbc / _chroma.tbc / .tbc.json / .log first.")
        print("  stop 1e       Stop one project+step job (cancels queued, terminates running).")
        print("  stop all      Stop everything immediately.")
        print("  cancel queue  Cancel queued jobs but let running ones finish.")
        print("  clean 1e      Reset a stuck progress display for one step.")
        print("  clean failed     Remove all FAILED entries from job history.")
        print("  clean cancelled  Remove all CANCELLED entries from job history.")
        print("  clean history    Remove all completed/failed/cancelled entries.")

        print("\nSelection:")
        print("  1..N          Select a project from the workflow matrix (N = however")
        print("                many projects you have).")
        print("  J1..JN        Select a job from the active jobs list.")
        print("  D             Show details for the selected project or job.")
        print("  R             Retry / restart the selected failed step.")
        print("  X             Stop the selected job. (When typed as part of 1X / 2X / ...")
        print("                opens the flags dialog instead.)")

        print("\nOther:")
        print("  cleanup       Clean up /tmp scratch files (ffmpeg, tbc, vhs).")
        print("  settemp       Pick the disk with the most free space and set it as")
        print("                $TMPDIR for this session.")
        print("  H             Show this help.")
        print("  Q             Quit back to the main menu.")

        print("\nStep Letters:")
        print("  D = (D)ecode, M = Co(M)press, E = (E)xport")
        print("  A = (A)lign,  F = (F)inal,    X = fla(X) dialog")

        print("\nTips:")
        print("  - Coordinate commands (1D, 2M, ...) work on any step status — the WCC")
        print("    will tell you to use 'force' if the step has already completed.")
        print("  - 'auto' queues every READY step across all projects; combine with the")
        print("    storage-aware concurrency cap to leave a long run going overnight.")
        print("  - Run 1mv before deleting any .lds — the .ldf.validated sidecar is the")
        print("    gate that proves the .ldf is a complete lossless compression.")
        print("  - Every hashed file also gets a portable <file>.sha256 sidecar next to it.")
        print("    Anyone with sha256sum / shasum / Get-FileHash can verify it without")
        print("    this toolkit, e.g.  sha256sum -c Foo.ldf.sha256")
        print("  - 'stage 1' is non-destructive (move, not delete). Reverse with 'unstage 1';")
        print("    only rm -rf the .intermediate/ subfolder once you're satisfied.")

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
                print(f"Lifetime Jobs: {status['total_jobs']}  (cumulative; reset via 'clean history')")
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
            print("e. Return to VHS-Decode Menu")

            choice = input("\nSelect workflow option (1-6/e): ").strip().lower()

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
            elif choice == 'e':
                break  # Return to VHS-Decode menu
            else:
                print("\nInvalid selection. Please enter 1-6 or e.")
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
