#!/usr/bin/env python3
"""
Shared Progress Display Utilities
Extracted from job_queue_display.py to provide reusable progress monitoring components.

IMPORTANT: This uses the existing shared components to avoid duplicating functionality.
DO NOT reimplement existing functionality - reuse these utilities across the system.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

# Import job queue components for progress extraction
try:
    from job_queue_manager import get_job_queue_manager, JobStatus, QueuedJob
    JOB_QUEUE_AVAILABLE = True
except ImportError:
    JOB_QUEUE_AVAILABLE = False

# Import parallel decoder for frame counting utilities
try:
    from parallel_vhs_decode import ParallelVHSDecoder
    PARALLEL_DECODE_AVAILABLE = True
except ImportError:
    PARALLEL_DECODE_AVAILABLE = False
    ParallelVHSDecoder = None


class ProgressDisplayUtils:
    """
    Shared progress display utilities extracted from job_queue_display.py
    
    PURPOSE: Provides reusable progress bar rendering, time formatting, and job progress
    extraction functionality for unified display across the workflow control centre.
    
    USAGE: This component provides standardised progress monitoring and should be used
    whenever progress bars, ETA calculations, or job progress data is needed.
    DO NOT reimplement this functionality.
    
    EXAMPLES:
    Basic progress bar:
    >>> progress_bar = ProgressDisplayUtils.create_progress_bar(75.5)
    >>> print(progress_bar)  # "███████████████░░░░░"
    
    Time formatting:
    >>> eta_text = ProgressDisplayUtils.format_time(3725)
    >>> print(eta_text)  # "1h 2m"
    
    Job progress extraction:
    >>> job_manager = get_job_queue_manager()
    >>> progress_info = ProgressDisplayUtils.extract_job_progress_info(
    ...     job_manager, "Metallica1", "vhs-decode")
    
    INTEGRATION:
    This component integrates with:
    - job_queue_manager.py for job status and progress data
    - parallel_vhs_decode.py for frame counting and time formatting
    - Rich library components for display formatting
    
    VERSION HISTORY:
    v1.0: Initial extraction from job_queue_display.py
    """
    
    # Cache for frame counts to avoid repeated JSON parsing
    _frame_count_cache: Dict[str, int] = {}
    
    @staticmethod
    def create_progress_bar(percentage: float, width: int = 20) -> str:
        """
        Create progress bar using exact logic from job_queue_display.py lines 173-175
        
        Args:
            percentage: Progress percentage (0-100)
            width: Width of progress bar in characters (default 20)
            
        Returns:
            Progress bar string using █ and ░ characters
        """
        if percentage < 0:
            percentage = 0
        elif percentage > 100:
            percentage = 100
            
        progress_chars = int(percentage / 5)  # 20 chars for 100%
        if width != 20:
            progress_chars = int((percentage / 100.0) * width)
            
        return "█" * progress_chars + "░" * (width - progress_chars)
    
    @staticmethod
    def format_time(seconds: int) -> str:
        """
        Format seconds as human-readable time using existing logic from job_queue_display.py lines 69-85
        
        Args:
            seconds: Time in seconds to format
            
        Returns:
            Human-readable time string (e.g., "1h 2m", "45s", "Unknown")
        """
        # Try to use parallel decoder's format_time method first
        if PARALLEL_DECODE_AVAILABLE:
            try:
                decoder = ParallelVHSDecoder()
                if hasattr(decoder, 'format_time'):
                    return decoder.format_time(seconds)
            except Exception:
                pass  # Fall back to our implementation
        
        # Fallback implementation from job_queue_display.py
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
    def extract_job_progress_info(job_manager, project_name: str, step_type: str) -> Optional[Dict[str, Any]]:
        """
        Extract real-time progress information from running jobs using logic from job_queue_display.py lines 179-224
        
        Args:
            job_manager: Job queue manager instance
            project_name: Name of project to find jobs for
            step_type: Type of job step (e.g., "vhs-decode", "tbc-export")
            
        Returns:
            Dictionary with progress information or None if no matching running job found:
            {
                'percentage': float,      # Progress percentage (0-100)
                'fps': Optional[float],   # Current processing FPS
                'eta_seconds': Optional[int],  # Estimated seconds remaining
                'runtime_seconds': float, # How long job has been running
                'current_frame': int,     # Current frame number
                'total_frames': int       # Total frames to process
            }
        """
        # Debug logging to file
        def debug_log(message: str):
            from datetime import datetime
            timestamp = datetime.now().strftime('%H:%M:%S')
            try:
                with open('workflow_debug.log', 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] PROGRESS_UTILS: {message}\n")
            except Exception:
                pass
        
        debug_log(f"extract_job_progress_info called with project='{project_name}', step_type='{step_type}'")
        
        if not job_manager:
            debug_log("No job manager provided")
            return None
            
        try:
            jobs = job_manager.get_jobs()
            debug_log(f"Retrieved {len(jobs) if jobs else 0} total jobs from manager")
        except Exception as e:
            debug_log(f"Exception getting jobs: {e}")
            return None
            
        for i, job in enumerate(jobs):
            debug_log(f"Job {i}: status={getattr(job, 'status', 'no_status')}, job_type={getattr(job, 'job_type', 'no_job_type')}, input_file={getattr(job, 'input_file', 'no_input_file')[:50]}...")
            
            # Debug: Check each condition individually for RUNNING jobs
            if hasattr(job, 'status') and job.status == JobStatus.RUNNING:
                debug_log(f"FOUND RUNNING JOB {i}: job_type={getattr(job, 'job_type', 'N/A')}, looking_for={step_type}, project_in_file={project_name in getattr(job, 'input_file', '')}, input_file={getattr(job, 'input_file', 'N/A')[:50]}...")
                
                # Check each matching condition
                if hasattr(job, 'job_type') and job.job_type == step_type:
                    debug_log(f"  - Job type matches: {step_type}")
                    if hasattr(job, 'input_file') and project_name in job.input_file:
                        debug_log(f"  - Project name found in input file")
                    else:
                        debug_log(f"  - Project name NOT found in input file: {getattr(job, 'input_file', 'N/A')}")
                else:
                    debug_log(f"  - Job type does NOT match: {getattr(job, 'job_type', 'N/A')} != {step_type}")
            
            # Match running jobs for this project and step type
            # Also include recently started jobs that might not show as RUNNING yet
            # But EXCLUDE clearly failed/completed jobs to avoid stuck displays
            is_eligible_for_progress = False
            
            if hasattr(job, 'status'):
                # Definitely show running jobs
                if job.status == JobStatus.RUNNING:
                    is_eligible_for_progress = True
                # Also show recently queued jobs that might be starting
                elif job.status == JobStatus.QUEUED and hasattr(job, 'created_at'):
                    if job.created_at and (datetime.now() - job.created_at) < timedelta(minutes=1):
                        is_eligible_for_progress = True
                # EXCLUDE failed jobs with 100% progress (these are the stuck ones we want to avoid)
                elif job.status == JobStatus.FAILED and hasattr(job, 'progress') and job.progress >= 100:
                    is_eligible_for_progress = False
                # EXCLUDE failed jobs with 0% progress (these are likely cancelled test jobs)
                elif job.status == JobStatus.FAILED and hasattr(job, 'progress') and job.progress <= 0:
                    is_eligible_for_progress = False
                # EXCLUDE completed jobs (these are done)
                elif job.status == JobStatus.COMPLETED:
                    is_eligible_for_progress = False
            
            if (is_eligible_for_progress and 
                hasattr(job, 'job_type') and
                job.job_type == step_type and 
                hasattr(job, 'input_file') and
                project_name in job.input_file):
                
                # Check if this job has been cleaned - if so, hide progress bars
                if hasattr(job, 'parameters') and job.parameters and job.parameters.get('_progress_cleaned', False):
                    debug_log(f"Job {job.job_id if hasattr(job, 'job_id') else 'no_id'} has been cleaned - hiding progress display")
                    continue
                
                debug_log(f"Found matching RUNNING job: {job.job_id if hasattr(job, 'job_id') else 'no_id'} for {project_name}/{step_type}")
                
                # Only process jobs that have been running for at least 2 seconds
                if not hasattr(job, 'started_at') or not job.started_at:
                    debug_log(f"  - SKIPPING: No started_at timestamp")
                    continue
                    
                runtime = datetime.now() - job.started_at
                runtime_seconds = runtime.total_seconds()
                debug_log(f"  - Runtime: {runtime_seconds:.1f} seconds")
                
                if runtime_seconds <= 2:
                    debug_log(f"  - SKIPPING: Runtime too short ({runtime_seconds:.1f}s <= 2s)")
                    continue
                    
                # Get basic progress info
                progress_percentage = getattr(job, 'progress', 0)
                debug_log(f"  - Progress: {progress_percentage}%")
                # For truly running jobs, we still want to show them even with 0% progress
                # But skip if it's been running for more than 5 minutes without any progress
                if progress_percentage <= 0 and runtime_seconds > 300:  # 5 minutes
                    debug_log(f"  - SKIPPING: Long-running job with no progress ({progress_percentage}%, {runtime_seconds:.1f}s)")
                    continue
                
                # Calculate FPS and frame information
                fps = None
                current_frame = 0
                total_frames = 0
                eta_seconds = None
                
                # For TBC export jobs, use real-time FPS if available
                if step_type == "tbc-export":
                    if hasattr(job, 'current_fps') and hasattr(job, 'total_frames'):
                        fps = getattr(job, 'current_fps', 0)
                        total_frames = getattr(job, 'total_frames', 0)
                        current_frame = getattr(job, 'current_frame', 0)
                        
                        if fps > 0 and total_frames > 0 and current_frame > 0:
                            remaining_frames = total_frames - current_frame
                            eta_seconds = int(remaining_frames / fps)
                
                # For VHS decode jobs, calculate from JSON metadata and progress
                elif step_type == "vhs-decode":
                    total_frames = ProgressDisplayUtils._get_total_frames_for_job(job)
                    
                    if total_frames > 0:
                        current_frame = int((progress_percentage / 100.0) * total_frames)
                        
                        if current_frame > 0 and runtime_seconds > 0:
                            # Calculate processing FPS
                            fps = current_frame / runtime_seconds
                            
                            # Calculate ETA (only after 30 seconds for stability)
                            if runtime_seconds > 30 and fps > 0:
                                remaining_frames = total_frames - current_frame
                                eta_seconds = int(remaining_frames / fps)
                
                # Fallback ETA calculation using progress rate
                if eta_seconds is None and runtime_seconds > 30 and progress_percentage > 0:
                    progress_rate = progress_percentage / runtime_seconds
                    if progress_rate > 0:
                        remaining_progress = 100 - progress_percentage
                        eta_seconds = int(remaining_progress / progress_rate)
                
                return {
                    'percentage': progress_percentage,
                    'fps': fps,
                    'eta_seconds': eta_seconds,
                    'runtime_seconds': runtime_seconds,
                    'current_frame': current_frame,
                    'total_frames': total_frames
                }
        
        debug_log(f"No matching RUNNING job found for project='{project_name}', step_type='{step_type}'")
        return None
    
    @staticmethod
    def _get_total_frames_for_job(job) -> int:
        """
        Get total frame count for a job using JSON metadata with caching
        Extracted from job_queue_display.py lines 49-67
        
        Args:
            job: QueuedJob instance
            
        Returns:
            Total frame count or 0 if cannot be determined
        """
        if not hasattr(job, 'input_file') or not hasattr(job, 'parameters'):
            return 0
            
        # Create cache key
        video_standard = 'pal'
        if hasattr(job, 'parameters') and job.parameters:
            video_standard = job.parameters.get('video_standard', 'pal')
        cache_key = f"{job.input_file}_{video_standard}"
        
        # Check cache first
        if cache_key in ProgressDisplayUtils._frame_count_cache:
            return ProgressDisplayUtils._frame_count_cache[cache_key]
        
        total_frames = 0
        
        # Use parallel decoder for frame counting if available
        if PARALLEL_DECODE_AVAILABLE and job.job_type == "vhs-decode":
            try:
                decoder = ParallelVHSDecoder()
                if hasattr(decoder, 'get_frame_count_from_json'):
                    total_frames = decoder.get_frame_count_from_json(
                        job.input_file,
                        video_standard
                    )
                    # Cache the result
                    ProgressDisplayUtils._frame_count_cache[cache_key] = total_frames
            except Exception:
                pass  # Fallback to 0 if JSON reading fails
        
        return total_frames
    
    @staticmethod
    def format_progress_text(progress_info: Dict[str, Any]) -> str:
        """
        Format progress information into display text
        
        Args:
            progress_info: Progress information dictionary from extract_job_progress_info()
            
        Returns:
            Formatted progress text suitable for display
        """
        if not progress_info:
            return "Waiting..."
        
        percentage = progress_info.get('percentage', 0)
        fps = progress_info.get('fps')
        eta_seconds = progress_info.get('eta_seconds')
        
        # Build progress text components
        text_parts = [f"{percentage:.1f}%"]
        
        if fps and fps > 0:
            text_parts.append(f"{fps:.1f}fps")
        
        if eta_seconds and eta_seconds > 0:
            eta_text = ProgressDisplayUtils.format_time(eta_seconds)
            text_parts.append(f"ETA {eta_text}")
        
        return " ".join(text_parts)
    
    @staticmethod
    def get_step_job_type_mapping() -> Dict[str, str]:
        """
        Get mapping from workflow steps to job types
        
        Returns:
            Dictionary mapping step names to job types
        """
        return {
            'decode': 'vhs-decode',
            'export': 'tbc-export',
            'compress': 'tbc-compress',  # Future implementation
            'align': 'audio-align',      # Future implementation
            'final': 'final-mux'         # Future implementation
        }
    
    @staticmethod
    def clear_frame_count_cache():
        """Clear the frame count cache to free memory"""
        ProgressDisplayUtils._frame_count_cache.clear()


# Compatibility functions for easy integration
def create_progress_bar(percentage: float, width: int = 20) -> str:
    """Convenience function for creating progress bars"""
    return ProgressDisplayUtils.create_progress_bar(percentage, width)


def format_time(seconds: int) -> str:
    """Convenience function for formatting time"""
    return ProgressDisplayUtils.format_time(seconds)


def extract_job_progress_info(job_manager, project_name: str, step_type: str) -> Optional[Dict[str, Any]]:
    """Convenience function for extracting job progress info"""
    return ProgressDisplayUtils.extract_job_progress_info(job_manager, project_name, step_type)


def extract_specific_job_progress_info(job_manager, project_name: str, step_type: str) -> Optional[Dict[str, Any]]:
    """
    Extract progress information for the SPECIFIC current job for a project+step combination.
    
    This function finds the most relevant job for the given project and step:
    1. First priority: RUNNING jobs
    2. Second priority: Most recently created job (regardless of status)
    
    Args:
        job_manager: Job queue manager instance  
        project_name: Name of project to find jobs for
        step_type: Type of job step (e.g., "vhs-decode", "tbc-export")
        
    Returns:
        Dictionary with progress information or None if no job found for this specific project+step
    """
    from datetime import datetime
    
    # Debug logging
    def debug_log(message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        try:
            with open('workflow_debug.log', 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] SPECIFIC_PROGRESS: {message}\n")
        except Exception:
            pass
    
    debug_log(f"Finding specific job for project='{project_name}', step_type='{step_type}'")
    
    if not job_manager:
        debug_log("No job manager provided")
        return None
        
    try:
        jobs = job_manager.get_jobs()
        debug_log(f"Retrieved {len(jobs) if jobs else 0} total jobs from manager")
    except Exception as e:
        debug_log(f"Exception getting jobs: {e}")
        return None
    
    # Find all jobs matching this project+step combination
    matching_jobs = []
    for job in jobs:
        if (hasattr(job, 'project_name') and hasattr(job, 'job_type') and
            job.project_name == project_name and job.job_type == step_type):
            
            # Check if this job has been cleaned - if so, skip it
            if hasattr(job, 'parameters') and job.parameters and job.parameters.get('_progress_cleaned', False):
                debug_log(f"Job {getattr(job, 'job_id', 'unknown')} has been cleaned - skipping")
                continue
                
            matching_jobs.append(job)
    
    debug_log(f"Found {len(matching_jobs)} jobs matching project+step")
    
    if not matching_jobs:
        debug_log("No matching jobs found")
        return None
    
    # Priority 1: Find running jobs
    running_jobs = [job for job in matching_jobs if hasattr(job, 'status') and job.status == JobStatus.RUNNING]
    
    if running_jobs:
        # Use the most recently started running job
        target_job = max(running_jobs, key=lambda j: j.started_at if hasattr(j, 'started_at') and j.started_at else datetime.min)
        debug_log(f"Using running job: {getattr(target_job, 'job_id', 'unknown')}") 
    else:
        # Priority 2: Use the most recently created job (any status)
        target_job = max(matching_jobs, key=lambda j: j.created_at if hasattr(j, 'created_at') and j.created_at else datetime.min)
        debug_log(f"No running jobs, using most recent job: {getattr(target_job, 'job_id', 'unknown')} (status: {getattr(target_job, 'status', 'unknown')})")
    
    # Only show progress for RUNNING jobs or jobs with meaningful progress
    if hasattr(target_job, 'status'):
        if target_job.status == JobStatus.RUNNING:
            debug_log("Job is running, extracting progress")
        elif hasattr(target_job, 'progress') and target_job.progress > 0:
            debug_log(f"Job is not running but has progress: {target_job.progress}%")
        else:
            debug_log(f"Job is not running and has no progress (status: {target_job.status}, progress: {getattr(target_job, 'progress', 0)}%)")
            return None
    
    # Extract progress info from the target job
    if not hasattr(target_job, 'started_at') or not target_job.started_at:
        debug_log("No started_at timestamp")
        return None
        
    runtime = datetime.now() - target_job.started_at
    runtime_seconds = runtime.total_seconds()
    
    progress_percentage = getattr(target_job, 'progress', 0)
    fps = getattr(target_job, 'current_fps', None)
    current_frame = getattr(target_job, 'current_frame', 0)
    total_frames = getattr(target_job, 'total_frames', 0)
    
    debug_log(f"Progress: {progress_percentage}%, FPS: {fps}, Frames: {current_frame}/{total_frames}")
    
    # Calculate ETA
    eta_seconds = None
    if fps and fps > 0 and total_frames > 0 and current_frame > 0:
        remaining_frames = total_frames - current_frame
        eta_seconds = int(remaining_frames / fps)
    
    return {
        'percentage': progress_percentage,
        'fps': fps,
        'eta_seconds': eta_seconds,
        'runtime_seconds': runtime_seconds,
        'current_frame': current_frame,
        'total_frames': total_frames
    }
