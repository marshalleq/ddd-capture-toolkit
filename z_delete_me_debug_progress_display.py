#!/usr/bin/env python3
"""
Debug progress display for running jobs
"""

import sys
import os
import time

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_running_jobs():
    """Debug what's happening with running jobs and progress display"""
    from workflow_control_centre import WorkflowControlCentre
    from job_queue_manager import get_job_queue_manager, JobStatus
    
    print("Debugging running jobs and progress display...")
    
    # Initialize components
    control_centre = WorkflowControlCentre()
    job_manager = get_job_queue_manager()
    
    # Get all jobs and check their status
    try:
        jobs = job_manager.get_jobs()
        print(f"\n=== ALL JOBS ({len(jobs)}) ===")
        
        for i, job in enumerate(jobs):
            job_id = getattr(job, 'job_id', 'N/A')
            job_type = getattr(job, 'job_type', 'N/A')
            job_status = getattr(job, 'status', 'N/A')
            job_progress = getattr(job, 'progress', 0)
            project_name = getattr(job, 'project_name', 'Unknown')
            input_file = getattr(job, 'input_file', 'N/A')
            
            print(f"Job {i}: {job_id}")
            print(f"  Status: {job_status}")
            print(f"  Type: {job_type}")
            print(f"  Progress: {job_progress}%")
            print(f"  Project: {project_name}")
            print(f"  Input: {os.path.basename(input_file)}")
            
            # Check if it's a running tbc-export job
            if job_status == JobStatus.RUNNING and job_type == 'tbc-export':
                print(f"  *** THIS IS A RUNNING EXPORT JOB ***")
            
            print()
            
            # Only show first 10 jobs to avoid spam
            if i >= 9:
                print(f"... and {len(jobs) - 10} more jobs")
                break
                
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return
    
    # Test progress extraction specifically for Metallica1 tbc-export
    print("\n=== TESTING PROGRESS EXTRACTION ===")
    from shared.progress_display_utils import ProgressDisplayUtils
    
    progress_info = ProgressDisplayUtils.extract_job_progress_info(
        job_manager, "Metallica1", "tbc-export"
    )
    
    print(f"Progress info for Metallica1 tbc-export: {progress_info}")
    
    # Test with project status display
    print("\n=== TESTING PROJECT STATUS DISPLAY ===")
    control_centre.refresh_data()
    
    if control_centre.current_projects:
        project = control_centre.current_projects[0]
        print(f"Project: {project.name}")
        
        # Test enhanced status cell creation
        from workflow_analyzer import WorkflowStep, StepStatus
        from project_status_display import ProjectStatusDisplay, DisplayConfig
        
        display_config = DisplayConfig()
        project_display = ProjectStatusDisplay(
            control_centre.project_discovery,
            control_centre.workflow_analyzer, 
            display_config
        )
        
        enhanced_cell = project_display.create_enhanced_status_cell(
            project, WorkflowStep.EXPORT, StepStatus.PROCESSING
        )
        
        print(f"Enhanced status cell for export: {enhanced_cell}")

if __name__ == "__main__":
    print("Starting debug...")
    debug_running_jobs()
    print("\nNow start a job with 'force 1e' and run this again to see the running job...")
