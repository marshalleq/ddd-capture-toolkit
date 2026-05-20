#!/usr/bin/env python3
"""
Job Queue Manager
Manages background processing jobs with persistent queue and configurable concurrency
"""

import os
import sys
import json
import time
import threading
import queue
import signal
import subprocess
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum
import pickle
import logging

# Import the existing parallel decode system
try:
    from parallel_vhs_decode import DecodeJob, ParallelVHSDecoder
    PARALLEL_DECODE_AVAILABLE = True
except ImportError:
    print("Warning: parallel_vhs_decode module not found")
    DecodeJob = None
    ParallelVHSDecoder = None
    PARALLEL_DECODE_AVAILABLE = False

# Import project flags manager for export flags
try:
    from project_flags import ProjectFlagsManager
    PROJECT_FLAGS_AVAILABLE = True
except ImportError:
    ProjectFlagsManager = None
    PROJECT_FLAGS_AVAILABLE = False

class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Job scheduling categories based on I/O characteristics
# Heavy I/O jobs saturate disk bandwidth and should not run concurrently on same storage
HEAVY_IO_JOBS = {"tbc-export", "final-mux"}
# Light jobs are algorithm-bound with low I/O, can run many in parallel
LIGHT_JOBS = {"vhs-decode", "lds-compress", "audio-align"}

# Storage type classification for scheduling rules
# Maps location names to storage type
STORAGE_TYPES = {
    "hdd1bpool": "hdd",
    "intel1tb": "ssd",
    "nvme2tb": "ssd",  # Treat NVMe same as SSD for scheduling
}

# Scheduling limits per storage type
# Format: {storage_type: {scenario: {job_category: max_concurrent}}}
# Based on benchmark data:
#   - HDD: 4 decodes @ 4.0 FPS each = 16 FPS total throughput
#   - SSD: decode uses ~9% disk utilization each
SCHEDULING_RULES = {
    "hdd": {
        # HDD: 4 parallel decodes gives best total throughput (~16 FPS)
        # When heavy I/O job running: allow 2 light jobs
        "heavy_running": {"light": 2, "heavy": 0},
        # When no heavy I/O: 4 light jobs, 1 heavy
        "normal": {"light": 4, "heavy": 1},
    },
    "ssd": {
        # SSDs handle concurrent I/O much better (~9% util per decode)
        "heavy_running": {"light": 4, "heavy": 0},
        "normal": {"light": 8, "heavy": 1},
    },
    # Default for unknown storage (conservative, same as HDD)
    "default": {
        "heavy_running": {"light": 2, "heavy": 0},
        "normal": {"light": 4, "heavy": 1},
    },
}


@dataclass
class QueuedJob:
    """Represents a job in the queue with metadata"""
    job_id: str
    job_type: str  # "vhs-decode", "tbc-export", "audio-align", etc.
    input_file: str
    output_file: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 1  # Higher numbers = higher priority
    progress: float = 0.0  # 0-100
    error_message: str = ""
    project_name: str = "Unknown"  # Project name for workflow tracking
    status_message: str = ""  # Current operation status (e.g., "Preparing reverse field order...")

    # Progress tracking fields for real-time monitoring
    total_frames: int = 0
    current_frame: int = 0
    current_fps: float = 0.0

    # Location tracking for per-disk concurrency limits
    source_location: str = ""  # Pool/disk name for input file (e.g., "hdd1bpool", "nvme2tb")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialisation"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary for JSON deserialisation"""
        data['status'] = JobStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data['started_at']:
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data['completed_at']:
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        
        # Handle missing progress tracking fields for backward compatibility
        data.setdefault('total_frames', 0)
        data.setdefault('current_frame', 0)
        data.setdefault('current_fps', 0.0)

        # Handle missing location field for backward compatibility
        data.setdefault('source_location', '')

        return cls(**data)

class JobQueueManager:
    """Manages a persistent job queue with background processing"""
    
    def __init__(self, queue_file="config/job_queue.json", max_concurrent_jobs=2):
        self.queue_file = queue_file
        self.max_concurrent_jobs = max_concurrent_jobs
        self.per_location_limits: Dict[str, int] = {}  # Per-disk concurrency limits
        self.jobs: List[QueuedJob] = []
        self.running_jobs: Dict[str, threading.Thread] = {}
        self.job_processes: Dict[str, subprocess.Popen] = {}  # Track active processes
        self.lock = threading.Lock()
        self.stop_processing = False
        self.processor_thread = None
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        
        # Setup logging first
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=f"{log_dir}/job_queue.log",
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load existing queue after logger is set up
        self.load_queue()

    def get_location_from_path(self, file_path: str) -> str:
        """
        Determine which location/pool a file path belongs to.

        Parses mount points to map paths like:
        - /mnt/hdd1bpool/captures/... -> "hdd1bpool"
        - /mnt/nvme2tb/captures/... -> "nvme2tb"
        - /mnt/intel1tb/captures/... -> "intel1tb"

        Returns empty string if path doesn't match /mnt/X/ pattern.
        """
        if not file_path:
            return ""

        # Handle /mnt/LOCATION/... pattern
        if file_path.startswith('/mnt/'):
            parts = file_path.split('/')
            if len(parts) >= 3:
                return parts[2]  # /mnt/LOCATION/...

        return ""

    def get_location_limit(self, location: str) -> int:
        """Get max concurrent jobs for a location (default: no specific limit)"""
        if not location:
            return self.max_concurrent_jobs  # No limit for unknown locations
        return self.per_location_limits.get(location, self.max_concurrent_jobs)

    def set_location_limit(self, location: str, limit: int):
        """Set max concurrent jobs for a specific location"""
        if limit <= 0:
            # Remove limit (use global)
            self.per_location_limits.pop(location, None)
        else:
            self.per_location_limits[location] = limit
        self.save_queue()
        self.logger.info(f"Set location limit for {location}: {limit}")

    def get_all_location_limits(self) -> Dict[str, int]:
        """Get all configured per-location limits"""
        return self.per_location_limits.copy()

    def get_storage_type(self, location: str) -> str:
        """Get storage type (hdd/ssd) for a location"""
        return STORAGE_TYPES.get(location, "default")

    def get_job_category(self, job_type: str) -> str:
        """Get job category (heavy/light) for scheduling"""
        if job_type in HEAVY_IO_JOBS:
            return "heavy"
        return "light"

    def can_schedule_job(self, job: 'QueuedJob', running_jobs: List['QueuedJob']) -> bool:
        """
        Determine if a job can be scheduled based on storage-aware rules.

        Rules:
        - Heavy I/O jobs (export, final-mux) block other heavy jobs on same storage
        - Light jobs (decode, compress, align) can run with limits
        - Different storage types have different limits (HDD more constrained than SSD)
        """
        location = job.source_location or self.get_location_from_path(job.input_file)
        if not location:
            # Unknown location - use global limit
            return len(running_jobs) < self.max_concurrent_jobs

        storage_type = self.get_storage_type(location)
        job_category = self.get_job_category(job.job_type)
        rules = SCHEDULING_RULES.get(storage_type, SCHEDULING_RULES["default"])

        # Count running jobs on same location by category
        location_jobs = [j for j in running_jobs
                        if (j.source_location or self.get_location_from_path(j.input_file)) == location]

        heavy_running = sum(1 for j in location_jobs if self.get_job_category(j.job_type) == "heavy")
        light_running = sum(1 for j in location_jobs if self.get_job_category(j.job_type) == "light")

        # Select scenario based on whether heavy I/O is running
        scenario = "heavy_running" if heavy_running > 0 else "normal"
        limits = rules[scenario]

        # Check if we can add this job
        if job_category == "heavy":
            return heavy_running < limits["heavy"]
        else:
            return light_running < limits["light"]

    def get_scheduling_status(self) -> Dict[str, Any]:
        """Get current scheduling status for display/debugging"""
        with self.lock:
            running_jobs = [j for j in self.jobs if j.status == JobStatus.RUNNING]
            queued_jobs = [j for j in self.jobs if j.status == JobStatus.QUEUED]

        # Group by location
        status = {}
        locations = set()
        for job in running_jobs + queued_jobs:
            loc = job.source_location or self.get_location_from_path(job.input_file)
            if loc:
                locations.add(loc)

        for loc in locations:
            loc_running = [j for j in running_jobs
                         if (j.source_location or self.get_location_from_path(j.input_file)) == loc]
            loc_queued = [j for j in queued_jobs
                        if (j.source_location or self.get_location_from_path(j.input_file)) == loc]

            heavy_running = sum(1 for j in loc_running if self.get_job_category(j.job_type) == "heavy")
            light_running = sum(1 for j in loc_running if self.get_job_category(j.job_type) == "light")

            storage_type = self.get_storage_type(loc)
            scenario = "heavy_running" if heavy_running > 0 else "normal"
            rules = SCHEDULING_RULES.get(storage_type, SCHEDULING_RULES["default"])
            limits = rules[scenario]

            status[loc] = {
                "storage_type": storage_type,
                "scenario": scenario,
                "heavy_running": heavy_running,
                "light_running": light_running,
                "heavy_limit": limits["heavy"],
                "light_limit": limits["light"],
                "queued_count": len(loc_queued),
                "running_jobs": [{"id": j.job_id, "type": j.job_type} for j in loc_running],
            }

        return status

    def start_processor(self):
        """Start the background job processor"""
        if self.processor_thread and self.processor_thread.is_alive():
            return  # Already running
        
        self.stop_processing = False
        self.processor_thread = threading.Thread(target=self._process_jobs, daemon=True)
        self.processor_thread.start()
        self.logger.info("Job processor started")
    
    def stop_processor(self):
        """Stop the background job processor"""
        self.stop_processing = True
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        self.logger.info("Job processor stopped")
    
    def add_job(self, job_type: str, input_file: str, output_file: str,
                parameters: Dict[str, Any] = None, priority: int = 1) -> str:
        """Add a new job to the queue"""
        if parameters is None:
            parameters = {}

        job_id = f"{job_type}_{int(time.time())}_{len(self.jobs)}"
        source_location = self.get_location_from_path(input_file)

        job = QueuedJob(
            job_id=job_id,
            job_type=job_type,
            input_file=input_file,
            output_file=output_file,
            parameters=parameters,
            priority=priority,
            source_location=source_location
        )
        
        with self.lock:
            self.jobs.append(job)
            # Sort by priority (higher priority first) then by created time
            self.jobs.sort(key=lambda j: (-j.priority, j.created_at))
        
        self.save_queue()
        self.logger.info(f"Added job {job_id}: {job_type} - {input_file}")
        
        return job_id
    
    def add_job_nonblocking(self, job_type: str, input_file: str, output_file: str, 
                            parameters: Dict[str, Any] = None, priority: int = 1, timeout: float = 0.5, project_name: str = "Unknown") -> Optional[str]:
        """Add a new job to the queue with timeout to avoid blocking UI"""
        if parameters is None:
            parameters = {}
        
        try:
            # Try to acquire lock with timeout
            if self.lock.acquire(timeout=timeout):
                try:
                    job_id = f"{job_type}_{int(time.time())}_{len(self.jobs)}"
                    source_location = self.get_location_from_path(input_file)

                    job = QueuedJob(
                        job_id=job_id,
                        job_type=job_type,
                        input_file=input_file,
                        output_file=output_file,
                        parameters=parameters,
                        priority=priority,
                        project_name=project_name,
                        source_location=source_location
                    )
                    
                    self.jobs.append(job)
                    # Sort by priority (higher priority first) then by created time
                    self.jobs.sort(key=lambda j: (-j.priority, j.created_at))
                    
                    # Save queue without holding lock too long
                    jobs_copy = self.jobs.copy()
                finally:
                    self.lock.release()
                
                # Save queue after releasing lock to minimize lock time
                try:
                    self._save_queue_data(jobs_copy)
                    self.logger.info(f"Added job {job_id}: {job_type} - {input_file}")
                    return job_id
                except Exception as e:
                    self.logger.error(f"Error saving queue after adding job: {e}")
                    return job_id  # Job was added, just saving failed
            else:
                # Timeout occurred - return None to indicate failure
                return None
        except Exception as e:
            self.logger.error(f"Error in add_job_nonblocking: {e}")
            return None
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue (only if not running)"""
        with self.lock:
            for i, job in enumerate(self.jobs):
                if job.job_id == job_id:
                    if job.status == JobStatus.RUNNING:
                        return False  # Cannot remove running job

                    del self.jobs[i]
                    self.save_queue()
                    self.logger.info(f"Removed job {job_id}")
                    return True
        return False

    def remove_jobs_by_status(self, statuses) -> int:
        """Remove all jobs whose status is in `statuses`.

        Active jobs (QUEUED, RUNNING) are never affected unless explicitly
        included. Returns the number of jobs removed.
        """
        status_set = set(statuses)
        with self.lock:
            before = len(self.jobs)
            # Never remove RUNNING jobs even if asked, as a safety net.
            self.jobs = [
                j for j in self.jobs
                if not (j.status in status_set and j.status != JobStatus.RUNNING)
            ]
            removed = before - len(self.jobs)
            if removed:
                self.save_queue()
                self.logger.info(
                    f"Removed {removed} job(s) with status in "
                    f"{[s.value for s in status_set]}"
                )
            return removed
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (mark as cancelled, stop if running)"""
        with self.lock:
            for job in self.jobs:
                if job.job_id == job_id:
                    if job.status == JobStatus.RUNNING:
                        # Terminate the running process
                        success = self._terminate_job_process(job_id)
                        job.status = JobStatus.CANCELLED
                        job.completed_at = datetime.now()
                        job.error_message = "Job cancelled by user"
                        self.logger.info(f"Cancelled running job {job_id} (process terminated: {success})")
                    elif job.status == JobStatus.QUEUED:
                        job.status = JobStatus.CANCELLED
                        job.completed_at = datetime.now()
                        job.error_message = "Job cancelled by user"
                        self.logger.info(f"Cancelled queued job {job_id}")
                    else:
                        return False  # Already completed/failed
                    
                    self.save_queue()
                    return True
        return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        with self.lock:
            queued = len([j for j in self.jobs if j.status == JobStatus.QUEUED])
            running = len([j for j in self.jobs if j.status == JobStatus.RUNNING])
            completed = len([j for j in self.jobs if j.status == JobStatus.COMPLETED])
            failed = len([j for j in self.jobs if j.status == JobStatus.FAILED])
            cancelled = len([j for j in self.jobs if j.status == JobStatus.CANCELLED])
            
            return {
                "total_jobs": len(self.jobs),
                "queued": queued,
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "max_concurrent": self.max_concurrent_jobs,
                "processor_running": not self.stop_processing
            }
    
    def get_queue_status_nonblocking(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """Get queue status with timeout to avoid blocking UI"""
        try:
            # Try to acquire lock with timeout
            if self.lock.acquire(timeout=timeout):
                try:
                    queued = len([j for j in self.jobs if j.status == JobStatus.QUEUED])
                    running = len([j for j in self.jobs if j.status == JobStatus.RUNNING])
                    completed = len([j for j in self.jobs if j.status == JobStatus.COMPLETED])
                    failed = len([j for j in self.jobs if j.status == JobStatus.FAILED])
                    cancelled = len([j for j in self.jobs if j.status == JobStatus.CANCELLED])
                    
                    return {
                        "total_jobs": len(self.jobs),
                        "queued": queued,
                        "running": running,
                        "completed": completed,
                        "failed": failed,
                        "cancelled": cancelled,
                        "max_concurrent": self.max_concurrent_jobs,
                        "processor_running": not self.stop_processing
                    }
                finally:
                    self.lock.release()
            else:
                # Timeout occurred - return None to indicate unavailable
                return None
        except Exception:
            return None
    
    def get_jobs(self, status_filter: Optional[JobStatus] = None) -> List[QueuedJob]:
        """Get all jobs, optionally filtered by status"""
        with self.lock:
            if status_filter:
                return [j for j in self.jobs if j.status == status_filter]
            return self.jobs.copy()
    
    def get_jobs_nonblocking(self, status_filter: Optional[JobStatus] = None, timeout: float = 0.1) -> Optional[List[QueuedJob]]:
        """Get all jobs with timeout to avoid blocking UI"""
        try:
            # Try to acquire lock with timeout
            if self.lock.acquire(timeout=timeout):
                try:
                    if status_filter:
                        return [j for j in self.jobs if j.status == status_filter]
                    return self.jobs.copy()
                finally:
                    self.lock.release()
            else:
                # Timeout occurred - return None to indicate unavailable
                return None
        except Exception:
            return None
    
    def set_max_concurrent_jobs(self, max_jobs: int):
        """Set maximum concurrent jobs"""
        self.max_concurrent_jobs = max(1, min(max_jobs, 8))  # Limit between 1-8
        self.save_queue()
        self.logger.info(f"Set max concurrent jobs to {self.max_concurrent_jobs}")
    
    def _process_jobs(self):
        """Background job processor thread with storage-aware scheduling"""
        while not self.stop_processing:
            try:
                # Check if we can start more jobs
                with self.lock:
                    running_jobs = [j for j in self.jobs if j.status == JobStatus.RUNNING]
                    running_count = len(running_jobs)
                    available_slots = self.max_concurrent_jobs - running_count

                    # Try to start multiple jobs if slots available
                    jobs_started = 0
                    while available_slots > 0:
                        # Find next queued job that can be scheduled
                        # Use storage-aware scheduling rules
                        next_job = None
                        for job in self.jobs:
                            if job.status != JobStatus.QUEUED:
                                continue

                            # Use smart scheduling based on job type and storage
                            if self.can_schedule_job(job, running_jobs):
                                next_job = job
                                break

                        if not next_job:
                            break  # No eligible jobs

                        # Start the job
                        next_job.status = JobStatus.RUNNING
                        next_job.started_at = datetime.now()
                        running_jobs.append(next_job)  # Add to running list for next iteration
                        available_slots -= 1
                        jobs_started += 1

                        # Start job in separate thread
                        job_thread = threading.Thread(
                            target=self._execute_job,
                            args=(next_job,),
                            daemon=True
                        )
                        job_thread.start()
                        self.running_jobs[next_job.job_id] = job_thread

                        loc = next_job.source_location or self.get_location_from_path(next_job.input_file)
                        category = self.get_job_category(next_job.job_type)
                        self.logger.info(f"Started job {next_job.job_id} ({next_job.job_type}/{category}) on {loc or 'unknown'}")

                    if jobs_started > 0:
                        self.save_queue()
                
                # Clean up completed threads
                completed_jobs = []
                for job_id, thread in list(self.running_jobs.items()):
                    if not thread.is_alive():
                        completed_jobs.append(job_id)
                
                for job_id in completed_jobs:
                    del self.running_jobs[job_id]
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error in job processor: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _execute_job(self, job: QueuedJob):
        """Execute a single job"""
        try:
            self.logger.info(f"Executing job {job.job_id}: {job.job_type}")
            
            if job.job_type == "vhs-decode":
                success = self._execute_vhs_decode_job(job)
            elif job.job_type == "tbc-export":
                success = self._execute_tbc_export_job(job)
            elif job.job_type == "audio-align":
                success = self._execute_audio_align_job(job)
            elif job.job_type == "final-mux":
                success = self._execute_final_mux_job(job)
            elif job.job_type == "lds-compress":
                success = self._execute_lds_compress_job(job)
            else:
                self.logger.error(f"Unknown job type: {job.job_type}")
                success = False
            
            with self.lock:
                # Don't overwrite CANCELLED status - respect user cancellation
                if job.status == JobStatus.CANCELLED:
                    self.logger.info(f"Job {job.job_id} was cancelled by user")
                elif success:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                    self.logger.info(f"Job {job.job_id} completed successfully")
                else:
                    job.status = JobStatus.FAILED
                    self.logger.error(f"Job {job.job_id} failed")

                job.completed_at = datetime.now()
                # Use async save to avoid blocking job completion
                self._save_queue_async()
        
        except Exception as e:
            self.logger.error(f"Error executing job {job.job_id}: {e}")
            with self.lock:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now()
                # Use async save to avoid blocking on error handling
                self._save_queue_async()
    
    def _execute_vhs_decode_job(self, job: QueuedJob) -> bool:
        """Execute a VHS decode job"""
        try:
            # Get total frame count from JSON metadata first
            if PARALLEL_DECODE_AVAILABLE:
                decoder_helper = ParallelVHSDecoder()
                total_frames = decoder_helper.get_frame_count_from_json(
                    job.input_file,
                    job.parameters.get('video_standard', 'pal')
                )
            else:
                total_frames = 0

            # Store total_frames on job object for progress display
            with self.lock:
                job.total_frames = total_frames
                self.logger.info(f"VHS decode total frames from capture JSON: {total_frames}")

            # Find vhs-decode command - check PATH first (installed version), then submodule
            import shutil
            script_dir = os.path.dirname(os.path.abspath(__file__))

            vhs_decode_cmd = None
            # First check if installed in PATH (via pip install)
            if shutil.which('vhs-decode'):
                vhs_decode_cmd = 'vhs-decode'
            else:
                # Fall back to submodule script
                submodule_path = os.path.join(script_dir, 'external', 'vhs-decode', 'vhs-decode')
                if os.path.exists(submodule_path):
                    vhs_decode_cmd = submodule_path

            if not vhs_decode_cmd:
                self.logger.error("vhs-decode not found in PATH or external/vhs-decode/")
                job.error_message = "vhs-decode not found. Run setup.sh to install it."
                return False

            # Build vhs-decode command
            cmd = [
                vhs_decode_cmd,
                '--tf', 'vhs',
                '-t', '3',
                '--ts', job.parameters.get('tape_speed', 'SP'),
            ]

            # Add video standard
            if job.parameters.get('video_standard', 'pal').lower() == 'pal':
                cmd.append('--pal')
            else:
                cmd.append('--ntsc')

            # Add per-project decode flags (includes defaults like --no_resample, --recheck_phase, --ire0_adjust)
            if PROJECT_FLAGS_AVAILABLE and job.project_name:
                flags_manager = ProjectFlagsManager()
                cli_flags = flags_manager.get_cli_flags(job.project_name, 'decode')
                if cli_flags:
                    cmd.extend(cli_flags)
                    self.logger.info(f"Added project decode flags: {' '.join(cli_flags)}")
            else:
                # Fallback if project flags not available - use hardcoded defaults
                cmd.extend(['--no_resample', '--recheck_phase', '--ire0_adjust'])

            # Check for segment configuration (for testing partial decodes)
            # segment_start_frame is used later for progress calculation
            segment_start_frame = 0
            try:
                from segment_config import load_segment_config
                segment_config = load_segment_config(job.project_name)
                if segment_config and segment_config.get('enabled', False):
                    video_standard = job.parameters.get('video_standard', 'pal').lower()
                    if video_standard == 'pal':
                        segment_start_frame = segment_config.get('start_frame_pal', 0)
                        frame_count = segment_config.get('frame_count_pal', 0)
                    else:
                        segment_start_frame = segment_config.get('start_frame_ntsc', 0)
                        frame_count = segment_config.get('frame_count_ntsc', 0)

                    if segment_start_frame >= 0 and frame_count > 0:
                        cmd.extend(['-s', str(segment_start_frame), '-l', str(frame_count)])
                        self.logger.info(f"Segment mode: start={segment_start_frame}, length={frame_count} ({video_standard.upper()})")
                        # Update total_frames to segment frame count for accurate ETA
                        # CRITICAL: Update both the job object AND the local variable
                        with self.lock:
                            job.total_frames = frame_count
                            self.save_queue()
                        total_frames = frame_count  # Update local variable for progress calculation
                        self.logger.info(f"Updated total_frames to segment count: {frame_count}")
            except ImportError:
                pass  # segment_config not available
            except Exception as e:
                self.logger.warning(f"Error checking segment config: {e}")

            # Add input and output
            cmd.extend([
                job.input_file,
                job.output_file.replace('.tbc', '')
            ])

            # Add additional parameters if specified
            additional_params = job.parameters.get('additional_params', '')
            if additional_params:
                cmd.extend(additional_params.split())
            
            self.logger.info(f"Starting VHS decode: {' '.join(cmd)}")
            
            # Start process. start_new_session puts the subprocess in its own
            # process group so _terminate_job_process can signal the whole group
            # without also killing the parent (which shares the controlling
            # terminal's group otherwise).
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True
            )

            # Track the process for termination capability
            self.job_processes[job.job_id] = process

            current_frame = 0
            start_time = time.time()  # Track start time for FPS calculation

            # Parse output for frame progress
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break

                line = line.strip()

                # Parse frame progress: "File Frame 1000: VHS"
                import re
                frame_match = re.search(r'File Frame (\d+):', line)
                if frame_match:
                    current_frame = int(frame_match.group(1))

                    # Calculate frames processed (relative to segment start for segment mode)
                    frames_processed = current_frame - segment_start_frame

                    # Calculate FPS based on elapsed time and frames actually processed
                    elapsed_time = time.time() - start_time
                    current_fps = frames_processed / elapsed_time if elapsed_time > 0 else 0

                    if total_frames > 0:
                        # Use frames_processed for accurate progress in segment mode
                        progress = (frames_processed / total_frames) * 100
                        # Update job progress with thread safety
                        with self.lock:
                            job.progress = min(progress, 99.9)  # Cap at 99.9% until completion
                            job.current_frame = frames_processed  # Store relative frame count
                            job.current_fps = current_fps
                            # Skip saving to disk to avoid blocking during job execution
                            # Final progress will be saved when job completes
                    else:
                        # No frame count available, show frame number as basic progress
                        with self.lock:
                            job.progress = min(frames_processed / 1000.0, 50.0)  # Very rough estimate
                            job.current_frame = frames_processed
                            job.current_fps = current_fps
            
            # Wait for completion
            return_code = process.wait()

            # Clean up process tracking
            if job.job_id in self.job_processes:
                del self.job_processes[job.job_id]

            # Check if the job actually succeeded by verifying output files exist
            # VHS decode produces both .tbc and .json files
            tbc_file = job.output_file
            json_file = job.output_file.replace('.tbc', '.json')
            
            tbc_exists = os.path.exists(tbc_file) and os.path.getsize(tbc_file) > 0
            json_exists = os.path.exists(json_file) and os.path.getsize(json_file) > 0
            output_files_exist = tbc_exists and json_exists
            
            # Set final progress
            with self.lock:
                if return_code == 0 and output_files_exist:
                    job.progress = 100.0
                    # Final save will be handled by _execute_job completion, not here
                    self.logger.info(f"VHS decode completed successfully: {tbc_file}, {json_file}")
                else:
                    if return_code != 0:
                        self.logger.error(f"VHS decode failed with return code {return_code}")
                    elif not output_files_exist:
                        missing_files = []
                        if not tbc_exists:
                            missing_files.append(tbc_file)
                        if not json_exists:
                            missing_files.append(json_file)
                        self.logger.error(f"VHS decode failed: output files not created or empty: {', '.join(missing_files)}")
            
            return return_code == 0 and output_files_exist
            
        except Exception as e:
            job.error_message = str(e)
            self.logger.error(f"VHS decode job error: {e}")
            return False
    
    def _get_total_frames_from_tbc_json(self, tbc_json_file: str) -> int:
        """Extract total frame count from TBC JSON metadata file"""
        try:
            if not os.path.exists(tbc_json_file):
                self.logger.warning(f"TBC JSON file not found: {tbc_json_file}")
                return 0
            
            with open(tbc_json_file, 'r') as f:
                data = json.load(f)
            
            # Count fields and divide by 2 to get frames (interlaced video has 2 fields per frame)
            if 'fields' in data:
                field_count = len(data['fields'])
                frame_count = int(field_count / 2)
                self.logger.info(f"TBC JSON metadata: {field_count} fields = {frame_count} frames")
                return frame_count
            else:
                self.logger.warning(f"No 'fields' data found in TBC JSON: {tbc_json_file}")
                return 0
                
        except Exception as e:
            self.logger.error(f"Error reading TBC JSON metadata {tbc_json_file}: {e}")
            return 0
    
    def _execute_tbc_export_job(self, job: QueuedJob) -> bool:
        """Execute a TBC export job"""
        try:
            self.logger.info(f"Starting TBC export: {job.input_file} -> {job.output_file}")

            # Find tbc-video-export command
            # Priority: 1) AppImage (easy mode), 2) conda env (performance mode), 3) PATH
            tbc_export_cmd = None
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # First check for AppImage (easy mode installation)
            appimage_path = os.path.join(script_dir, 'tools', 'tbc-video-export.AppImage')
            if os.path.exists(appimage_path) and os.access(appimage_path, os.X_OK):
                tbc_export_cmd = appimage_path
                self.logger.info(f"Using tbc-video-export AppImage: {appimage_path}")

            # If no AppImage, check conda environment (performance mode)
            if not tbc_export_cmd:
                conda_prefix = os.environ.get('CONDA_PREFIX')
                if conda_prefix:
                    conda_tbc_path = os.path.join(conda_prefix, 'bin', 'tbc-video-export')
                    if os.path.exists(conda_tbc_path):
                        tbc_export_cmd = conda_tbc_path
                        self.logger.info(f"Using conda tbc-video-export: {conda_tbc_path}")

            # If not found in conda, try common user paths
            if not tbc_export_cmd:
                user_local_path = os.path.expanduser('~/.local/bin/tbc-video-export')
                if os.path.exists(user_local_path):
                    tbc_export_cmd = user_local_path
                    self.logger.info(f"Using user-local tbc-video-export: {user_local_path}")

            # Fall back to PATH lookup
            if not tbc_export_cmd:
                import shutil
                if shutil.which('tbc-video-export'):
                    tbc_export_cmd = 'tbc-video-export'
                    self.logger.info("Using tbc-video-export from PATH")

            if not tbc_export_cmd:
                self.logger.error("tbc-video-export not found. Run setup.sh to install it.")
                job.error_message = "tbc-video-export not found. Run setup.sh to install it."
                return False
            
            # Build tbc-video-export command
            cmd = [
                tbc_export_cmd,
                '--threads', '0',  # Use all available threads
                '--profile', 'ffv1',  # Use FFV1 lossless codec
                '--show-process-output',  # Disable TUI and show raw FFmpeg output for progress parsing
            ]
            
            # Add overwrite flag if requested
            if job.parameters.get('overwrite', False):
                cmd.append('--overwrite')

            # Apply per-project segment config (time range) if enabled. tbc-video-export
            # uses the same -s / -l flags as vhs-decode. We pick PAL or NTSC frame counts
            # based on the .tbc.json's videoSystem field, since export jobs don't reliably
            # carry video_standard in their parameters.
            try:
                from segment_config import load_segment_config
                segment_config = load_segment_config(job.project_name) if job.project_name else None
                if segment_config and segment_config.get('enabled', False):
                    video_standard = 'pal'
                    candidate_json = job.input_file + '.json' if not job.input_file.endswith('.json') else job.input_file
                    if not os.path.exists(candidate_json) and job.input_file.endswith('.tbc'):
                        candidate_json = job.input_file[:-4] + '.tbc.json'
                    if os.path.exists(candidate_json):
                        try:
                            with open(candidate_json, 'r') as jf:
                                tbc_meta = json.load(jf)
                            vs = (tbc_meta.get('videoParameters', {}) or {}).get('system', '')
                            if isinstance(vs, str) and vs.upper().startswith('NTSC'):
                                video_standard = 'ntsc'
                        except Exception as e:
                            self.logger.debug(f"Could not parse video system from {candidate_json}: {e}")

                    if video_standard == 'pal':
                        seg_start = segment_config.get('start_frame_pal', 0)
                        seg_len = segment_config.get('frame_count_pal', 0)
                    else:
                        seg_start = segment_config.get('start_frame_ntsc', 0)
                        seg_len = segment_config.get('frame_count_ntsc', 0)

                    if seg_start >= 0 and seg_len > 0:
                        # tbc-video-export is 1-indexed for -s (errors out on 0);
                        # the segment config stores 0-indexed values matching vhs-decode.
                        tbc_start = seg_start + 1
                        cmd.extend(['-s', str(tbc_start), '-l', str(seg_len)])
                        self.logger.info(
                            f"Export segment mode: start={tbc_start} (1-indexed), length={seg_len} ({video_standard.upper()})"
                        )
                        with self.lock:
                            job.total_frames = seg_len
                            self.save_queue()
            except ImportError:
                pass
            except Exception as e:
                self.logger.warning(f"Error applying export segment config: {e}")

            # Add per-project export flags (e.g., --luma-only for B&W sources)
            # Also handle reverse field order specially - it requires pre-processing
            reverse_temp_file = None
            reverse_temp_json = None
            reverse_temp_chroma = None
            if PROJECT_FLAGS_AVAILABLE and job.project_name:
                flags_manager = ProjectFlagsManager()
                cli_flags = flags_manager.get_cli_flags(job.project_name)

                # Check if reverse field order is enabled - requires special handling
                if '--reverse' in cli_flags:
                    self.logger.info("Reverse field order enabled - pre-processing with ld-dropout-correct")

                    # Update status message to show we're in pre-processing phase
                    with self.lock:
                        job.status_message = "Preparing reverse field order (luma)..."
                        job.progress = 0.0

                    # Find ld-dropout-correct command
                    import shutil
                    dropout_cmd = shutil.which('ld-dropout-correct')
                    if not dropout_cmd:
                        # Check common paths
                        for path in ['/usr/bin/ld-dropout-correct', '/usr/local/bin/ld-dropout-correct',
                                     os.path.expanduser('~/.local/bin/ld-dropout-correct')]:
                            if os.path.exists(path):
                                dropout_cmd = path
                                break

                    if dropout_cmd:
                        # Create temp file for dropout-corrected TBC
                        tbc_dir = os.path.dirname(job.input_file)
                        tbc_base = os.path.basename(job.input_file)
                        if tbc_base.endswith('.tbc'):
                            project_base = tbc_base[:-4]  # Remove .tbc
                            temp_base = project_base + '_reverse_temp.tbc'
                        else:
                            project_base = tbc_base
                            temp_base = tbc_base + '_reverse_temp.tbc'
                        reverse_temp_file = os.path.join(tbc_dir, temp_base)
                        reverse_temp_json = reverse_temp_file + '.json'
                        # ld-dropout-correct creates chroma file with _chroma.tbc suffix
                        reverse_temp_chroma = os.path.join(tbc_dir, project_base + '_reverse_temp_chroma.tbc')

                        # Check if source has a chroma file (for colour output)
                        source_chroma = os.path.join(tbc_dir, project_base + '_chroma.tbc')
                        has_chroma = os.path.exists(source_chroma)
                        if has_chroma:
                            self.logger.info(f"Source has chroma file: {source_chroma}")
                        else:
                            self.logger.info("No chroma file found - output will be B&W")

                        # Build and run ld-dropout-correct --reverse on luma TBC
                        dropout_process_cmd = [
                            dropout_cmd,
                            '--reverse',
                            job.input_file,
                            reverse_temp_file
                        ]
                        self.logger.info(f"Running dropout correction with reverse (luma): {' '.join(dropout_process_cmd)}")

                        try:
                            import subprocess
                            result = subprocess.run(
                                dropout_process_cmd,
                                capture_output=True,
                                text=True,
                                timeout=7200  # 2 hour timeout for very large files
                            )
                            if result.returncode != 0:
                                self.logger.error(f"ld-dropout-correct (luma) failed: {result.stderr}")
                                job.error_message = f"Reverse field dropout correction failed: {result.stderr}"
                                job.status_message = ""
                                return False
                            self.logger.info("Dropout correction with reverse (luma) completed successfully")

                            # Check if chroma file was automatically created
                            if has_chroma:
                                if os.path.exists(reverse_temp_chroma):
                                    self.logger.info(f"Chroma temp file created automatically: {reverse_temp_chroma}")
                                else:
                                    # Chroma file wasn't auto-created, process it explicitly
                                    # Note: ld-dropout-correct on chroma uses the luma TBC's JSON for metadata
                                    self.logger.info("Chroma not auto-created, processing chroma file explicitly")

                                    # Update status for chroma processing
                                    with self.lock:
                                        job.status_message = "Preparing reverse field order (chroma)..."

                                    dropout_chroma_cmd = [
                                        dropout_cmd,
                                        '--reverse',
                                        '--input-json', reverse_temp_file + '.json',  # Use the reversed luma's JSON
                                        source_chroma,
                                        reverse_temp_chroma
                                    ]
                                    self.logger.info(f"Running dropout correction with reverse (chroma): {' '.join(dropout_chroma_cmd)}")

                                    chroma_result = subprocess.run(
                                        dropout_chroma_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=7200  # 2 hour timeout for very large files
                                    )
                                    if chroma_result.returncode != 0:
                                        self.logger.warning(f"ld-dropout-correct (chroma) failed: {chroma_result.stderr}")
                                        self.logger.warning("Continuing without chroma - output will be B&W")
                                    else:
                                        self.logger.info("Dropout correction with reverse (chroma) completed successfully")

                                    # Verify chroma was created
                                    if os.path.exists(reverse_temp_chroma):
                                        self.logger.info(f"Chroma temp file created: {reverse_temp_chroma}")
                                    else:
                                        self.logger.warning("Chroma temp file still not created - output will be B&W")

                        except subprocess.TimeoutExpired:
                            self.logger.error("ld-dropout-correct timed out")
                            job.error_message = "Reverse field dropout correction timed out"
                            job.status_message = ""
                            return False
                        except Exception as e:
                            self.logger.error(f"ld-dropout-correct error: {e}")
                            job.error_message = f"Reverse field dropout correction error: {e}"
                            job.status_message = ""
                            return False

                        # Clear status message before starting export
                        with self.lock:
                            job.status_message = "Exporting video..."

                        # Now modify the flags: keep --reverse, add --no-dropout-correct
                        # (dropout correction already done in pre-processing)
                        if '--no-dropout-correct' not in cli_flags:
                            cli_flags.append('--no-dropout-correct')
                    else:
                        self.logger.warning("ld-dropout-correct not found - reverse field order may not work correctly")

                if cli_flags:
                    cmd.extend(cli_flags)
                    self.logger.info(f"Added project export flags: {' '.join(cli_flags)}")

            # Find the exact corresponding .tbc.json file based on project base name
            # The project naming convention: base name (e.g. "Metallica1") stays consistent
            # throughout pipeline, only extensions change to indicate processing stage
            tbc_json_file = None
            try:
                tbc_dir = os.path.dirname(job.input_file)
                tbc_filename = os.path.basename(job.input_file)  # e.g. "Metallica1.tbc"
                
                # Extract the project base name from the .tbc file
                if tbc_filename.endswith('.tbc'):
                    project_base_name = tbc_filename[:-4]  # Remove .tbc extension -> "Metallica1"
                    
                    # The corresponding JSON file is exactly: ProjectName.tbc.json
                    expected_json_file = os.path.join(tbc_dir, f"{project_base_name}.tbc.json")
                    
                    if os.path.exists(expected_json_file):
                        tbc_json_file = expected_json_file
                        self.logger.info(f"Found TBC JSON file: {tbc_json_file}")
                    else:
                        self.logger.warning(f"Expected TBC JSON file not found: {expected_json_file}")
                        self.logger.info(f"tbc-video-export may fail without the correct JSON metadata")
                else:
                    self.logger.warning(f"Input file does not have .tbc extension: {tbc_filename}")
                
                if tbc_json_file:
                    cmd.extend(['--input-tbc-json', tbc_json_file])
                    self.logger.info(f"Using TBC JSON file: {tbc_json_file}")
                else:
                    self.logger.info(f"No TBC JSON file provided - tbc-video-export may fail without videoParameters")
                    
            except Exception as e:
                self.logger.warning(f"Error during JSON file detection (non-critical): {e}")

            # Use temp file if reverse field order pre-processing was done
            actual_input_file = reverse_temp_file if reverse_temp_file and os.path.exists(reverse_temp_file) else job.input_file

            # If using temp file, also use its JSON file
            if reverse_temp_file and os.path.exists(reverse_temp_file) and reverse_temp_json and os.path.exists(reverse_temp_json):
                # Replace the JSON file reference in cmd if it was added
                try:
                    json_idx = cmd.index('--input-tbc-json')
                    cmd[json_idx + 1] = reverse_temp_json
                    self.logger.info(f"Using reverse-corrected TBC JSON: {reverse_temp_json}")
                except ValueError:
                    # --input-tbc-json not in cmd, add it
                    cmd.extend(['--input-tbc-json', reverse_temp_json])

            cmd.extend([
                actual_input_file,
                job.output_file
            ])
            
            self.logger.info(f"TBC export command: {' '.join(cmd)}")
            
            # Start process with proper environment
            import subprocess
            
            # Prepare environment - inherit current environment and ensure conda paths are included
            env = os.environ.copy()
            
            # Set up conda environment paths - Force use of the ddd-capture-toolkit environment
            conda_prefix = os.environ.get('CONDA_PREFIX')
            if not conda_prefix:
                # Always use the ddd-capture-toolkit environment for TBC exports
                home_dir = os.path.expanduser('~')
                potential_paths = [
                    os.path.join(home_dir, 'anaconda3', 'envs', 'ddd-capture-toolkit'),
                    os.path.join(home_dir, 'miniconda3', 'envs', 'ddd-capture-toolkit'),
                    '/opt/anaconda3/envs/ddd-capture-toolkit',
                    '/opt/miniconda3/envs/ddd-capture-toolkit'
                ]
                
                for path in potential_paths:
                    if os.path.exists(os.path.join(path, 'bin', 'ffmpeg')):
                        conda_prefix = path
                        self.logger.info(f"Found conda environment at: {conda_prefix}")
                        break
            
            # Always set conda environment, even if we think we're already in one
            if not conda_prefix:
                # Fallback - try to auto-detect based on ffmpeg location
                import shutil
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path:
                    # If ffmpeg is found, derive conda prefix from its path
                    if 'conda' in ffmpeg_path or 'anaconda' in ffmpeg_path or 'miniconda' in ffmpeg_path:
                        conda_prefix = ffmpeg_path.split('/bin/')[0]
                        self.logger.info(f"Derived conda environment from ffmpeg path: {conda_prefix}")
            
            if conda_prefix:
                conda_bin = os.path.join(conda_prefix, 'bin')
                current_path = env.get('PATH', '')
                # Prepend conda bin to PATH to ensure conda tools are found first
                env['PATH'] = f"{conda_bin}:{current_path}"
                env['CONDA_PREFIX'] = conda_prefix
                env['CONDA_DEFAULT_ENV'] = 'ddd-capture-toolkit'
                env['CONDA_PROMPT_MODIFIER'] = '(ddd-capture-toolkit) '
                self.logger.info(f"Set conda environment PATH: {conda_bin}")
            else:
                self.logger.warning(f"Could not find conda environment with ffmpeg - TBC export may fail")
            
            # start_new_session: see decode launch for rationale (avoid killing parent)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
                start_new_session=True
            )
            
            # Track the process for termination
            self.job_processes[job.job_id] = process
            
            # Get total frames from TBC JSON metadata first (similar to VHS decode approach)
            if tbc_json_file:
                total_frames = self._get_total_frames_from_tbc_json(tbc_json_file)
                if total_frames > 0:
                    with self.lock:
                        job.total_frames = total_frames
                        self.save_queue()
                    self.logger.info(f"TBC export will process {total_frames} frames based on JSON metadata")
            else:
                total_frames = 0
                self.logger.warning("No TBC JSON file available - frame count will be parsed from stderr")
            
            # Parse output for progress (tbc-video-export shows detailed progress)
            current_frame = 0
            current_fps = 0
            import re
            import threading
            start_time = time.time()

            # Helper function to parse frame progress from a line
            def parse_frame_progress(line: str, source: str):
                nonlocal current_frame, current_fps, total_frames

                # Clean ANSI escape codes
                clean_line = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', line)

                # Parse total frames if not yet known
                if 'Total Frames:' in clean_line and total_frames == 0:
                    match = re.search(r'Total Frames:\s*(\d+)', clean_line)
                    if match:
                        total_frames = int(match.group(1))
                        self.logger.info(f"TBC export total frames: {total_frames}")
                        with self.lock:
                            job.total_frames = total_frames

                new_frame = None
                new_fps = None

                # Parse tbc-video-export progress format: "Info: 9856 frames processed - 119.726 FPS"
                tbc_progress_match = re.search(r'(\d+)\s+frames processed\s*-\s*([0-9.]+)\s*FPS', clean_line)
                if tbc_progress_match:
                    new_frame = int(tbc_progress_match.group(1))
                    new_fps = float(tbc_progress_match.group(2))

                # Alternative format: "Info: Processed and written frame 10300"
                if new_frame is None:
                    written_frame_match = re.search(r'Processed and written frame\s+(\d+)', clean_line)
                    if written_frame_match:
                        new_frame = int(written_frame_match.group(1))

                # Fallback: FFmpeg format "frame=  123 fps= 45 ..."
                if new_frame is None:
                    frame_match = re.search(r'frame=\s*(\d+)', clean_line)
                    if frame_match:
                        new_frame = int(frame_match.group(1))
                        fps_match = re.search(r'fps=\s*([0-9.]+)', clean_line)
                        if fps_match:
                            new_fps = float(fps_match.group(1))

                # Only update if we have a new frame count AND it's higher than before (never go backwards)
                if new_frame is not None and new_frame > current_frame:
                    current_frame = new_frame

                    # Update FPS if we got it from the output, otherwise calculate it
                    if new_fps is not None:
                        current_fps = new_fps
                    else:
                        elapsed_time = time.time() - start_time
                        current_fps = current_frame / elapsed_time if elapsed_time > 0 else 0

                    # Update job progress
                    if total_frames > 0:
                        progress = (current_frame / total_frames) * 100
                        with self.lock:
                            job.progress = min(progress, 99.9)
                            job.current_frame = current_frame
                            job.current_fps = current_fps

                        self.logger.debug(f"TBC export progress ({source}): {progress:.1f}% (frame {current_frame}/{total_frames}, {current_fps:.1f} fps)")

            # Read stdout - with --show-process-output, FFmpeg output goes here
            def read_stdout():
                try:
                    for line in iter(process.stdout.readline, ''):
                        if not line:
                            break

                        line = line.strip()
                        if line:
                            self.logger.debug(f"TBC export stdout: {line}")
                            parse_frame_progress(line, "stdout")
                except Exception as e:
                    self.logger.debug(f"Error reading stdout: {e}")
            
            # Start stdout reader thread
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()
            
            # Parse tbc-video-export stderr for total frames and FFmpeg frame progress
            def monitor_progress():
                nonlocal current_frame, total_frames, current_fps

                # Read tbc-video-export stderr for total frames and FFmpeg progress
                try:
                    for line in iter(process.stderr.readline, ''):
                        if not line:
                            break

                        line = line.strip()
                        if line:
                            self.logger.debug(f"TBC export stderr: {line}")
                            parse_frame_progress(line, "stderr")

                except Exception as e:
                    self.logger.debug(f"Error reading tbc-video-export stderr: {e}")
            
            # Start progress monitoring thread
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()
            
            # Wait for completion with proper tracking
            self.logger.info(f"TBC export process started (PID: {process.pid}), monitoring completion...")
            
            try:
                # Wait for the main process to complete
                return_code = process.wait()
                self.logger.info(f"TBC export main process completed with return code: {return_code}")
                
                # Give the progress monitoring thread a chance to finish updating
                monitor_thread.join(timeout=5.0)
                
                # Verify the actual completion status
                output_exists = os.path.exists(job.output_file) and os.path.getsize(job.output_file) > 0
                
                # Determine success based on return code AND output file
                success = return_code == 0 and output_exists
                
                # Set final status and progress
                with self.lock:
                    if success:
                        job.progress = 100.0
                        self.logger.info(f"TBC export completed successfully: {job.output_file} ({os.path.getsize(job.output_file) // (1024*1024)} MB)")
                    else:
                        if return_code != 0:
                            self.logger.error(f"TBC export failed with return code {return_code}")
                            job.error_message = f"Process failed with return code {return_code}"
                        elif not output_exists:
                            self.logger.error(f"TBC export failed: output file not created or empty: {job.output_file}")
                            job.error_message = f"Output file not created or empty"
                    
                    # Always save the final state
                    self.save_queue()
                
                return success
                
            finally:
                # Always clean up process tracking when the job execution thread is done
                if job.job_id in self.job_processes:
                    del self.job_processes[job.job_id]
                    self.logger.debug(f"Cleaned up process tracking for job {job.job_id}")

                # Clean up reverse field order temp files if they were created
                if reverse_temp_file:
                    # Build list of temp files to clean up
                    temp_files_to_clean = [reverse_temp_file, reverse_temp_json]
                    # Add chroma file if it was tracked
                    if reverse_temp_chroma:
                        temp_files_to_clean.append(reverse_temp_chroma)

                    for temp_file in temp_files_to_clean:
                        if temp_file and os.path.exists(temp_file):
                            try:
                                os.remove(temp_file)
                                self.logger.info(f"Cleaned up temp file: {temp_file}")
                            except Exception as cleanup_error:
                                self.logger.warning(f"Failed to clean up temp file {temp_file}: {cleanup_error}")
            
        except Exception as e:
            job.error_message = str(e)
            self.logger.error(f"TBC export job error: {e}")
            return False
    
    def _execute_audio_align_job(self, job: QueuedJob) -> bool:
        """Execute an audio alignment job using the existing mono-based alignment functionality"""
        try:
            self.logger.info(f"Starting audio alignment: {job.input_file} -> {job.output_file}")
            
            # Get parameters from the job
            audio_file = job.parameters.get('audio_file', job.input_file)
            tbc_json_file = job.parameters.get('tbc_json_file')
            aligned_output = job.parameters.get('aligned_output', job.output_file)
            overwrite = job.parameters.get('overwrite', False)
            
            # Validate input files exist
            if not os.path.exists(audio_file):
                self.logger.error(f"Audio file not found: {audio_file}")
                job.error_message = f"Audio file not found: {audio_file}"
                return False
            
            if not os.path.exists(tbc_json_file):
                self.logger.error(f"TBC JSON file not found: {tbc_json_file}")
                job.error_message = f"TBC JSON file not found: {tbc_json_file}"
                return False
            
            # Check if output already exists and handle overwrite
            if os.path.exists(aligned_output) and not overwrite:
                self.logger.error(f"Output file already exists and overwrite not requested: {aligned_output}")
                job.error_message = f"Output file already exists: {aligned_output}"
                return False
            
            # Use the VHS audio alignment script directly to avoid blocking the UI
            try:
                self.logger.info(f"Running VHS audio alignment script directly for background processing")
                
                # Update progress to indicate alignment has started
                with self.lock:
                    job.progress = 10.0
                    self.save_queue()
                
                # Find the VHS audio alignment script
                alignment_script_paths = [
                    'tools/audio-sync/vhs_audio_align.py',
                    'vhs_audio_align.py',
                    'tools/vhs_audio_align.py'
                ]
                
                alignment_script = None
                for script_path in alignment_script_paths:
                    if os.path.exists(script_path):
                        alignment_script = script_path
                        break
                
                if not alignment_script:
                    self.logger.error("VHS audio alignment script not found")
                    job.error_message = "VHS audio alignment script not found"
                    return False
                
                self.logger.info(f"Using alignment script: {alignment_script}")
                
                # Run the alignment script as a subprocess to avoid blocking
                import subprocess
                
                alignment_cmd = [
                    sys.executable, alignment_script,
                    audio_file, tbc_json_file, aligned_output
                ]
                
                self.logger.info(f"Running alignment command: {' '.join(alignment_cmd)}")

                # Get input file size for progress estimation
                input_file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
                self.logger.info(f"Input audio file size: {input_file_size / (1024*1024):.1f} MB")

                # Update progress during processing
                with self.lock:
                    job.progress = 5.0
                    job.total_frames = input_file_size  # Use bytes as "frames" for progress calc
                    self.save_queue()

                # Run the subprocess with proper output capture.
                # start_new_session: see decode launch for rationale (avoid killing parent)
                process = subprocess.Popen(
                    alignment_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    start_new_session=True
                )

                # Track the process for termination capability
                self.job_processes[job.job_id] = process

                # Monitor the process and log output (but don't print to console)
                stdout_lines = []
                stderr_lines = []
                start_time = time.time()
                last_output_size = 0

                # Track throughput: bytes/sec over the most recent sample window.
                # The job's current_fps field is documented as type-dependent; for
                # audio-align we use it for write-rate (analogous to compress).
                last_sample_time = start_time

                # Read output without blocking the main interface
                while True:
                    return_code = process.poll()

                    # Read available output
                    try:
                        stdout_line = process.stdout.readline()
                        if stdout_line:
                            stdout_lines.append(stdout_line.strip())
                            self.logger.debug(f"Alignment stdout: {stdout_line.strip()}")

                        stderr_line = process.stderr.readline()
                        if stderr_line:
                            stderr_lines.append(stderr_line.strip())
                            self.logger.debug(f"Alignment stderr: {stderr_line.strip()}")

                    except Exception as e:
                        self.logger.debug(f"Error reading process output: {e}")

                    # Monitor output file size for progress
                    if os.path.exists(aligned_output):
                        try:
                            output_size = os.path.getsize(aligned_output)
                            if output_size > last_output_size and input_file_size > 0:
                                # Calculate progress based on output file growth
                                # Output should be roughly same size as input
                                progress = min((output_size / input_file_size) * 100, 95.0)
                                progress = max(progress, 5.0)  # Minimum 5%

                                # Throughput over the last sample window
                                now = time.time()
                                dt = now - last_sample_time
                                bytes_per_sec = ((output_size - last_output_size) / dt) if dt > 0 else 0.0

                                with self.lock:
                                    job.progress = progress
                                    job.current_frame = output_size
                                    job.current_fps = bytes_per_sec  # bytes/sec, rendered as MB/s

                                last_output_size = output_size
                                last_sample_time = now
                                self.logger.debug(
                                    f"Alignment progress: {progress:.1f}% "
                                    f"({output_size / (1024*1024):.1f} MB) @ "
                                    f"{bytes_per_sec / (1024*1024):.1f} MB/s"
                                )
                        except Exception as e:
                            self.logger.debug(f"Error monitoring output file: {e}")

                    # Check if process has finished
                    if return_code is not None:
                        break

                    # Small delay to avoid busy waiting
                    time.sleep(0.5)  # Check every 0.5 seconds
                
                # Read any remaining output
                try:
                    remaining_stdout, remaining_stderr = process.communicate(timeout=5)
                    if remaining_stdout:
                        stdout_lines.extend(remaining_stdout.strip().split('\n'))
                    if remaining_stderr:
                        stderr_lines.extend(remaining_stderr.strip().split('\n'))
                except subprocess.TimeoutExpired:
                    self.logger.warning("Timeout waiting for remaining process output")

                # Clean up process tracking
                if job.job_id in self.job_processes:
                    del self.job_processes[job.job_id]

                # Log the full output for debugging
                self.logger.info(f"Audio alignment process completed with return code: {return_code}")
                if stdout_lines:
                    self.logger.info(f"Alignment stdout: {' '.join(stdout_lines)}")
                if stderr_lines:
                    self.logger.info(f"Alignment stderr: {' '.join(stderr_lines)}")
                
                # Update progress
                with self.lock:
                    job.progress = 95.0
                    self.save_queue()
                
                # Check if alignment completed successfully by verifying output file
                if return_code == 0 and os.path.exists(aligned_output) and os.path.getsize(aligned_output) > 0:
                    file_size = os.path.getsize(aligned_output) / (1024*1024)  # MB
                    self.logger.info(f"Audio alignment completed successfully: {aligned_output} ({file_size:.1f} MB)")

                    # Set final progress
                    with self.lock:
                        job.progress = 100.0
                        self.save_queue()

                    return True
                else:
                    # Alignment failed
                    self.logger.error("Audio alignment failed or could not detect timing patterns")
                    job.error_message = "Audio alignment failed - no timing patterns detected"
                    return False
                    
            except ImportError as e:
                self.logger.error(f"Could not import ddd_clockgen_sync module: {e}")
                job.error_message = f"Missing dependency: ddd_clockgen_sync module"
                return False
            except Exception as e:
                self.logger.error(f"Error during alignment analysis: {e}")
                job.error_message = f"Alignment analysis error: {str(e)}"
                return False
            
        except Exception as e:
            self.logger.error(f"Audio alignment job error: {e}")
            job.error_message = str(e)
            return False
    
    def _execute_final_mux_job(self, job: QueuedJob) -> bool:
        """Execute a final muxing job using FFmpeg to combine video and audio"""
        try:
            self.logger.info(f"Starting final muxing: {job.input_file} -> {job.output_file}")
            
            # Get parameters from the job
            video_file = job.parameters.get('video_file', job.input_file)
            audio_file = job.parameters.get('audio_file')  # Can be None for video-only
            final_output = job.parameters.get('final_output', job.output_file)
            overwrite = job.parameters.get('overwrite', False)
            
            # Validate video file exists (required)
            if not os.path.exists(video_file):
                self.logger.error(f"Video file not found: {video_file}")
                job.error_message = f"Video file not found: {video_file}"
                return False
            
            # Audio file is optional
            audio_exists = audio_file and os.path.exists(audio_file)
            
            # Check if output already exists and handle overwrite
            if os.path.exists(final_output) and not overwrite:
                self.logger.error(f"Output file already exists and overwrite not requested: {final_output}")
                job.error_message = f"Output file already exists: {final_output}"
                return False
            
            self.logger.info(f"Final muxing configuration:")
            self.logger.info(f"  Video: {video_file}")
            if audio_exists:
                self.logger.info(f"  Audio: {audio_file}")
            else:
                self.logger.info(f"  Audio: None (video-only final output)")
            self.logger.info(f"  Output: {final_output}")
            
            # Update progress to indicate muxing has started
            with self.lock:
                job.progress = 10.0
                self.save_queue()
            
            # Build FFmpeg command
            import subprocess
            # Import config functions
            try:
                from config import get_ffmpeg_threads
                ffmpeg_threads = get_ffmpeg_threads()
            except ImportError:
                self.logger.warning("Could not import config module, using default 4 threads")
                ffmpeg_threads = 4
            
            ffmpeg_cmd = ['ffmpeg']
            
            # Add thread control for performance management
            if ffmpeg_threads > 0:
                ffmpeg_cmd.extend(['-threads', str(ffmpeg_threads)])
                self.logger.info(f"Using {ffmpeg_threads} threads for FFmpeg to maintain UI responsiveness")
            else:
                self.logger.info("Using auto-detect threads for FFmpeg")
            
            # Add input video file
            ffmpeg_cmd.extend(['-i', video_file])
            
            # Add input audio file if it exists
            if audio_exists:
                ffmpeg_cmd.extend(['-i', audio_file])
            
            # Copy video stream (no re-encoding)
            ffmpeg_cmd.extend(['-c:v', 'copy'])
            
            if audio_exists:
                # Resolve audio output settings: per-project flags override config defaults.
                # Backwards compat: old `resample_48k`/`output_wav` boolean flags map to the
                # equivalent new values.
                try:
                    from config import get_default_audio_resample_rate, get_default_audio_format
                    default_rate = get_default_audio_resample_rate()
                    default_format = get_default_audio_format()
                except ImportError:
                    default_rate = '96000'
                    default_format = 'flac'

                resample_target = default_rate
                audio_format = default_format
                if PROJECT_FLAGS_AVAILABLE and job.project_name:
                    try:
                        flags_manager = ProjectFlagsManager()
                        audio_flags = flags_manager.get_project_flags(job.project_name, 'audio')

                        # New choice-typed flags. Both are present in the schema
                        # so get_project_flags always includes them; only treat
                        # as an override when the value is a non-empty string
                        # (False/None/'' mean "no override; use system default").
                        rt = audio_flags.get('resample_target')
                        if isinstance(rt, str) and rt:
                            resample_target = rt
                        elif audio_flags.get('resample_48k', False):
                            resample_target = '48000'

                        af = audio_flags.get('audio_format')
                        if isinstance(af, str) and af:
                            audio_format = af
                        elif audio_flags.get('output_wav', False):
                            audio_format = 'wav'
                    except Exception as e:
                        self.logger.warning(f"Could not load audio flags: {e}")

                # Apply resampling if not 'none'. Use soxr for high-quality SRC on
                # the non-integer ratio (78125 -> 96000 / 48000 / 192000).
                if resample_target != 'none':
                    ffmpeg_cmd.extend([
                        '-af', f'aresample=resampler=soxr:precision=33:osf=s32',
                        '-ar', resample_target,
                    ])
                    self.logger.info(f"Audio: resampling to {resample_target} Hz (soxr)")
                else:
                    self.logger.info("Audio: keeping source sample rate (no resampling)")

                # Encode audio per chosen format (24-bit either way)
                if audio_format == 'wav':
                    ffmpeg_cmd.extend(['-c:a', 'pcm_s24le'])
                    self.logger.info("Audio: 24-bit WAV (pcm_s24le)")
                else:
                    ffmpeg_cmd.extend(['-c:a', 'flac', '-sample_fmt', 's32'])
                    self.logger.info("Audio: 24-bit FLAC")

                # Map video stream from input 0
                ffmpeg_cmd.extend(['-map', '0:v:0'])

                # Map audio stream from input 1
                ffmpeg_cmd.extend(['-map', '1:a:0'])
            else:
                # Video-only output - no audio mapping
                self.logger.info("Creating video-only final output (no audio stream)")
            
            # Overwrite output file if it exists
            ffmpeg_cmd.extend(['-y'])
            
            # Add output file
            ffmpeg_cmd.append(final_output)
            
            self.logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
            
            # Update progress
            with self.lock:
                job.progress = 20.0
                self.save_queue()
            
            # Run FFmpeg process with simple subprocess handling.
            # start_new_session: see decode launch for rationale (avoid killing parent)
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True
            )

            # Track the process for termination capability
            self.job_processes[job.job_id] = process

            self.logger.info(f"Started FFmpeg process with PID: {process.pid}")

            # Probe the input video for total frame count so we can compute a real
            # percentage and ETA. ffprobe is fast (~50ms) and one-shot.
            total_frames = 0
            try:
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-count_packets',
                    '-show_entries', 'stream=nb_read_packets',
                    '-of', 'csv=p=0',
                    video_file
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=15)
                if probe_result.returncode == 0:
                    probe_str = probe_result.stdout.strip()
                    if probe_str.isdigit():
                        total_frames = int(probe_str)
                        self.logger.info(f"Final mux: input has {total_frames} video packets/frames")
            except Exception as e:
                self.logger.debug(f"ffprobe for total frames failed: {e}")

            with self.lock:
                job.total_frames = total_frames
                job.current_frame = 0
                job.current_fps = 0.0

            # Monitor FFmpeg output for progress
            import re as _re_mux
            stderr_lines = []
            mux_start_time = time.time()

            while True:
                return_code = process.poll()

                # Read stderr output from FFmpeg
                try:
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        stderr_lines.append(stderr_line.strip())
                        self.logger.debug(f"FFmpeg stderr: {stderr_line.strip()}")

                        # Parse FFmpeg's "frame=N fps=NN" progress lines
                        frame_match = _re_mux.search(r'frame=\s*(\d+)', stderr_line)
                        if frame_match:
                            new_frame = int(frame_match.group(1))
                            fps_match = _re_mux.search(r'fps=\s*([0-9.]+)', stderr_line)
                            new_fps = float(fps_match.group(1)) if fps_match else 0.0

                            try:
                                with self.lock:
                                    job.current_frame = new_frame
                                    job.current_fps = new_fps
                                    if total_frames > 0:
                                        # Cap at 99% until process exits + size validation
                                        job.progress = min((new_frame / total_frames) * 100.0, 99.0)
                                    else:
                                        # No total known: hold at a safe placeholder
                                        # rather than the old 2%-per-line guess.
                                        if job.progress < 5.0:
                                            job.progress = 5.0
                            except Exception:
                                pass

                except Exception as e:
                    self.logger.debug(f"Error reading FFmpeg output: {e}")

                # Check if process has finished
                if return_code is not None:
                    break

                # Small delay to avoid busy waiting
                time.sleep(0.1)
            
            # Read any remaining output
            try:
                remaining_stdout, remaining_stderr = process.communicate(timeout=10)
                if remaining_stderr:
                    stderr_lines.extend(remaining_stderr.strip().split('\n'))
            except subprocess.TimeoutExpired:
                self.logger.warning("Timeout waiting for remaining FFmpeg output")

            # Clean up process tracking
            if job.job_id in self.job_processes:
                del self.job_processes[job.job_id]

            # Update progress
            with self.lock:
                job.progress = 95.0
                self.save_queue()
            
            # Check results
            self.logger.info(f"FFmpeg process completed with return code: {return_code}")
            if stderr_lines:
                self.logger.info(f"FFmpeg stderr: {' '.join(stderr_lines[-10:])}")
            
            # Verify output file was created successfully
            output_exists = os.path.exists(final_output) and os.path.getsize(final_output) > 0
            
            # Additional validation for final muxing: check if output file size is reasonable
            # A properly muxed final file should be roughly the size of the video file
            # (since we're just copying video stream and adding audio)
            size_validation_passed = True
            if output_exists and os.path.exists(video_file):
                output_size = os.path.getsize(final_output)
                video_size = os.path.getsize(video_file)
                
                # Final file should be at least 80% of the video file size
                # (accounting for different container overhead, but catching severely truncated files)
                min_expected_size = video_size * 0.8
                
                if output_size < min_expected_size:
                    size_validation_passed = False
                    self.logger.warning(f"Final output file appears truncated: {output_size} bytes vs video file {video_size} bytes")
            
            if return_code == 0 and output_exists and size_validation_passed:
                file_size = os.path.getsize(final_output) / (1024 * 1024)  # MB
                self.logger.info(f"Final muxing completed successfully: {final_output} ({file_size:.1f} MB)")
                
                # Set final progress
                with self.lock:
                    job.progress = 100.0
                    # Final save will be handled by _execute_job completion, not here
                
                return True
            else:
                error_msg = "FFmpeg failed"
                if return_code != 0:
                    error_msg = f"FFmpeg failed with return code {return_code}"
                elif not os.path.exists(final_output):
                    error_msg = f"Output file not created: {final_output}"
                elif os.path.getsize(final_output) == 0:
                    error_msg = f"Output file is empty: {final_output}"
                
                self.logger.error(error_msg)
                job.error_message = error_msg
                return False
                
        except FileNotFoundError:
            error_msg = "FFmpeg not found - please install FFmpeg to use muxing functionality"
            self.logger.error(error_msg)
            job.error_message = error_msg
            return False
        except Exception as e:
            self.logger.error(f"Final muxing job error: {e}")
            job.error_message = str(e)
            return False

    def _execute_lds_compress_job(self, job: QueuedJob) -> bool:
        """Execute an LDS compression job using ld-compress to convert .lds to .ldf"""
        try:
            self.logger.info(f"Starting LDS compression: {job.input_file} -> {job.output_file}")

            # Validate input file exists
            if not os.path.exists(job.input_file):
                self.logger.error(f"Input LDS file not found: {job.input_file}")
                job.error_message = f"Input file not found: {job.input_file}"
                return False

            # Get compression level from parameters (default 11)
            compression_level = job.parameters.get('compression_level', 11)
            show_progress = job.parameters.get('show_progress', True)
            overwrite = job.parameters.get('overwrite', False)
            gpu = job.parameters.get('gpu', False)
            # GPU mode (ld-compress -a) caps at level 11; clamp here so we don't
            # pass an invalid level if the parameter ever exceeds the cap.
            if gpu and compression_level > 11:
                compression_level = 11

            # Check if output already exists
            if os.path.exists(job.output_file) and not overwrite:
                self.logger.error(f"Output file already exists: {job.output_file}")
                job.error_message = f"Output file already exists: {job.output_file}"
                return False

            # Get input file size for progress estimation
            input_size = os.path.getsize(job.input_file)
            input_size_gb = input_size / (1024 ** 3)
            self.logger.info(f"Input file size: {input_size_gb:.2f} GB")

            # Find the ld-compress script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ld_compress_paths = [
                os.path.join(script_dir, 'external', 'vhs-decode', 'scripts', 'ld-compress'),
                os.path.join(script_dir, 'external', 'ld-decode', 'scripts', 'ld-compress'),
                'ld-compress'  # Try PATH as fallback
            ]

            ld_compress_cmd = None
            for path in ld_compress_paths:
                if os.path.exists(path):
                    ld_compress_cmd = path
                    break
                elif path == 'ld-compress':
                    # Check if it's in PATH
                    import shutil
                    if shutil.which('ld-compress'):
                        ld_compress_cmd = 'ld-compress'
                        break

            if not ld_compress_cmd:
                self.logger.error("ld-compress script not found")
                job.error_message = "ld-compress script not found in external/vhs-decode/scripts/ or PATH"
                return False

            # Build the ld-compress command. -a (GPU) and -c (CPU) are mutually
            # exclusive modes in ld-compress; -a must come before -l so the level
            # validator runs in GPU mode (which caps at 11). GPU output is
            # <base>.flac.ldf and is renamed to <base>.ldf below to keep the rest
            # of the toolkit's naming consistent.
            mode_flag = '-a' if gpu else '-c'
            cmd = [ld_compress_cmd, mode_flag, '-l', str(compression_level)]

            if show_progress:
                cmd.append('-p')

            cmd.append(job.input_file)

            self.logger.info(f"Running ld-compress ({'GPU' if gpu else 'CPU'} mode): {' '.join(cmd)}")

            # Update progress
            with self.lock:
                job.progress = 5.0
                self.save_queue()

            # Change to output directory since ld-compress writes to current directory
            output_dir = os.path.dirname(job.output_file)
            if not output_dir:
                output_dir = os.getcwd()

            # Run ld-compress. start_new_session puts the bash script and its
            # pipeline children (ld-lds-converter, flaldf/ffmpeg) in their own
            # process group so we can signal the whole group on cancel - otherwise
            # bash dies but the pipeline children keep running as orphans.
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=output_dir,
                start_new_session=True
            )

            # Track the process for termination capability
            self.job_processes[job.job_id] = process

            self.logger.info(f"Started ld-compress process with PID: {process.pid}")

            # Real progress comes from polling the output file's size on disk.
            # CPU mode writes <base>.ldf directly; GPU mode writes <base>.flac.ldf
            # and we rename it after the process exits. Watch both.
            input_basename = os.path.basename(job.input_file)
            output_candidates = []
            if input_basename.endswith('.lds'):
                base = input_basename[:-4]
                output_candidates = [
                    os.path.join(output_dir, base + '.ldf'),
                    os.path.join(output_dir, base + '.flac.ldf'),
                ]

            # Estimated final output size as a fraction of input. Used to convert
            # bytes-on-disk into a percentage. The ld-decode wiki cites ~0.70 for
            # FLAC level 11 on RF, but observed reality on this toolkit's captures
            # is closer to 0.80-0.86 (varies with RF noise floor and content).
            # Bias the default toward the high end so progress doesn't hit the cap
            # too early; the dynamic-expansion logic below handles outliers.
            EXPECTED_RATIO = 0.85
            expected_output_bytes = int(input_size * EXPECTED_RATIO)

            # Stash bytes in the existing per-job progress fields. They are
            # documented as type-dependent (frames for decode/export, bytes here).
            with self.lock:
                job.total_frames = expected_output_bytes
                job.current_frame = 0
                job.current_fps = 0.0

            last_progress_update = time.time()
            start_time = time.time()
            last_output_bytes = 0
            last_sample_time = start_time

            import select

            while True:
                return_code = process.poll()

                # Non-blocking read of output using select
                try:
                    if process.stdout:
                        # Check if there's data to read (with 0.5s timeout)
                        readable, _, _ = select.select([process.stdout], [], [], 0.5)
                        if readable:
                            line = process.stdout.readline()
                            if line:
                                line = line.strip()
                                self.logger.debug(f"ld-compress: {line}")
                except Exception as e:
                    self.logger.debug(f"Error reading ld-compress output: {e}")

                # Update progress from output file size every ~1s
                current_time = time.time()
                if current_time - last_progress_update > 1.0:
                    try:
                        # Find whichever output file currently exists
                        current_output_bytes = 0
                        for candidate in output_candidates:
                            if os.path.exists(candidate):
                                current_output_bytes = os.path.getsize(candidate)
                                break

                        # Compute throughput as bytes-per-second over the last interval
                        dt = current_time - last_sample_time
                        bytes_per_sec = ((current_output_bytes - last_output_bytes) / dt) if dt > 0 else 0.0

                        # If the file is compressing worse than our default ratio,
                        # extend the estimate so progress keeps moving instead of
                        # parking at 99%. We push the estimate to current+10% so
                        # the percentage drops a bit but resumes climbing.
                        if expected_output_bytes > 0 and current_output_bytes > expected_output_bytes:
                            expected_output_bytes = int(current_output_bytes * 1.10)
                            with self.lock:
                                job.total_frames = expected_output_bytes

                        # Real percentage. Cap at 99 until the process exits so we
                        # don't claim 100% before the rename / verify steps run.
                        if expected_output_bytes > 0:
                            real_progress = (current_output_bytes / expected_output_bytes) * 100.0
                            real_progress = min(real_progress, 99.0)
                        else:
                            real_progress = 0.0

                        with self.lock:
                            job.progress = real_progress
                            job.current_frame = current_output_bytes
                            job.current_fps = bytes_per_sec
                            self._save_queue_async()

                        last_output_bytes = current_output_bytes
                        last_sample_time = current_time

                        elapsed = current_time - start_time
                        if int(elapsed) % 10 == 0:
                            mbps = bytes_per_sec / (1024 * 1024)
                            self.logger.debug(
                                f"Compress progress: {real_progress:.1f}% "
                                f"({current_output_bytes / (1024**3):.2f} GB / "
                                f"~{expected_output_bytes / (1024**3):.2f} GB est) "
                                f"@ {mbps:.1f} MB/s, elapsed {elapsed:.0f}s"
                            )
                    except Exception as e:
                        self.logger.debug(f"Error updating progress: {e}")
                    last_progress_update = current_time

                if return_code is not None:
                    break

                time.sleep(0.5)

            # Read remaining output
            try:
                remaining_output, _ = process.communicate(timeout=10)
                if remaining_output:
                    self.logger.debug(f"ld-compress remaining output: {remaining_output}")
            except subprocess.TimeoutExpired:
                self.logger.warning("Timeout waiting for remaining ld-compress output")

            # Clean up process tracking
            if job.job_id in self.job_processes:
                del self.job_processes[job.job_id]

            # Check if output file was created
            # ld-compress writes to the current working directory.
            # CPU mode produces <base>.ldf; GPU mode (-a) produces <base>.flac.ldf.
            expected_output = job.output_file

            # Build candidate paths in priority order. We rename to the expected
            # path so the rest of the toolkit sees the standard .ldf extension.
            input_basename = os.path.basename(job.input_file)
            candidate_outputs = []
            if input_basename.endswith('.lds'):
                base = input_basename[:-4]  # strip .lds
                candidate_outputs.append(os.path.join(output_dir, base + '.ldf'))
                candidate_outputs.append(os.path.join(output_dir, base + '.flac.ldf'))

            output_exists = os.path.exists(expected_output)
            if not output_exists:
                for candidate in candidate_outputs:
                    if candidate != expected_output and os.path.exists(candidate):
                        import shutil
                        shutil.move(candidate, expected_output)
                        self.logger.info(f"Renamed {os.path.basename(candidate)} -> {os.path.basename(expected_output)}")
                        output_exists = True
                        break

            self.logger.info(f"ld-compress completed with return code: {return_code}")

            if return_code == 0 and output_exists and os.path.getsize(expected_output) > 0:
                output_size = os.path.getsize(expected_output) / (1024 ** 3)
                compression_ratio = (1 - (os.path.getsize(expected_output) / input_size)) * 100
                self.logger.info(f"LDS compression completed: {expected_output}")
                self.logger.info(f"Output size: {output_size:.2f} GB (compression ratio: {compression_ratio:.1f}%)")

                with self.lock:
                    job.progress = 100.0

                return True
            else:
                error_msg = "ld-compress failed"
                if return_code != 0:
                    error_msg = f"ld-compress failed with return code {return_code}"
                elif not output_exists:
                    error_msg = f"Output file not created: {expected_output}"
                elif os.path.getsize(expected_output) == 0:
                    error_msg = f"Output file is empty: {expected_output}"

                self.logger.error(error_msg)
                job.error_message = error_msg
                return False

        except FileNotFoundError as e:
            error_msg = f"Required tool not found: {e}"
            self.logger.error(error_msg)
            job.error_message = error_msg
            return False
        except Exception as e:
            self.logger.error(f"LDS compression job error: {e}")
            job.error_message = str(e)
            return False

    def save_queue(self):
        """Save queue to persistent storage"""
        try:
            data = {
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "per_location_limits": self.per_location_limits,
                "jobs": [job.to_dict() for job in self.jobs]
            }

            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Error saving queue: {e}")
    
    def _save_queue_data(self, jobs_list):
        """Save specific job list to persistent storage (used by non-blocking methods)"""
        try:
            data = {
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "per_location_limits": self.per_location_limits,
                "jobs": [job.to_dict() for job in jobs_list]
            }

            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Error saving queue data: {e}")
    
    def _save_queue_async(self):
        """Save queue asynchronously without holding the main lock for too long"""
        try:
            # Quickly acquire lock, copy job data, and release
            jobs_copy = None
            if self.lock.acquire(timeout=0.1):
                try:
                    jobs_copy = self.jobs.copy()
                finally:
                    self.lock.release()
                
                # Save without holding the main lock
                if jobs_copy is not None:
                    self._save_queue_data(jobs_copy)
            else:
                # If we can't get the lock quickly, skip the save to avoid blocking
                self.logger.debug("Skipping queue save due to lock contention")
                
        except Exception as e:
            self.logger.debug(f"Error in async queue save: {e}")
    
    def load_queue(self):
        """Load queue from persistent storage"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                
                self.max_concurrent_jobs = data.get("max_concurrent_jobs", 2)
                self.per_location_limits = data.get("per_location_limits", {})
                self.jobs = [QueuedJob.from_dict(job_data) for job_data in data.get("jobs", [])]
                
                # Improved auto-restart logic: only mark truly orphaned jobs as failed
                # Check for jobs that were running but have no associated process
                import psutil
                
                for job in self.jobs:
                    if job.status == JobStatus.RUNNING:
                        # Check if this is a recent job (within last 2 hours)
                        if job.started_at and (datetime.now() - job.started_at).total_seconds() < 7200:
                            # Recent job - check if process still exists
                            process_still_running = False
                            
                            try:
                                # Look for processes that might be related to this job
                                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                    try:
                                        cmdline = proc.info.get('cmdline', [])
                                        if cmdline and len(cmdline) > 0:
                                            cmdline_str = ' '.join(cmdline)
                                            
                                            # Check for tbc-video-export or ffmpeg processes with our files
                                            if ('tbc-video-export' in cmdline_str or 'ffmpeg' in cmdline_str):
                                                if (job.input_file in cmdline_str or 
                                                    job.output_file in cmdline_str or
                                                    os.path.basename(job.input_file) in cmdline_str or
                                                    os.path.basename(job.output_file) in cmdline_str):
                                                    process_still_running = True
                                                    self.logger.info(f"Found running process for job {job.job_id}: PID {proc.info['pid']}")
                                                    break
                                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                        continue
                                        
                            except ImportError:
                                # psutil not available, be conservative and keep job as running
                                self.logger.warning("psutil not available for process checking, keeping job as running")
                                process_still_running = True
                            except Exception as e:
                                self.logger.debug(f"Error checking processes for job {job.job_id}: {e}")
                                process_still_running = False
                            
                            if process_still_running:
                                # Process still running, keep job as RUNNING
                                self.logger.info(f"Job {job.job_id} has active process, keeping as RUNNING")
                            else:
                                # No process found, mark as failed
                                job.status = JobStatus.FAILED
                                job.completed_at = datetime.now()
                                job.error_message = "Job was interrupted (no active process found)"
                                self.logger.info(f"Marked orphaned job {job.job_id} as failed (no process found)")
                        else:
                            # Old job (>2 hours) or no start time - definitely failed
                            job.status = JobStatus.FAILED
                            job.completed_at = datetime.now()
                            job.error_message = "Job was interrupted (too old)"
                            job.started_at = None
                            self.logger.info(f"Marked old interrupted job {job.job_id} as failed")
                
                self.logger.info(f"Loaded {len(self.jobs)} jobs from queue")
                
        except Exception as e:
            self.logger.error(f"Error loading queue: {e}")
            self.jobs = []
    
    def cleanup_old_jobs(self, days: int = 7):
        """Remove completed/failed jobs older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with self.lock:
            original_count = len(self.jobs)
            self.jobs = [
                job for job in self.jobs 
                if job.status in [JobStatus.QUEUED, JobStatus.RUNNING] or 
                   (job.completed_at and job.completed_at > cutoff_date)
            ]
            
            removed_count = original_count - len(self.jobs)
            if removed_count > 0:
                self.save_queue()
                self.logger.info(f"Cleaned up {removed_count} old jobs")
    
    def _terminate_job_process(self, job_id: str) -> bool:
        """Terminate the process for a running job, including pipeline children.

        For jobs launched with start_new_session=True, the process is the leader
        of its own process group and we signal the whole group so any children
        (e.g. ld-lds-converter, flaldf in the ld-compress pipeline) are killed
        too. Falls back to single-process terminate/kill if process-group lookup
        fails (e.g. process already exited)."""
        import signal
        try:
            if job_id in self.job_processes:
                process = self.job_processes[job_id]
                self.logger.info(f"Terminating process {process.pid} for job {job_id}")

                # Try to find the process group so we can signal pipeline children too.
                # Critical safety check: if the subprocess shares the parent's process
                # group (i.e. was launched without start_new_session=True), killpg
                # would terminate the parent (and the entire WCC). Detect that case
                # and fall back to single-PID signalling.
                pgid = None
                try:
                    child_pgid = os.getpgid(process.pid)
                    own_pgid = os.getpgid(0)
                    if child_pgid == own_pgid:
                        self.logger.warning(
                            f"Process {process.pid} shares parent process group "
                            f"({child_pgid}); falling back to single-PID terminate "
                            "to avoid killing the parent. Launch this job with "
                            "start_new_session=True to clean up pipeline children."
                        )
                    else:
                        pgid = child_pgid
                except (ProcessLookupError, OSError):
                    pass

                def _signal(sig):
                    if pgid is not None:
                        try:
                            os.killpg(pgid, sig)
                            return
                        except (ProcessLookupError, PermissionError, OSError) as e:
                            self.logger.debug(f"killpg({pgid}, {sig}) failed: {e}, falling back to single PID")
                    # Fallback: signal just the tracked process
                    if sig == signal.SIGTERM:
                        process.terminate()
                    else:
                        process.kill()

                # Graceful termination first
                try:
                    _signal(signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                        self.logger.info(f"Process group for {process.pid} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful termination didn't work
                        self.logger.warning(f"Process {process.pid} didn't terminate gracefully, killing whole group")
                        _signal(signal.SIGKILL)
                        process.wait()
                        self.logger.info(f"Process group for {process.pid} killed forcefully")

                except ProcessLookupError:
                    # Process already terminated
                    self.logger.info(f"Process {process.pid} was already terminated")

                # Clean up process tracking
                del self.job_processes[job_id]
                return True
            else:
                self.logger.warning(f"No tracked process found for job {job_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error terminating process for job {job_id}: {e}")
            return False
    
    def _clean_job_progress(self, job_id: str) -> bool:
        """Clean stuck progress displays for failed jobs

        This method resets progress and error messages for failed jobs to clear
        stuck progress displays in the UI. It's intended for jobs that have
        failed but still show progress from their last run.

        Args:
            job_id: The ID of the job to clean

        Returns:
            bool: True if job was found and cleaned, False otherwise
        """
        try:
            with self.lock:
                for job in self.jobs:
                    if job.job_id == job_id:
                        # Check if this is a truly running job with an active process
                        has_active_process = job_id in self.job_processes

                        # Clean failed, cancelled, or stuck "running" jobs without active processes
                        if (job.status == JobStatus.FAILED or
                            job.status == JobStatus.CANCELLED or
                            (job.status == JobStatus.RUNNING and not has_active_process)):

                            # If it was stuck in RUNNING without a process, mark it as failed
                            if job.status == JobStatus.RUNNING and not has_active_process:
                                job.status = JobStatus.FAILED
                                self.logger.info(f"Marking stuck RUNNING job {job_id} as FAILED (no active process)")

                            # Reset progress and timing fields
                            job.progress = 0.0
                            job.current_frame = 0
                            job.total_frames = 0
                            job.current_fps = 0.0

                            # Mark job as cleaned so progress extraction knows to hide progress bars
                            if not hasattr(job, 'parameters'):
                                job.parameters = {}
                            job.parameters['_progress_cleaned'] = True

                            # Update error message to indicate cleanup
                            if job.error_message and not job.error_message.endswith(" (cleaned)"):
                                job.error_message += " (cleaned)"
                            elif not job.error_message:
                                job.error_message = "Progress cleaned"

                            # Save changes
                            self.save_queue()

                            self.logger.info(f"Cleaned stuck progress for job {job_id} (status: {job.status.value})")
                            return True
                        else:
                            self.logger.warning(f"Cannot clean actively running job {job_id}")
                            return False

                self.logger.warning(f"Job {job_id} not found for cleaning")
                return False

        except Exception as e:
            self.logger.error(f"Error cleaning job progress for {job_id}: {e}")
            return False

# Global instance
_job_queue_manager = None

def get_job_queue_manager() -> JobQueueManager:
    """Get the global job queue manager instance"""
    global _job_queue_manager
    if _job_queue_manager is None:
        _job_queue_manager = JobQueueManager()
        _job_queue_manager.start_processor()
    return _job_queue_manager

if __name__ == '__main__':
    # Test the job queue system
    print("Testing Job Queue Manager")
    manager = get_job_queue_manager()
    
    # Add some test jobs
    job1 = manager.add_job(
        job_type="vhs-decode",
        input_file="/test/sample1.lds",
        output_file="/test/sample1.tbc",
        parameters={"video_standard": "pal", "tape_speed": "SP"}
    )
    
    job2 = manager.add_job(
        job_type="vhs-decode", 
        input_file="/test/sample2.lds",
        output_file="/test/sample2.tbc",
        parameters={"video_standard": "ntsc", "tape_speed": "LP"}
    )
    
    print(f"Added jobs: {job1}, {job2}")
    print("Queue status:", manager.get_queue_status())
    
    # Keep running for a bit to test
    time.sleep(10)
    manager.stop_processor()
