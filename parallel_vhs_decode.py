#!/usr/bin/env python3
"""
Parallel VHS Decode Manager
Advanced parallel processing system for VHS-decode with real-time progress display.
Supports scanning multiple configured processing locations for RF files.
"""

import os
import sys
import json
import time
import subprocess
import threading
import re
from datetime import datetime, timedelta
from multiprocessing import Process, Queue, Manager
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path

try:
    from rich.live import Live
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.console import Console
    from rich.text import Text
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: Rich library not available. Install with: pip install rich")

@dataclass
class DecodeJob:
    """Represents a single processing job (VHS decode, TBC export, etc.)"""
    job_id: int
    job_type: str  # "VHS-Decode", "TBC-Export", "Audio-Align", etc.
    input_file: str
    output_file: str
    video_standard: str = ""
    tape_speed: str = ""
    additional_params: str = ""
    
    # Progress tracking
    total_frames: int = 0
    current_frame: int = 0
    current_fps: float = 0.0
    status: str = "Queued"  # Queued -> Starting -> Running -> Completed/Failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    process: Optional[subprocess.Popen] = None
    
    # Real-time FPS calculation (30-60 second rolling window)
    frame_timestamps: list = field(default_factory=list)  # Store recent frame updates
    calculation_window_seconds: int = 45  # Configurable window size
    
    # UI state
    eta_seconds: int = 0
    progress_percent: float = 0.0
    runtime_seconds: int = 0
    
    # Legacy compatibility for VHS decode
    @property
    def rf_file(self):
        return self.input_file
    
    @property
    def tbc_file(self):
        return self.output_file

class ParallelVHSDecoder:
    """Manager for parallel VHS decode operations
    
    Supports scanning multiple processing locations configured via the settings menu.
    Processing locations are managed through: Settings → Manage Processing Locations
    """
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.jobs: List[DecodeJob] = []
        self.status_queue = Queue()
        self.manager = Manager()
        self.shared_data = self.manager.dict()
        self.running = False
        
    def get_frame_count_from_json(self, rf_file: str, video_standard: str) -> int:
        """Extract frame count from Domesday Duplicator JSON metadata"""
        json_file = rf_file.replace('.lds', '.json').replace('.ldf', '.json')
        
        if not os.path.exists(json_file):
            print(f"Warning: JSON metadata not found for {os.path.basename(rf_file)}")
            return 0
            
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract duration from JSON
            duration_ms = data['captureInfo']['durationInMilliseconds']
            duration_seconds = duration_ms / 1000.0
            
            # Calculate frame count based on video standard
            if video_standard.lower() == 'pal':
                frames = int(duration_seconds * 25.0)  # PAL: 25fps
            else:  # NTSC
                frames = int(duration_seconds * 29.97)  # NTSC: 29.97fps
                
            print(f"Calculated {frames:,} frames for {os.path.basename(rf_file)} ({video_standard})")
            return frames
            
        except Exception as e:
            print(f"Error reading JSON metadata: {e}")
            return 0
    
    def parse_decode_output(self, line: str) -> Tuple[Optional[int], Optional[float], Optional[str]]:
        """Parse VHS decode output for progress information"""
        current_frame = None
        fps = None
        status = None
        
        # Actual vhs-decode frame pattern: "File Frame 1000: VHS"
        frame_match = re.search(r'File Frame (\d+):', line, re.IGNORECASE)
        if frame_match:
            current_frame = int(frame_match.group(1))
            status = "Processing"
        
        # FPS appears only at completion: "(9.36 FPS post-setup)"
        fps_match = re.search(r'\(([0-9.]+)\s*fps\s*post-setup\)', line, re.IGNORECASE)
        if fps_match:
            fps = float(fps_match.group(1))
            status = "Completed"
        
        # Alternative FPS pattern: "Took X seconds to decode Y frames (Z.Z FPS"
        if fps is None:
            fps_alt_match = re.search(r'decode\s+\d+\s+frames\s*\(([0-9.]+)\s*fps', line, re.IGNORECASE)
            if fps_alt_match:
                fps = float(fps_alt_match.group(1))
        
        # Status detection for vhs-decode
        line_lower = line.lower()
        if 'file frame' in line_lower:
            status = "Processing"
        elif 'completed' in line_lower and 'saving' in line_lower:
            status = "Completed"
        elif 'error' in line_lower or 'failed' in line_lower:
            status = "Error"
        elif 'took' in line_lower and 'seconds' in line_lower:
            status = "Finalizing"
        
        return current_frame, fps, status
    
    def run_single_decode(self, job: DecodeJob, status_queue: Queue):
        """Run a single decode job in a separate process"""
        try:
            # Build vhs-decode command using same parameters as working single decode
            cmd = [
                'vhs-decode',
                '--tf', 'vhs',          # Format: VHS
                '-t', '3',              # Threads: 3
                '--ts', job.tape_speed, # Tape speed: SP/LP/EP
                '--no_resample',        # No resampling
                '--recheck_phase',      # Recheck phase
                '--ire0_adjust',        # IRE 0 adjust
            ]
            
            # Add video standard (PAL/NTSC)
            if job.video_standard.lower() == 'pal':
                cmd.append('--pal')
            else:  # NTSC
                cmd.append('--ntsc')
            
            # Add input and output files - output is base name without extension
            cmd.extend([
                job.rf_file,
                job.tbc_file.replace('.tbc', '')  # Output base name (without extension)
            ])
            
            # Add additional parameters if specified
            if job.additional_params:
                cmd.extend(job.additional_params.split())
            
            print(f"[Job {job.job_id}] Starting: {' '.join(cmd)}")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            job.process = process
            job.start_time = datetime.now()
            
            # Send initial status update
            status_queue.put({
                'job_id': job.job_id,
                'status': 'Running',
                'start_time': job.start_time
            })
            
            # Process output line by line
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                    
                line = line.strip()
                if not line:
                    continue
                    
                # Store all output for debugging
                output_lines.append(line)
                
                # Parse progress information
                current_frame, fps, status_text = self.parse_decode_output(line)
                
                # Send status update if we have new information
                if current_frame is not None or fps is not None or status_text is not None:
                    update = {'job_id': job.job_id}
                    
                    if current_frame is not None:
                        update['current_frame'] = current_frame
                    if fps is not None:
                        update['fps'] = fps
                    if status_text is not None:
                        update['status'] = status_text
                    
                    status_queue.put(update)
            
            # Wait for process completion
            process.wait()
            
            # If process failed, send error details
            if process.returncode != 0:
                error_msg = f"Exit code {process.returncode}"
                if output_lines:
                    # Send last few lines of output for debugging
                    last_lines = output_lines[-5:] if len(output_lines) > 5 else output_lines
                    error_msg += f": {'; '.join(last_lines)}"
                
                status_queue.put({
                    'job_id': job.job_id,
                    'error_details': error_msg,
                    'full_output': output_lines
                })
            
            # Send completion status
            status_queue.put({
                'job_id': job.job_id,
                'completed': True,
                'return_code': process.returncode,
                'end_time': datetime.now()
            })
            
        except Exception as e:
            status_queue.put({
                'job_id': job.job_id,
                'error': str(e),
                'end_time': datetime.now()
            })
    
    def calculate_realtime_fps(self, job: DecodeJob, new_frame: int) -> float:
        """Calculate real-time processing FPS based on frame progression"""
        current_time = datetime.now()
        
        # Add this frame update to our tracking list
        job.frame_timestamps.append((new_frame, current_time))
        
        # Keep only recent timestamps (last 30 seconds worth)
        cutoff_time = current_time - timedelta(seconds=30)
        job.frame_timestamps = [(frame, time) for frame, time in job.frame_timestamps if time > cutoff_time]
        
        # Need at least 2 data points to calculate speed
        if len(job.frame_timestamps) < 2:
            return 0.0
        
        # Calculate FPS using first and last timestamps
        first_frame, first_time = job.frame_timestamps[0]
        last_frame, last_time = job.frame_timestamps[-1]
        
        time_diff = (last_time - first_time).total_seconds()
        frame_diff = last_frame - first_frame
        
        if time_diff > 0 and frame_diff > 0:
            fps = frame_diff / time_diff
            return fps
        
        return 0.0
    
    def calculate_eta(self, job: DecodeJob) -> int:
        """Calculate ETA in seconds based on current progress"""
        if job.current_frame <= 0 or job.total_frames <= 0 or job.current_fps <= 0:
            return 0
            
        remaining_frames = job.total_frames - job.current_frame
        eta_seconds = remaining_frames / job.current_fps
        return int(eta_seconds)
    
    def update_job_stats(self, job: DecodeJob):
        """Update calculated statistics for a job"""
        if job.start_time:
            job.runtime_seconds = int((datetime.now() - job.start_time).total_seconds())
        
        if job.total_frames > 0 and job.current_frame > 0:
            job.progress_percent = (job.current_frame / job.total_frames) * 100
        else:
            job.progress_percent = 0.0
            
        job.eta_seconds = self.calculate_eta(job)
    
    def format_time(self, seconds: int) -> str:
        """Format seconds as human-readable time"""
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
    
    def create_progress_display(self) -> Layout:
        """Create the Rich progress display layout"""
        if not RICH_AVAILABLE:
            return None
            
        layout = Layout()
        
        # Create header - adapt to show mixed job types in future
        job_types = set(job.job_type for job in self.jobs)
        if len(job_types) == 1:
            header_text = Text(f"{list(job_types)[0]} Status", style="bold magenta")
        else:
            header_text = Text("Processing Status", style="bold magenta")
        header_text.append(f" ({len(self.jobs)} jobs)", style="cyan")
        
        # Create job table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Job", style="cyan", no_wrap=True, width=6)
        table.add_column("Type", style="magenta", no_wrap=True, width=12)  # New job type column
        table.add_column("File", style="white", no_wrap=True, width=18)
        table.add_column("Progress", width=26)
        table.add_column("Frame", style="yellow", width=15)
        table.add_column("Speed", style="green", width=8)
        table.add_column("ETA", style="magenta", width=8)
        table.add_column("Status", style="blue", width=12)
        
        for job in self.jobs:
            # Create progress bar
            if job.total_frames > 0:
                progress_chars = int(job.progress_percent / 4)  # 25 chars for 100%
                bar = "█" * progress_chars + "░" * (25 - progress_chars)
                progress_text = f"[{bar}] {job.progress_percent:.1f}%"
            else:
                progress_text = "Calculating..."
            
            # Format frame info
            if job.total_frames > 0:
                frame_text = f"{job.current_frame:,}/{job.total_frames:,}"
            else:
                frame_text = f"{job.current_frame:,}"
            
            # Add row to table
            table.add_row(
                f"Job {job.job_id}",
                job.job_type[:12],  # Job type column
                os.path.basename(job.input_file)[:18],  # Use input_file instead of rf_file
                progress_text,
                frame_text,
                f"{job.current_fps:.1f} fps" if job.current_fps > 0 else "-",
                self.format_time(job.eta_seconds),
                job.status[:12]
            )
        
        # Create summary stats
        running_jobs = len([j for j in self.jobs if j.status not in ['Completed', 'Failed']])
        completed_jobs = len([j for j in self.jobs if j.status == 'Completed'])
        failed_jobs = len([j for j in self.jobs if j.status == 'Failed'])
        
        summary = Text("Status: ", style="bold")
        summary.append(f"Running: {running_jobs} ", style="green")
        summary.append(f"Completed: {completed_jobs} ", style="blue")
        if failed_jobs > 0:
            summary.append(f"Failed: {failed_jobs} ", style="red")
        
        # Layout structure
        layout.split_column(
            Layout(Panel(header_text, border_style="blue"), size=3),
            Layout(Panel(table, title="Job Details", border_style="cyan")),
            Layout(Panel(summary, title="Summary", border_style="green"), size=3)
        )
        
        return layout
    
    def process_status_updates(self):
        """Process status updates from decode jobs"""
        while self.running:
            try:
                # Get updates with timeout
                if not self.status_queue.empty():
                    update = self.status_queue.get_nowait()
                    job_id = update['job_id']
                    
                    # Find the job
                    job = None
                    for j in self.jobs:
                        if j.job_id == job_id:
                            job = j
                            break
                    
                    if job is None:
                        continue
                    
                    # Apply updates
                    if 'current_frame' in update:
                        job.current_frame = update['current_frame']
                        # Calculate real-time FPS based on frame progression
                        realtime_fps = self.calculate_realtime_fps(job, update['current_frame'])
                        if realtime_fps > 0:
                            job.current_fps = realtime_fps
                    if 'fps' in update:
                        # Use final FPS from vhs-decode if available (overrides calculated)
                        job.current_fps = update['fps']
                    if 'status' in update:
                        job.status = update['status']
                    if 'start_time' in update:
                        job.start_time = update['start_time']
                    if 'completed' in update:
                        if update['return_code'] == 0:
                            job.status = 'Completed'
                        else:
                            job.status = 'Failed'
                    if 'error' in update:
                        job.status = f'Error: {update["error"][:20]}'
                    
                    # Update calculated stats
                    self.update_job_stats(job)
                
                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                print(f"Error processing status update: {e}")
                time.sleep(0.5)
    
    def add_job(self, rf_file: str, video_standard: str, tape_speed: str, additional_params: str = ""):
        """Add a decode job to the queue"""
        job_id = len(self.jobs) + 1
        tbc_file = rf_file.replace('.lds', '.tbc').replace('.ldf', '.tbc')
        
        job = DecodeJob(
            job_id=job_id,
            job_type="VHS-Decode",  # Set job type
            input_file=rf_file,      # Use new field names
            output_file=tbc_file,    # Use new field names
            video_standard=video_standard,
            tape_speed=tape_speed,
            additional_params=additional_params
        )
        
        # Get frame count from JSON metadata
        job.total_frames = self.get_frame_count_from_json(rf_file, video_standard)
        
        self.jobs.append(job)
        print(f"Added Job {job_id}: {os.path.basename(rf_file)} -> {os.path.basename(tbc_file)}")
        
        return job
    
    def run_parallel_decode(self):
        """Run all decode jobs in parallel"""
        if not self.jobs:
            print("No jobs to run!")
            return
        
        print(f"Starting {len(self.jobs)} parallel decode jobs...")
        
        # Start status update processor
        self.running = True
        status_thread = threading.Thread(target=self.process_status_updates)
        status_thread.daemon = True
        status_thread.start()
        
        # Start all decode processes
        processes = []
        for job in self.jobs:
            p = Process(target=self.run_single_decode, args=(job, self.status_queue))
            p.start()
            processes.append(p)
        
        # Display progress using Rich if available
        if RICH_AVAILABLE:
            try:
                with Live(self.create_progress_display(), refresh_per_second=2) as live:
                    while any(p.is_alive() for p in processes):
                        live.update(self.create_progress_display())
                        time.sleep(0.5)
                        
                        # Check for keyboard interrupt
                        try:
                            # This allows Ctrl+C to work
                            pass
                        except KeyboardInterrupt:
                            print("\nStopping all decode jobs...")
                            for p in processes:
                                p.terminate()
                            break
                    
                    # Final display update
                    live.update(self.create_progress_display())
                    
            except KeyboardInterrupt:
                print("\nStopping all decode jobs...")
                for p in processes:
                    p.terminate()
        else:
            # Fallback simple display without Rich
            try:
                while any(p.is_alive() for p in processes):
                    print("\n=== VHS Decode Status ===")
                    for job in self.jobs:
                        if job.total_frames > 0:
                            percent = (job.current_frame / job.total_frames) * 100
                            print(f"Job {job.job_id}: {percent:.1f}% ({job.current_frame:,}/{job.total_frames:,}) "
                                  f"@ {job.current_fps:.1f}fps - {job.status}")
                        else:
                            print(f"Job {job.job_id}: {job.current_frame:,} frames @ {job.current_fps:.1f}fps - {job.status}")
                    time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopping all decode jobs...")
                for p in processes:
                    p.terminate()
        
        # Wait for all processes to complete
        for p in processes:
            p.join()
        
        self.running = False
        
        # Final summary
        print("\n=== DECODE SUMMARY ===")
        completed = 0
        failed = 0
        for job in self.jobs:
            if job.status == 'Completed':
                completed += 1
                print(f"✓ Job {job.job_id}: {os.path.basename(job.rf_file)} - COMPLETED")
            elif job.status == 'Failed' or 'Error' in job.status:
                failed += 1
                print(f"✗ Job {job.job_id}: {os.path.basename(job.rf_file)} - FAILED")
            else:
                print(f"? Job {job.job_id}: {os.path.basename(job.rf_file)} - {job.status}")
        
        print(f"\nResults: {completed} completed, {failed} failed out of {len(self.jobs)} total jobs")
        
        return completed == len(self.jobs)  # Return True if all jobs completed successfully
    
    def get_processing_locations(self) -> List[str]:
        """Get all configured processing locations from config"""
        try:
            # Import config functions
            from config import load_config
            
            config = load_config()
            processing_locations = config.get('processing_locations', [])
            
            # Always include current capture directory as fallback
            from config import get_capture_directory
            capture_dir = get_capture_directory()
            
            if capture_dir not in processing_locations:
                processing_locations.append(capture_dir)
            
            # Filter to only existing directories
            existing_locations = []
            for location in processing_locations:
                if os.path.exists(location):
                    existing_locations.append(location)
                else:
                    print(f"Warning: Processing location not found: {location}")
            
            return existing_locations
            
        except Exception as e:
            print(f"Warning: Could not load processing locations: {e}")
            # Fallback to capture directory only
            try:
                from config import get_capture_directory
                return [get_capture_directory()]
            except:
                return []
    
    def scan_all_locations_for_rf_files(self) -> List[Dict[str, str]]:
        """Scan all processing locations for RF files and return file info
        
        Returns:
            List of dictionaries with keys: 'rf_file', 'location', 'basename'
        """
        rf_files = []
        processing_locations = self.get_processing_locations()
        
        print(f"Scanning {len(processing_locations)} processing locations for RF files...")
        
        for location in processing_locations:
            try:
                print(f"  Scanning: {location}")
                location_files = []
                
                # Get all .lds and .ldf files in this location
                for ext in ['.lds', '.ldf']:
                    pattern = os.path.join(location, f"*{ext}")
                    import glob
                    location_files.extend(glob.glob(pattern))
                
                # Add to results with location info
                for rf_file in location_files:
                    rf_files.append({
                        'rf_file': rf_file,
                        'location': location,
                        'basename': os.path.basename(rf_file)
                    })
                
                print(f"    Found {len(location_files)} RF files")
                
            except Exception as e:
                print(f"    Error scanning {location}: {e}")
        
        print(f"Total RF files found: {len(rf_files)}")
        return rf_files
    
    def display_processing_locations_summary(self) -> str:
        """Get formatted summary of processing locations and file counts"""
        try:
            processing_locations = self.get_processing_locations()
            lines = [
                "PROCESSING LOCATIONS SCAN RESULTS",
                "=" * 50
            ]
            
            if not processing_locations:
                lines.append("No processing locations configured or accessible.")
                return "\n".join(lines)
            
            total_rf_files = 0
            
            for i, location in enumerate(processing_locations, 1):
                lines.append(f"\n{i}. {location}")
                
                # Count files in this location
                try:
                    rf_count = 0
                    for ext in ['.lds', '.ldf']:
                        pattern = os.path.join(location, f"*{ext}")
                        import glob
                        rf_count += len(glob.glob(pattern))
                    
                    json_count = len(glob.glob(os.path.join(location, "*.json")))
                    tbc_count = len(glob.glob(os.path.join(location, "*.tbc")))
                    
                    lines.append(f"   RF files: {rf_count} (.lds/.ldf)")
                    lines.append(f"   Metadata: {json_count} (.json)")
                    lines.append(f"   TBC files: {tbc_count} (.tbc)")
                    
                    total_rf_files += rf_count
                    
                    # Check disk space
                    try:
                        if sys.platform == 'win32':
                            import shutil
                            total, used, free = shutil.disk_usage(location)
                            free_gb = free / (1024**3)
                        else:
                            statvfs = os.statvfs(location)
                            free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
                        lines.append(f"   Free space: {free_gb:.1f} GB")
                    except:
                        lines.append("   Free space: Unknown")
                    
                except Exception as e:
                    lines.append(f"   Error reading location: {e}")
            
            lines.append(f"\nTOTAL: {total_rf_files} RF files across {len(processing_locations)} locations")
            lines.append(f"")
            lines.append(f"Note: Configure locations via Settings → Manage Processing Locations")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error generating processing locations summary: {e}"


def run_parallel_decode(jobs_list, max_workers=2):
    """Wrapper function for menu integration
    
    Args:
        jobs_list: List of job dictionaries with keys:
            - 'rf_file': Path to RF file
            - 'video_standard': 'pal' or 'ntsc' 
            - 'tape_speed': 'SP', 'LP', or 'EP'
            - 'additional_params': Optional additional parameters string
        max_workers: Maximum number of parallel decode jobs
    
    Returns:
        bool: True if all jobs completed successfully
    """
    if not jobs_list:
        print("No jobs provided for parallel decode")
        return False
    
    print(f"Setting up {len(jobs_list)} parallel decode jobs (max {max_workers} concurrent)...")
    
    # Create decoder instance
    decoder = ParallelVHSDecoder()
    
    # Process jobs in batches based on max_workers
    all_successful = True
    
    for i in range(0, len(jobs_list), max_workers):
        batch = jobs_list[i:i + max_workers]
        decoder.jobs = []  # Clear previous jobs
        
        print(f"\nProcessing batch {i//max_workers + 1}: {len(batch)} jobs")
        
        # Add jobs to decoder
        for job_dict in batch:
            decoder.add_job(
                rf_file=job_dict['rf_file'],
                video_standard=job_dict['video_standard'],
                tape_speed=job_dict['tape_speed'],
                additional_params=job_dict.get('additional_params', '')
            )
        
        # Run this batch
        batch_success = decoder.run_parallel_decode()
        if not batch_success:
            all_successful = False
            print(f"Warning: Some jobs in batch {i//max_workers + 1} failed")
    
    return all_successful


def main():
    """Interactive main function for testing"""
    print("Parallel VHS Decode Manager")
    print("=" * 40)
    
    if not RICH_AVAILABLE:
        print("Warning: Rich library not available for fancy display")
        print("Install with: pip install rich")
        print()
    
    decoder = ParallelVHSDecoder()
    
    # Show processing locations summary
    print(decoder.display_processing_locations_summary())
    print()
    
    # Scan all configured processing locations for RF files
    rf_file_info = decoder.scan_all_locations_for_rf_files()
    
    if rf_file_info:
        print(f"\nFound RF files across all processing locations:")
        # Group by location for display
        by_location = {}
        for info in rf_file_info:
            location = info['location']
            if location not in by_location:
                by_location[location] = []
            by_location[location].append(info)
        
        for location, files in by_location.items():
            print(f"\n  {location}: ({len(files)} files)")
            for i, info in enumerate(files[:3], 1):  # Show first 3 per location
                print(f"    {i}. {info['basename']}")
            if len(files) > 3:
                print(f"    ... and {len(files) - 3} more files")
        
        # Add first few RF files as example jobs
        print(f"\nAdding first 3 RF files as example decode jobs:")
        for i, info in enumerate(rf_file_info[:3], 1):
            print(f"  Adding {info['basename']} from {os.path.basename(info['location'])}")
            decoder.add_job(info['rf_file'], 'PAL', 'SP', '--dod-threshold 0.8')
        
        if decoder.jobs:
            print(f"\nStarting parallel decode of {len(decoder.jobs)} job(s)...")
            print("Press Ctrl+C to stop all jobs")
            decoder.run_parallel_decode()
    else:
        print("\nNo RF files found in any configured processing locations.")
        print("\nTo add processing locations:")
        print("  1. Run the main menu: python ddd_main_menu.py")
        print("  2. Go to Settings → Manage Processing Locations")
        print("  3. Add directories containing your RF (.lds/.ldf) files")
        return

if __name__ == '__main__':
    main()
