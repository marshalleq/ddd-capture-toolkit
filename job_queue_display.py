#!/usr/bin/env python3
"""
Job Queue Display Manager
Displays job queue status and progress without triggering jobs
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import List

try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.console import Console
    from rich.text import Text
    from rich.table import Table
    from rich.columns import Columns
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from job_queue_manager import get_job_queue_manager, JobStatus, QueuedJob
from shared.progress_display_utils import ProgressDisplayUtils

# Import ETA calculation functions from the parallel decoder
try:
    from parallel_vhs_decode import ParallelVHSDecoder
    PARALLEL_DECODE_AVAILABLE = True
except ImportError:
    PARALLEL_DECODE_AVAILABLE = False
    ParallelVHSDecoder = None

class JobQueueDisplay:
    """Displays job queue status with real-time updates"""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.job_manager = get_job_queue_manager()
        self.show_completed = False
        self.auto_refresh = True
        # Cache for total frame counts from JSON metadata
        self._frame_count_cache = {}
        # Initialize the parallel decoder for its utility functions
        self._decoder = ParallelVHSDecoder() if PARALLEL_DECODE_AVAILABLE else None
    
    def _get_total_frames(self, job: QueuedJob) -> int:
        """Get total frame count for a job using JSON metadata (with caching)"""
        cache_key = f"{job.input_file}_{job.parameters.get('video_standard', 'pal')}"
        
        if cache_key in self._frame_count_cache:
            return self._frame_count_cache[cache_key]
        
        total_frames = 0
        if self._decoder and job.job_type == "vhs-decode":
            try:
                total_frames = self._decoder.get_frame_count_from_json(
                    job.input_file,
                    job.parameters.get('video_standard', 'pal')
                )
                self._frame_count_cache[cache_key] = total_frames
            except Exception:
                pass  # Fallback to 0 if JSON reading fails
        
        return total_frames
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as human-readable time"""
        return ProgressDisplayUtils.format_time(seconds)
        
    def create_status_panel(self) -> Panel:
        """Create the main status panel"""
        status = self.job_manager.get_queue_status()
        
        status_text = Text("Job Queue Status", style="bold blue")
        status_content = Text()
        
        # Queue statistics
        status_content.append(f"Total Jobs: {status['total_jobs']}", style="white")
        status_content.append(" | ", style="dim")
        status_content.append(f"Queued: {status['queued']}", style="yellow")
        status_content.append(" | ", style="dim")
        status_content.append(f"Running: {status['running']}", style="green")
        status_content.append(" | ", style="dim")
        status_content.append(f"Completed: {status['completed']}", style="blue")
        
        if status['failed'] > 0:
            status_content.append(" | ", style="dim")
            status_content.append(f"Failed: {status['failed']}", style="red")
        
        if status['cancelled'] > 0:
            status_content.append(" | ", style="dim")
            status_content.append(f"Cancelled: {status['cancelled']}", style="magenta")
        
        status_content.append("\n")
        status_content.append(f"Max Concurrent: {status['max_concurrent']}", style="cyan")
        status_content.append(" | ", style="dim")
        processor_status = "Running" if status['processor_running'] else "Stopped"
        processor_style = "green" if status['processor_running'] else "red"
        status_content.append(f"Processor: {processor_status}", style=processor_style)
        
        return Panel(status_content, title="System Status", border_style="blue")
    
    def create_jobs_table(self) -> Table:
        """Create the jobs table"""
        table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        table.add_column("Job ID", style="cyan", no_wrap=True, width=15)
        table.add_column("Type", style="magenta", no_wrap=True, width=12)
        table.add_column("Input File", style="white", width=25)
        table.add_column("Status", style="yellow", no_wrap=True, width=12)
        table.add_column("Progress", width=20)
        table.add_column("FPS", style="dim", width=8)
        table.add_column("ETA", style="green", width=10)
        
        jobs = self.job_manager.get_jobs()
        
        # Filter jobs based on display settings
        if not self.show_completed:
            jobs = [j for j in jobs if j.status not in [JobStatus.COMPLETED, JobStatus.CANCELLED]]
        
        # Sort by status priority: Running > Queued > Failed > Completed
        priority_order = {
            JobStatus.RUNNING: 1,
            JobStatus.QUEUED: 2, 
            JobStatus.FAILED: 3,
            JobStatus.COMPLETED: 4,
            JobStatus.CANCELLED: 5
        }
        jobs.sort(key=lambda j: (priority_order.get(j.status, 99), j.created_at))
        
        for job in jobs:
            # Format job ID
            job_id_display = job.job_id.split('_')[0] + "_" + job.job_id.split('_')[-1]
            
            # Format input file (show basename only)
            input_file = os.path.basename(job.input_file)
            if len(input_file) > 25:
                input_file = input_file[:22] + "..."
            
            # Format status with colour
            status_text = job.status.value.title()
            if job.status == JobStatus.RUNNING:
                status_style = "green bold"
            elif job.status == JobStatus.QUEUED:
                status_style = "yellow"
            elif job.status == JobStatus.COMPLETED:
                status_style = "blue"
            elif job.status == JobStatus.FAILED:
                status_style = "red"
            elif job.status == JobStatus.CANCELLED:
                status_style = "magenta"
            else:
                status_style = "white"
            
            # Format progress
            if job.progress > 0:
                progress_bar = ProgressDisplayUtils.create_progress_bar(job.progress, width=20)
                progress_text = f"[{progress_bar}] {job.progress:.1f}%"
            else:
                progress_text = "Waiting..."
            
            # Calculate FPS and ETA using shared utility
            fps_text = "-"
            eta_text = "-"
            
            if job.status == JobStatus.RUNNING and job.started_at and job.progress > 0:
                progress_info = ProgressDisplayUtils.extract_job_progress_info(
                    self.job_manager, os.path.basename(job.input_file), job.job_type
                )
                
                if progress_info:
                    if progress_info.get('fps', 0) > 0:
                        fps_text = f"{progress_info['fps']:.1f}"
                    
                    if progress_info.get('eta_seconds', 0) > 0:
                        eta_text = self._format_time(progress_info['eta_seconds'])
            
            # Add error message to status if failed
            display_status = status_text
            if job.status == JobStatus.FAILED and job.error_message:
                error_preview = job.error_message[:20] + "..." if len(job.error_message) > 20 else job.error_message
                display_status = f"{status_text}: {error_preview}"
            
            table.add_row(
                job_id_display,
                job.job_type,
                input_file,
                Text(display_status, style=status_style),
                progress_text,
                fps_text,
                eta_text
            )
        
        return table
    
    def create_controls_panel(self) -> Panel:
        """Create the controls panel"""
        controls = Text("Controls", style="bold green")
        controls.append("\\n")
        controls.append("R", style="bold cyan")
        controls.append(" - Refresh display manually\\n", style="white")
        controls.append("T", style="bold cyan") 
        controls.append(" - Toggle auto-refresh\\n", style="white")
        controls.append("C", style="bold cyan")
        controls.append(" - Toggle completed jobs display\\n", style="white")
        controls.append("S", style="bold cyan")
        controls.append(" - Show queue settings\\n", style="white")
        controls.append("Q", style="bold cyan")
        controls.append(" - Quit to menu\\n", style="white")
        
        return Panel(controls, title="Controls", border_style="green")
    
    def create_layout(self) -> Layout:
        """Create the main display layout"""
        layout = Layout()
        
        # Main structure
        layout.split_column(
            Layout(self.create_status_panel(), size=5),
            Layout(name="main_content"),
            Layout(self.create_controls_panel(), size=8)
        )
        
        # Split main content
        layout["main_content"].split_row(
            Layout(Panel(self.create_jobs_table(), title="Job Queue", border_style="cyan")),
            Layout(size=25, name="side_panel")
        )
        
        # Add side panel content
        settings_text = Text("Queue Settings", style="bold magenta")
        settings_content = Text()
        settings_content.append(f"Max Concurrent Jobs: {self.job_manager.max_concurrent_jobs}\n", style="cyan")
        settings_content.append(f"Auto-refresh: {'On' if self.auto_refresh else 'Off'}\n", style="yellow")
        settings_content.append(f"Show Completed: {'On' if self.show_completed else 'Off'}\n", style="blue")
        settings_content.append(f"\nLast Updated:\n{datetime.now().strftime('%H:%M:%S')}", style="dim")
        
        layout["side_panel"].update(Panel(settings_content, title="Settings", border_style="magenta"))
        
        return layout
    
    def show_queue_settings(self):
        """Show queue settings and allow modification"""
        clear_screen()
        print("JOB QUEUE SETTINGS")
        print("=" * 30)
        
        status = self.job_manager.get_queue_status()
        print(f"Current max concurrent jobs: {status['max_concurrent']}")
        print(f"Processor status: {'Running' if status['processor_running'] else 'Stopped'}")
        print(f"Jobs in queue: {status['total_jobs']}")
        print()
        
        print("SETTINGS MENU:")
        print("1. Change max concurrent jobs")
        print("2. Start/stop job processor")
        print("3. Clean up old jobs")
        print("4. View detailed job information")
        print("5. Return to display")
        
        choice = input("\\nSelect option (1-5): ").strip()
        
        if choice == '1':
            self._change_max_concurrent()
        elif choice == '2':
            self._toggle_processor()
        elif choice == '3':
            self._cleanup_old_jobs()
        elif choice == '4':
            self._show_job_details()
        
        input("\\nPress Enter to continue...")
    
    def _change_max_concurrent(self):
        """Change max concurrent jobs setting"""
        try:
            current = self.job_manager.max_concurrent_jobs
            new_max = input(f"Enter new max concurrent jobs (1-8, current: {current}): ").strip()
            
            if new_max:
                max_jobs = int(new_max)
                if 1 <= max_jobs <= 8:
                    self.job_manager.set_max_concurrent_jobs(max_jobs)
                    print(f"Max concurrent jobs set to {max_jobs}")
                else:
                    print("Please enter a number between 1 and 8")
            
        except ValueError:
            print("Invalid number entered")
    
    def _toggle_processor(self):
        """Start or stop the job processor"""
        if self.job_manager.stop_processing:
            self.job_manager.start_processor()
            print("Job processor started")
        else:
            self.job_manager.stop_processor()
            print("Job processor stopped")
    
    def _cleanup_old_jobs(self):
        """Clean up old completed jobs"""
        try:
            days = input("Remove completed/failed jobs older than how many days? [7]: ").strip()
            days = int(days) if days else 7
            
            print(f"Cleaning up jobs older than {days} days...")
            self.job_manager.cleanup_old_jobs(days)
            print("Cleanup completed")
            
        except ValueError:
            print("Invalid number entered")
    
    def _show_job_details(self):
        """Show detailed information about jobs"""
        jobs = self.job_manager.get_jobs()
        
        if not jobs:
            print("No jobs in queue")
            return
        
        print("\\nDETAILED JOB INFORMATION:")
        print("=" * 50)
        
        for i, job in enumerate(jobs, 1):
            print(f"\\n{i}. Job: {job.job_id}")
            print(f"   Type: {job.job_type}")
            print(f"   Input: {job.input_file}")
            print(f"   Output: {job.output_file}")
            print(f"   Status: {job.status.value}")
            print(f"   Progress: {job.progress:.1f}%")
            print(f"   Created: {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if job.started_at:
                print(f"   Started: {job.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if job.completed_at:
                print(f"   Completed: {job.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if job.error_message:
                print(f"   Error: {job.error_message}")
            if job.parameters:
                print(f"   Parameters: {job.parameters}")
    
    def run_display(self):
        """Run the interactive display"""
        if not RICH_AVAILABLE:
            return self.run_simple_display()
        
        try:
            import termios
            import tty
            
            # Save original terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
            with Live(self.create_layout(), refresh_per_second=2) as live:
                while True:
                    if self.auto_refresh:
                        live.update(self.create_layout())
                    
                    # Non-blocking input check with better terminal handling
                    import select
                    
                    if select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1).lower()
                        
                        if key == 'q':
                            break
                        elif key == 'r':
                            live.update(self.create_layout())
                        elif key == 't':
                            self.auto_refresh = not self.auto_refresh
                            live.update(self.create_layout())  # Update to show change
                        elif key == 'c':
                            self.show_completed = not self.show_completed
                            live.update(self.create_layout())  # Update to show change
                        elif key == 's':
                            live.stop()
                            # Restore terminal settings temporarily
                            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                            self.show_queue_settings()
                            # Reset terminal for live display
                            tty.setcbreak(sys.stdin.fileno())
                            live.start()
                    
                    if not self.auto_refresh:
                        time.sleep(1)
                        
        except (KeyboardInterrupt, EOFError):
            pass
        except ImportError:
            # Fallback if termios not available (Windows)
            print("\nAdvanced terminal controls not available on this system.")
            print("Press Ctrl+C to exit or use the simple display mode.")
            self.run_simple_display()
        finally:
            try:
                # Restore original terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass
    
    def run_simple_display(self):
        """Run a simple text-based display for systems without Rich"""
        try:
            while True:
                clear_screen()
                print("JOB QUEUE DISPLAY")
                print("=" * 50)
                
                # Status
                status = self.job_manager.get_queue_status()
                print(f"Status: {status['running']} running, {status['queued']} queued, "
                      f"{status['completed']} completed, {status['failed']} failed")
                print(f"Max concurrent: {status['max_concurrent']} | "
                      f"Processor: {'Running' if status['processor_running'] else 'Stopped'}")
                print()
                
                # Jobs
                jobs = self.job_manager.get_jobs()
                if not self.show_completed:
                    jobs = [j for j in jobs if j.status not in [JobStatus.COMPLETED, JobStatus.CANCELLED]]
                
                if jobs:
                    print("JOBS:")
                    print("-" * 80)
                    for job in jobs:
                        status_char = {
                            JobStatus.QUEUED: "⏳",
                            JobStatus.RUNNING: "▶️",
                            JobStatus.COMPLETED: "✅",
                            JobStatus.FAILED: "❌",
                            JobStatus.CANCELLED: "🚫"
                        }.get(job.status, "?")
                        
                        print(f"{status_char} {job.job_type}: {os.path.basename(job.input_file)} "
                              f"({job.status.value}) - {job.progress:.1f}%")
                else:
                    print("No jobs to display")
                
                print("\\nControls: R)efresh, C)ompleted toggle, S)ettings, Q)uit")
                
                # Simple input handling
                print("\\n[Auto-refreshing every 3 seconds - press Enter for menu]")
                import select
                if select.select([sys.stdin], [], [], 3)[0]:
                    choice = input().strip().lower()
                    if choice == 'q':
                        break
                    elif choice == 'c':
                        self.show_completed = not self.show_completed
                    elif choice == 's':
                        self.show_queue_settings()
                        
        except KeyboardInterrupt:
            pass

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_job_queue_display():
    """Standalone function to show the job queue status display"""
    try:
        display = JobQueueDisplay()
        display.run_display()
        
    except ImportError as e:
        print(f"ERROR: Job queue display system not available: {e}")
        print("Please ensure all required modules are installed")
        input("\nPress Enter to return to menu...")
    except Exception as e:
        print(f"Error running job queue display: {e}")
        input("\nPress Enter to return to menu...")

if __name__ == '__main__':
    print("Job Queue Display")
    print("Starting display...")
    
    show_job_queue_display()
