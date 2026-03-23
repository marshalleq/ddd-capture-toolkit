#!/usr/bin/env python3
"""
Debug script to investigate progress metadata of running jobs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_queue_manager import JobQueueManager
from project_discovery import ProjectDiscovery
from shared.progress_display_utils import extract_job_progress_info
import time

def debug_job_progress():
    print("=== Debug: Job Progress Metadata ===")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize job manager
    job_manager = JobQueueManager()
    
    # Get all jobs
    all_jobs = job_manager.get_jobs_nonblocking()
    print(f"Total jobs found: {len(all_jobs)}")
    
    # Filter for running and recent jobs
    running_jobs = [job for job in all_jobs if hasattr(job, 'status') and 
                   (str(job.status).lower() in ['running', 'processing'] or
                    ('running' in str(job.status).lower()) or
                    ('processing' in str(job.status).lower()))]
    
    print(f"Jobs with running/processing status: {len(running_jobs)}")
    
    # Also check failed jobs with recent activity (our temporary fix)
    from job_queue_manager import JobStatus
    recent_failed_jobs = []
    current_time = time.time()
    
    for job in all_jobs:
        if hasattr(job, 'status') and job.status == JobStatus.FAILED:
            if hasattr(job, 'progress') and job.progress and job.progress > 0:
                if hasattr(job, 'started_at') and job.started_at:
                    time_since_start = current_time - job.started_at.timestamp()
                    if time_since_start < 3600:  # Within 1 hour
                        recent_failed_jobs.append(job)
    
    print(f"Recent failed jobs with progress: {len(recent_failed_jobs)}")
    
    # Combine both sets
    candidate_jobs = running_jobs + recent_failed_jobs
    print(f"Total candidate jobs to examine: {len(candidate_jobs)}")
    print()
    
    if not candidate_jobs:
        print("No running or recently failed jobs with progress found!")
        return
    
    # Examine each candidate job in detail
    for i, job in enumerate(candidate_jobs):
        print(f"=== Job {i+1} ===")
        print(f"Job ID: {getattr(job, 'job_id', 'N/A')}")
        print(f"Status: {getattr(job, 'status', 'N/A')}")
        print(f"Job Type: {getattr(job, 'job_type', 'N/A')}")
        print(f"Project Name: {getattr(job, 'project_name', 'N/A')}")
        print(f"Input File: {getattr(job, 'input_file', 'N/A')}")
        
        # Progress-related attributes
        print(f"Progress: {getattr(job, 'progress', 'N/A')}")
        print(f"Current Frame: {getattr(job, 'current_frame', 'N/A')}")
        print(f"Total Frames: {getattr(job, 'total_frames', 'N/A')}")
        print(f"Current FPS: {getattr(job, 'current_fps', 'N/A')}")
        print(f"Started At: {getattr(job, 'started_at', 'N/A')}")
        
        # Calculate runtime if started_at exists
        if hasattr(job, 'started_at') and job.started_at:
            runtime = current_time - job.started_at.timestamp()
            print(f"Runtime: {runtime:.1f} seconds")
        
        # Test progress extraction
        print("\n--- Testing progress extraction ---")
        progress_info = extract_job_progress_info(job, debug=True)
        if progress_info:
            print(f"Extracted progress info: {progress_info}")
        else:
            print("Progress extraction returned None")
        
        print("-" * 50)
        print()

if __name__ == "__main__":
    debug_job_progress()
