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

class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

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
    
    # Progress tracking fields for real-time monitoring
    total_frames: int = 0
    current_frame: int = 0
    current_fps: float = 0.0
    
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
        
        return cls(**data)

class JobQueueManager:
    """Manages a persistent job queue with background processing"""
    
    def __init__(self, queue_file="config/job_queue.json", max_concurrent_jobs=2):
        self.queue_file = queue_file
        self.max_concurrent_jobs = max_concurrent_jobs
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
        
        job = QueuedJob(
            job_id=job_id,
            job_type=job_type,
            input_file=input_file,
            output_file=output_file,
            parameters=parameters,
            priority=priority
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
                    
                    job = QueuedJob(
                        job_id=job_id,
                        job_type=job_type,
                        input_file=input_file,
                        output_file=output_file,
                        parameters=parameters,
                        priority=priority,
                        project_name=project_name
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
        """Background job processor thread"""
        while not self.stop_processing:
            try:
                # Check if we can start more jobs
                with self.lock:
                    running_count = len([j for j in self.jobs if j.status == JobStatus.RUNNING])
                    available_slots = self.max_concurrent_jobs - running_count
                    
                    if available_slots > 0:
                        # Find next queued job with highest priority
                        next_job = None
                        for job in self.jobs:
                            if job.status == JobStatus.QUEUED:
                                next_job = job
                                break
                        
                        if next_job:
                            # Start the job
                            next_job.status = JobStatus.RUNNING
                            next_job.started_at = datetime.now()
                            self.save_queue()
                            
                            # Start job in separate thread
                            job_thread = threading.Thread(
                                target=self._execute_job, 
                                args=(next_job,),
                                daemon=True
                            )
                            job_thread.start()
                            self.running_jobs[next_job.job_id] = job_thread
                            
                            self.logger.info(f"Started job {next_job.job_id}")
                
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
            else:
                self.logger.error(f"Unknown job type: {job.job_type}")
                success = False
            
            with self.lock:
                if success:
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
            
            # Build vhs-decode command directly (simpler approach)
            cmd = [
                'vhs-decode',
                '--tf', 'vhs',
                '-t', '3',
                '--ts', job.parameters.get('tape_speed', 'SP'),
                '--no_resample',
                '--recheck_phase', 
                '--ire0_adjust'
            ]
            
            # Add video standard
            if job.parameters.get('video_standard', 'pal').lower() == 'pal':
                cmd.append('--pal')
            else:
                cmd.append('--ntsc')
            
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
            
            # Start process
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            current_frame = 0
            
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
                    if total_frames > 0:
                        progress = (current_frame / total_frames) * 100
                        # Update job progress with thread safety
                        with self.lock:
                            job.progress = min(progress, 99.9)  # Cap at 99.9% until completion
                            # Skip saving progress updates to avoid blocking during job execution
                            # Final progress will be saved when job completes
                    else:
                        # No frame count available, show frame number as basic progress
                        with self.lock:
                            job.progress = min(current_frame / 1000.0, 50.0)  # Very rough estimate
                            # Skip saving progress updates to avoid blocking during job execution
            
            # Wait for completion
            return_code = process.wait()
            
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
            
            # Find tbc-video-export command - try conda environment first, then PATH
            tbc_export_cmd = 'tbc-video-export'  # Default to PATH lookup
            
            # Check if we're in a conda environment
            conda_prefix = os.environ.get('CONDA_PREFIX')
            if conda_prefix:
                conda_tbc_path = os.path.join(conda_prefix, 'bin', 'tbc-video-export')
                if os.path.exists(conda_tbc_path):
                    tbc_export_cmd = conda_tbc_path
                    self.logger.info(f"Using conda tbc-video-export: {conda_tbc_path}")
            
            # If not found in conda, try common user paths
            if tbc_export_cmd == 'tbc-video-export':
                # Try ~/.local/bin (pip install --user)
                user_local_path = os.path.expanduser('~/.local/bin/tbc-video-export')
                if os.path.exists(user_local_path):
                    tbc_export_cmd = user_local_path
                    self.logger.info(f"Using user-local tbc-video-export: {user_local_path}")
            
            # Build tbc-video-export command
            cmd = [
                tbc_export_cmd,
                '--threads', '0',  # Use all available threads
                '--profile', 'ffv1',  # Use FFV1 lossless codec
            ]
            
            # Add overwrite flag if requested
            if job.parameters.get('overwrite', False):
                cmd.append('--overwrite')
            
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
            cmd.extend([
                job.input_file,
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
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
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
            
            # Read stdout (usually empty for tbc-video-export)
            def read_stdout():
                try:
                    for line in iter(process.stdout.readline, ''):
                        if not line:
                            break
                        
                        line = line.strip()
                        if line:
                            self.logger.debug(f"TBC export stdout: {line}")
                except Exception as e:
                    self.logger.debug(f"Error reading stdout: {e}")
            
            # Start stdout reader thread
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()
            
            # Simple approach: Parse tbc-video-export stderr for total frames, then estimate progress from output file size
            def monitor_progress():
                nonlocal current_frame, total_frames, current_fps
                start_time = time.time()  # Track start time for FPS calculation
                
                # Read tbc-video-export stderr for total frames and any other useful info
                try:
                    for line in iter(process.stderr.readline, ''):
                        if not line:
                            break
                        
                        line = line.strip()
                        if line:
                            self.logger.debug(f"TBC export stderr: {line}")
                            
                            # Parse total frames with more flexible regex
                            # Handle format: "Total Fields:  284578 Total Frames: 142289"
                            if 'Total Frames:' in line and total_frames == 0:
                                try:
                                    # Clean ANSI escape codes from the line first
                                    import re
                                    clean_line = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', line)
                                    self.logger.debug(f"Original line: {repr(line)}")
                                    self.logger.debug(f"Cleaned line: {repr(clean_line)}")
                                    
                                    # Use regex to extract number directly after "Total Frames:"
                                    match = re.search(r'Total Frames:\s*(\d+)', clean_line)
                                    if match:
                                        total_frames = int(match.group(1))
                                        self.logger.info(f"TBC export total frames: {total_frames}")
                                        with self.lock:
                                            job.total_frames = total_frames
                                            self.save_queue()
                                    else:
                                        self.logger.debug(f"Could not parse total frames from cleaned line: {clean_line}")
                                except Exception as e:
                                    self.logger.debug(f"Error parsing total frames: {e}")
                            
                            # If this line indicates FFmpeg has started, break to start monitoring output file
                            if 'Step 1' in line or 'ld-dropout-correct' in line or 'ld-chroma-decoder' in line:
                                self.logger.info("FFmpeg processing started, monitoring output file size")
                                break
                                
                except Exception as e:
                    self.logger.debug(f"Error reading tbc-video-export stderr: {e}")
                
                # If we got total frames, monitor output file size for progress estimation
                if total_frames > 0:
                    # Estimate final file size based on similar files or rough calculation
                    # For now, just monitor the file and show basic progress
                    output_file_path = job.output_file
                    last_size = 0
                    stall_count = 0
                    
                    while process.poll() is None:
                        try:
                            if os.path.exists(output_file_path):
                                current_size = os.path.getsize(output_file_path)
                                if current_size > last_size:
                                    # File is growing, estimate progress
                                    # Very rough estimate: assume ~60MB per minute of video
                                    estimated_total_size = total_frames * 40000  # Very rough bytes per frame
                                    if estimated_total_size > 0:
                                        progress = min((current_size / estimated_total_size) * 100, 95.0)
                                        
                                        # Calculate FPS based on frames processed over time
                                        elapsed_time = time.time() - start_time
                                        if elapsed_time > 0:
                                            current_frames = int((current_size / estimated_total_size) * total_frames)
                                            calculated_fps = current_frames / elapsed_time if elapsed_time > 0 else 0
                                        else:
                                            current_frames = 0
                                            calculated_fps = 0
                                        
                                        with self.lock:
                                            job.progress = progress
                                            job.current_frame = current_frames
                                            job.current_fps = calculated_fps
                                            self.save_queue()
                                        
                                        self.logger.info(f"TBC export progress: ~{progress:.1f}% (file size: {current_size // 1024 // 1024}MB)")
                                    
                                    last_size = current_size
                                    stall_count = 0
                                else:
                                    stall_count += 1
                                    if stall_count > 10:  # File hasn't grown in 10 seconds
                                        break
                            
                            time.sleep(1)  # Check every second
                            
                        except Exception as e:
                            self.logger.debug(f"Error monitoring file size: {e}")
                            time.sleep(1)
                else:
                    self.logger.warning("Could not determine total frames for progress monitoring")
            
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
                
                # Update progress during processing
                with self.lock:
                    job.progress = 20.0
                    self.save_queue()
                
                # Run the subprocess with proper output capture
                process = subprocess.Popen(
                    alignment_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Monitor the process and log output (but don't print to console)
                stdout_lines = []
                stderr_lines = []
                
                # Read output without blocking the main interface
                while True:
                    return_code = process.poll()
                    
                    # Read available output
                    try:
                        stdout_line = process.stdout.readline()
                        if stdout_line:
                            stdout_lines.append(stdout_line.strip())
                            self.logger.debug(f"Alignment stdout: {stdout_line.strip()}")
                            
                            # Update progress based on output patterns
                            if 'Starting VHS audio alignment' in stdout_line:
                                with self.lock:
                                    job.progress = 30.0
                                    self.save_queue()
                            elif 'Running alignment pipeline' in stdout_line:
                                with self.lock:
                                    job.progress = 50.0
                                    self.save_queue()
                            elif 'Audio alignment completed successfully' in stdout_line:
                                with self.lock:
                                    job.progress = 90.0
                                    self.save_queue()
                        
                        stderr_line = process.stderr.readline()
                        if stderr_line:
                            stderr_lines.append(stderr_line.strip())
                            self.logger.debug(f"Alignment stderr: {stderr_line.strip()}")
                    
                    except Exception as e:
                        self.logger.debug(f"Error reading process output: {e}")
                    
                    # Check if process has finished
                    if return_code is not None:
                        break
                    
                    # Small delay to avoid busy waiting
                    time.sleep(0.1)
                
                # Read any remaining output
                try:
                    remaining_stdout, remaining_stderr = process.communicate(timeout=5)
                    if remaining_stdout:
                        stdout_lines.extend(remaining_stdout.strip().split('\n'))
                    if remaining_stderr:
                        stderr_lines.extend(remaining_stderr.strip().split('\n'))
                except subprocess.TimeoutExpired:
                    self.logger.warning("Timeout waiting for remaining process output")
                
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
                    if isinstance(result, str) and result.endswith('_aligned.wav'):
                        # The function returned an aligned audio file path
                        if os.path.exists(result) and os.path.getsize(result) > 0:
                            # If the result path is different from expected output, move/copy it
                            if result != aligned_output:
                                import shutil
                                shutil.move(result, aligned_output)
                                self.logger.info(f"Moved aligned audio from {result} to {aligned_output}")
                            
                            file_size = os.path.getsize(aligned_output) / (1024*1024)  # MB
                            self.logger.info(f"Audio alignment completed successfully: {aligned_output} ({file_size:.1f} MB)")
                            
                            # Set final progress
                            with self.lock:
                                job.progress = 100.0
                                self.save_queue()
                            
                            return True
                        else:
                            self.logger.error(f"Aligned audio file not created or empty: {result}")
                            job.error_message = f"Aligned audio file not created: {result}"
                            return False
                    
                    elif isinstance(result, (int, float)):
                        # The function returned an offset value
                        self.logger.info(f"Audio alignment analysis completed with offset: {result:.3f} seconds")
                        
                        # For workflow purposes, we need to create an output file
                        # This could be a metadata file or we could copy the original with metadata
                        import shutil
                        shutil.copy2(audio_file, aligned_output)
                        
                        # Create a metadata file alongside the aligned audio
                        metadata_file = aligned_output.replace('.wav', '_align_info.json')
                        metadata = {
                            'offset_seconds': result,
                            'original_audio': audio_file,
                            'tbc_json': tbc_json_file,
                            'alignment_timestamp': datetime.now().isoformat()
                        }
                        
                        with open(metadata_file, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        
                        self.logger.info(f"Audio alignment metadata saved: {metadata_file}")
                        
                        # Set final progress
                        with self.lock:
                            job.progress = 100.0
                            self.save_queue()
                        
                        return True
                    
                    else:
                        self.logger.info(f"Audio alignment completed with result: {result}")
                        # For other result types, assume success if we got something
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
                # Encode audio as FLAC for archival quality
                ffmpeg_cmd.extend(['-c:a', 'flac'])
                
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
            
            # Run FFmpeg process with simple subprocess handling
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.logger.info(f"Started FFmpeg process with PID: {process.pid}")
            
            # Monitor FFmpeg output for progress
            stderr_lines = []
            
            while True:
                return_code = process.poll()
                
                # Read stderr output from FFmpeg
                try:
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        stderr_lines.append(stderr_line.strip())
                        self.logger.debug(f"FFmpeg stderr: {stderr_line.strip()}")
                        
                        # Look for progress indicators in FFmpeg output
                        if 'time=' in stderr_line or 'frame=' in stderr_line:
                            # Update progress occasionally
                            current_time = time.time()
                            try:
                                with self.lock:
                                    job.progress = min(job.progress + 2.0, 85.0)
                            except Exception:
                                pass  # Continue if we can't update progress
                
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
    
    def save_queue(self):
        """Save queue to persistent storage"""
        try:
            data = {
                "max_concurrent_jobs": self.max_concurrent_jobs,
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
        """Terminate the process for a running job"""
        try:
            if job_id in self.job_processes:
                process = self.job_processes[job_id]
                self.logger.info(f"Terminating process {process.pid} for job {job_id}")
                
                # Try graceful termination first
                try:
                    process.terminate()
                    # Wait up to 5 seconds for graceful shutdown
                    try:
                        process.wait(timeout=5)
                        self.logger.info(f"Process {process.pid} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful termination didn't work
                        self.logger.warning(f"Process {process.pid} didn't terminate gracefully, killing forcefully")
                        process.kill()
                        process.wait()  # Wait for kill to complete
                        self.logger.info(f"Process {process.pid} killed forcefully")
                        
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
                        # Clean failed or cancelled jobs only - do NOT clean truly running jobs
                        # as that would interfere with the ability to stop them properly
                        if (job.status == JobStatus.FAILED or 
                            job.status == JobStatus.CANCELLED):
                            
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
                            self.logger.warning(f"Cannot clean running job {job_id}")
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
