#!/usr/bin/env python3
"""
Debug the clean command issue step by step
"""

import sys
import os
import time

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_clean_issue():
    """Debug why clean command isn't working in live interface"""
    from workflow_control_centre import WorkflowControlCentre
    
    print("Debugging clean command issue...")
    
    # Initialize the control centre exactly like the live interface
    control_centre = WorkflowControlCentre()
    
    # Refresh data like the live interface does
    print("Refreshing data...")
    control_centre.refresh_data()
    
    print(f"Found {len(control_centre.current_projects)} projects")
    print(f"Found {len(control_centre.current_jobs)} active jobs in UI cache")
    
    if control_centre.current_projects:
        project = control_centre.current_projects[0]
        print(f"Project 1: {project.name}")
    else:
        print("No projects found!")
        return
    
    # Now let's test the clean command logic step by step
    print("\n=== DEBUGGING CLEAN COMMAND STEP BY STEP ===")
    
    project_num = 1
    step_letter = 'e'
    project_idx = project_num - 1
    project = control_centre.current_projects[project_idx]
    
    print(f"Project: {project.name}")
    print(f"Step: {step_letter} (export)")
    
    # Map step letters to job types (same as in clean command)
    step_to_job_type = {
        'd': 'vhs-decode',
        'c': 'compress',
        'e': 'tbc-export',
        'a': 'audio-align',
        'f': 'final-mux'
    }
    
    job_type = step_to_job_type[step_letter]
    print(f"Looking for job_type: {job_type}")
    
    # Get jobs directly like clean command does
    if control_centre.job_manager:
        print("Getting jobs from job manager...")
        jobs = control_centre.job_manager.get_jobs_nonblocking(timeout=0.5)
        
        if jobs is None:
            print("ERROR: Job manager returned None (busy)")
            return
        else:
            print(f"Got {len(jobs)} jobs from job manager")
        
        # Look for matching jobs
        target_jobs = []
        all_matching_jobs = []
        
        print(f"\n=== ANALYZING {len(jobs)} JOBS ===")
        for i, job in enumerate(jobs):
            if hasattr(job, 'project_name') and hasattr(job, 'job_type') and hasattr(job, 'status'):
                job_project = getattr(job, 'project_name', 'N/A')
                job_type_attr = getattr(job, 'job_type', 'N/A')
                job_status = getattr(job, 'status', 'N/A')
                job_progress = getattr(job, 'progress', 0)
                job_id = getattr(job, 'job_id', 'N/A')
                
                # Check if it matches our project and job type
                matches_project = (job_project == project.name)
                matches_type = (job_type_attr == job_type)
                
                # Show details for all matching jobs, and first 10 of all jobs
                show_details = (i < 10) or matches_project or matches_type
                if show_details:
                    print(f"Job {i}: ID={job_id}, Project={job_project}, Type={job_type_attr}, Status={job_status}, Progress={job_progress}")
                    if matches_project or matches_type:
                        print(f"  Matches project? {matches_project} | Matches type? {matches_type}")
                
                if matches_project and matches_type:
                    all_matching_jobs.append(job)
                    job_status_str = str(job_status).lower()
                    
                    # Check if it's a target for cleaning
                    is_failed = 'failed' in job_status_str
                    is_stuck = (job_progress > 0 and 'running' not in job_status_str)
                    
                    print(f"  MATCHING JOB FOUND: Status={job_status_str}, Failed={is_failed}, Stuck={is_stuck}")
                    
                    if is_failed or is_stuck:
                        target_jobs.append(job)
                        print(f"  -> ADDED TO TARGET LIST")
            else:
                print(f"Job {i}: Missing required attributes")
        
        print(f"\nSUMMARY:")
        print(f"Total matching jobs for {project.name} + {job_type}: {len(all_matching_jobs)}")
        print(f"Target jobs for cleaning: {len(target_jobs)}")
        
        if target_jobs:
            print(f"\nTARGET JOBS:")
            for job in target_jobs:
                job_id = getattr(job, 'job_id', 'N/A')
                job_status = getattr(job, 'status', 'N/A')
                job_progress = getattr(job, 'progress', 0)
                print(f"  {job_id}: {job_status} ({job_progress}%)")
        
        # Test the actual cleaning
        if target_jobs:
            print(f"\n=== TESTING ACTUAL CLEANING ===")
            cleaned_count = 0
            for job in target_jobs[:3]:  # Test first 3 jobs only
                try:
                    job_id = getattr(job, 'job_id', None)
                    if job_id:
                        print(f"Attempting to clean job {job_id}...")
                        success = control_centre.job_manager._clean_job_progress(job_id)
                        print(f"  Result: {success}")
                        if success:
                            cleaned_count += 1
                    else:
                        print(f"  No job_id for job")
                except Exception as e:
                    print(f"  ERROR: {e}")
            
            print(f"Successfully cleaned: {cleaned_count} jobs")
        else:
            print("No target jobs to clean")
    else:
        print("No job manager available")

if __name__ == "__main__":
    debug_clean_issue()
