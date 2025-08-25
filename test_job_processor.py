#!/usr/bin/env python3
"""
Test to investigate job processor behavior and potential hanging
"""

import os
import time
import threading
from job_queue_manager import get_job_queue_manager

def test_job_processor():
    """Test the job processor behavior"""
    print("JOB PROCESSOR INVESTIGATION")
    print("=" * 30)
    
    # Get job manager
    print("Getting job manager...")
    job_manager = get_job_queue_manager()
    
    # Check current status
    print("Current queue status:")
    status = job_manager.get_queue_status()
    print(f"  Total jobs: {status['total_jobs']}")
    print(f"  Running: {status['running']}")
    print(f"  Queued: {status['queued']}")
    print(f"  Failed: {status['failed']}")
    print(f"  Processor running: {status['processor_running']}")
    
    # Get the jobs that are "running"
    jobs = job_manager.get_jobs()
    running_jobs = [job for job in jobs if str(job.status).lower() == 'running']
    
    if running_jobs:
        print(f"\nFound {len(running_jobs)} 'running' jobs:")
        for job in running_jobs:
            print(f"  Job ID: {job.job_id}")
            print(f"  Type: {job.job_type}")
            print(f"  Started: {job.started_at}")
            print(f"  Progress: {job.progress}")
            print(f"  Input: {job.input_file}")
            print(f"  Output: {job.output_file}")
            
            # Check if files exist
            input_exists = os.path.exists(job.input_file) if job.input_file else False
            output_exists = os.path.exists(job.output_file) if job.output_file else False
            print(f"  Input file exists: {input_exists}")
            print(f"  Output file exists: {output_exists}")
            print()
    
    # Test what happens when we try to manually process one of these jobs
    if running_jobs:
        job = running_jobs[0]
        print(f"Attempting to understand why job {job.job_id} is stuck...")
        
        if job.job_type == "final-mux":
            print("This is a final-mux job. Checking parameters:")
            params = job.parameters
            video_file = params.get('video_file', 'Unknown')
            audio_file = params.get('audio_file', 'Unknown')
            final_output = params.get('final_output', 'Unknown')
            
            print(f"  Video file: {video_file}")
            print(f"  Audio file: {audio_file}")
            print(f"  Final output: {final_output}")
            
            # Check file existence
            video_exists = os.path.exists(video_file) if video_file != 'Unknown' else False
            audio_exists = os.path.exists(audio_file) if audio_file != 'Unknown' else False
            
            print(f"  Video exists: {video_exists}")
            print(f"  Audio exists: {audio_exists}")
            
            if not video_exists:
                print("  --> Job will fail because video file doesn't exist")
            elif not audio_exists and audio_file != 'Unknown':
                print("  --> Job will fail because audio file doesn't exist")
            else:
                print("  --> Job should be able to run (files exist)")
    
    # Check if there are any background threads running
    print(f"\nCurrent thread count: {threading.active_count()}")
    print("Active threads:")
    for thread in threading.enumerate():
        print(f"  {thread.name}: {thread.is_alive()}")
    
    # Test stopping and restarting the processor
    print("\nTesting processor stop/restart...")
    print("Stopping processor...")
    job_manager.stop_processor()
    time.sleep(1)
    
    status_after_stop = job_manager.get_queue_status()
    print(f"After stop - processor running: {status_after_stop['processor_running']}")
    
    print("Starting processor...")
    job_manager.start_processor()
    time.sleep(1)
    
    status_after_start = job_manager.get_queue_status()
    print(f"After restart - processor running: {status_after_start['processor_running']}")
    
    # Wait a bit to see if the stuck job changes status
    print("\nMonitoring for 5 seconds to see if stuck job gets processed...")
    for i in range(5):
        time.sleep(1)
        current_status = job_manager.get_queue_status_nonblocking()
        if current_status:
            print(f"  Second {i+1}: {current_status['running']} running, {current_status['queued']} queued, {current_status['failed']} failed")
        else:
            print(f"  Second {i+1}: Status unavailable")
    
    print("\nInvestigation completed!")

if __name__ == "__main__":
    test_job_processor()
