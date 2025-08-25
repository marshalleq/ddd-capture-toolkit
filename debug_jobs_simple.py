#!/usr/bin/env python3
"""
Simple debug script to show current job status
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_queue_manager import JobQueueManager, JobStatus
import time

def debug_jobs_simple():
    print("=== Simple Job Status Debug ===")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize job manager
    job_manager = JobQueueManager()
    
    # Get all jobs
    all_jobs = job_manager.get_jobs_nonblocking()
    print(f"Total jobs found: {len(all_jobs)}")
    print()
    
    # Group by status
    status_counts = {}
    for job in all_jobs:
        status = str(job.status) if hasattr(job, 'status') else 'Unknown'
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Jobs by status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    print()
    
    # Show most recent 5 jobs
    print("Most recent 5 jobs:")
    recent_jobs = sorted(all_jobs, key=lambda j: j.created_at if hasattr(j, 'created_at') else 0, reverse=True)[:5]
    
    for i, job in enumerate(recent_jobs):
        print(f"{i+1}. {job.job_id} - {job.status} - {job.job_type}")
        print(f"   Project: {job.project_name}")
        print(f"   Progress: {job.progress}%")
        print(f"   Created: {job.created_at}")
        print(f"   Started: {job.started_at}")
        if job.progress > 0:
            print(f"   ** HAS PROGRESS: {job.progress}% **")
        print()
    
    # Look specifically for jobs with progress > 0
    progress_jobs = [j for j in all_jobs if hasattr(j, 'progress') and j.progress > 0]
    if progress_jobs:
        print(f"Found {len(progress_jobs)} jobs with progress > 0:")
        for job in progress_jobs:
            print(f"  - {job.job_id}: {job.progress}% ({job.status})")
    else:
        print("No jobs found with progress > 0")

if __name__ == "__main__":
    debug_jobs_simple()
