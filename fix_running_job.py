#!/usr/bin/env python3
"""
Fix the currently running job's total_frames so progress can be calculated
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_queue_manager import JobQueueManager, JobStatus
import time

def fix_running_job():
    print("=== Fix Running Job Total Frames ===")
    
    # Initialize job manager
    job_manager = JobQueueManager()
    
    # Get running jobs
    running_jobs = job_manager.get_jobs_nonblocking(JobStatus.RUNNING)
    
    if not running_jobs:
        print("No running jobs found")
        return
    
    for job in running_jobs:
        print(f"Found running job: {job.job_id}")
        print(f"  Current total_frames: {job.total_frames}")
        
        if job.total_frames == 0 and job.job_type == "tbc-export":
            # Set the correct total frames from the log output
            correct_total_frames = 142289  # From the log: "Total Frames: 142289"
            
            print(f"  Fixing total_frames to: {correct_total_frames}")
            
            with job_manager.lock:
                job.total_frames = correct_total_frames
                job_manager.save_queue()
            
            print("  ✓ Fixed!")
        else:
            print("  Job already has total_frames set or is not tbc-export")

if __name__ == "__main__":
    fix_running_job()
