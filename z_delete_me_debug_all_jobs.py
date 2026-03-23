#!/usr/bin/env python3
"""
Enhanced debug script to show all jobs and identify progress issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_queue_manager import JobQueueManager, JobStatus
from project_discovery import ProjectDiscovery
from shared.progress_display_utils import extract_job_progress_info
import time

def debug_all_jobs():
    print("=== Debug: All Jobs in Queue ===")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize job manager
    job_manager = JobQueueManager()
    
    # Get all jobs
    all_jobs = job_manager.get_jobs_nonblocking()
    print(f"Total jobs found: {len(all_jobs)}")
    print()
    
    if not all_jobs:
        print("No jobs found in queue!")
        return
    
    # Group jobs by status
    status_counts = {}
    for job in all_jobs:
        status = str(job.status) if hasattr(job, 'status') else 'Unknown'
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Jobs by status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    print()
    
    # Show recent jobs (last 10)
    print("=== Recent Jobs (last 10) ===")
    recent_jobs = sorted(all_jobs, key=lambda j: j.created_at if hasattr(j, 'created_at') else 0, reverse=True)[:10]
    
    for i, job in enumerate(recent_jobs):
        print(f"Job {i+1}:")
        print(f"  ID: {getattr(job, 'job_id', 'N/A')}")
        print(f"  Status: {getattr(job, 'status', 'N/A')}")
        print(f"  Type: {getattr(job, 'job_type', 'N/A')}")
        print(f"  Project: {getattr(job, 'project_name', 'N/A')}")
        print(f"  Progress: {getattr(job, 'progress', 'N/A')}")
        print(f"  Created: {getattr(job, 'created_at', 'N/A')}")
        print(f"  Started: {getattr(job, 'started_at', 'N/A')}")
        print(f"  Current Frame: {getattr(job, 'current_frame', 'N/A')}")
        print(f"  Total Frames: {getattr(job, 'total_frames', 'N/A')}")
        print(f"  Current FPS: {getattr(job, 'current_fps', 'N/A')}")
        
        # Test if this job would show progress
        progress_info = extract_job_progress_info(job, debug=False)
        print(f"  Progress Extract Result: {'YES' if progress_info else 'NO'}")
        
        print()
    
    # Look for jobs that might have progress but aren't detected
    print("=== Jobs with Progress > 0 ===")
    progressing_jobs = [job for job in all_jobs if hasattr(job, 'progress') and job.progress > 0]
    
    if progressing_jobs:
        for job in progressing_jobs:
            print(f"Job {job.job_id}:")
            print(f"  Status: {job.status}")
            print(f"  Progress: {job.progress}%")
            print(f"  Type: {job.job_type}")
            print(f"  Project: {job.project_name}")
            
            # Test progress extraction with debug
            print(f"  --- Progress Extraction Test ---")
            progress_info = extract_job_progress_info(job, debug=True)
            print(f"  Result: {progress_info}")
            print()
    else:
        print("No jobs with progress > 0 found")
    
    print("=== Jobs in RUNNING status ===")
    running_jobs = [job for job in all_jobs if hasattr(job, 'status') and job.status == JobStatus.RUNNING]
    
    if running_jobs:
        for job in running_jobs:
            print(f"Job {job.job_id}:")
            print(f"  Type: {job.job_type}")
            print(f"  Project: {job.project_name}")
            print(f"  Progress: {job.progress}%")
            print(f"  Started: {job.started_at}")
            print()
    else:
        print("No jobs in RUNNING status found")

if __name__ == "__main__":
    debug_all_jobs()
