#!/usr/bin/env python3
"""
Test starting a job and monitoring its progress display
"""

import sys
import os
import time

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_job_progress():
    """Test starting a job and monitoring progress"""
    from workflow_control_centre import WorkflowControlCentre
    from job_queue_manager import get_job_queue_manager, JobStatus
    from shared.progress_display_utils import ProgressDisplayUtils
    
    print("Testing job start and progress monitoring...")
    
    # Initialize components
    control_centre = WorkflowControlCentre()
    job_manager = get_job_queue_manager()
    
    # Refresh data
    control_centre.refresh_data()
    
    if not control_centre.current_projects:
        print("No projects found!")
        return
    
    project = control_centre.current_projects[0]
    print(f"Using project: {project.name}")
    
    # Start a force export job for project 1
    print("\nStarting 'force 1e' command...")
    control_centre.handle_command("force 1e")
    print(f"Command result: {control_centre.message}")
    
    # Wait a moment for job to start
    time.sleep(2)
    
    # Check for running jobs
    print("\n=== CHECKING FOR RUNNING JOBS ===")
    try:
        jobs = job_manager.get_jobs()
        running_jobs = [job for job in jobs if job.status == JobStatus.RUNNING]
        
        print(f"Found {len(running_jobs)} running jobs")
        
        for job in running_jobs:
            print(f"Running job: {job.job_id}")
            print(f"  Type: {job.job_type}")
            print(f"  Status: {job.status}")
            print(f"  Progress: {getattr(job, 'progress', 0)}%")
            print(f"  Input: {os.path.basename(job.input_file)}")
            
    except Exception as e:
        print(f"Error checking jobs: {e}")
        return
    
    # Test progress extraction
    print("\n=== TESTING PROGRESS EXTRACTION ===")
    
    for attempt in range(5):  # Try for 5 attempts over 10 seconds
        progress_info = ProgressDisplayUtils.extract_job_progress_info(
            job_manager, "Metallica1", "tbc-export"
        )
        
        print(f"Attempt {attempt + 1}: {progress_info}")
        
        if progress_info:
            # Test creating progress bar
            percentage = progress_info.get('percentage', 0)
            progress_bar = ProgressDisplayUtils.create_progress_bar(percentage, width=11)
            fps = progress_info.get('fps', 0)
            
            print(f"  Progress bar: {progress_bar}")
            print(f"  Percentage: {percentage}%")
            print(f"  FPS: {fps}")
            
            # This should show up in the workflow matrix now
            break
        
        time.sleep(2)
    
    print("\nNow check the workflow control centre - it should show progress for the Export step!")

if __name__ == "__main__":
    test_job_progress()
