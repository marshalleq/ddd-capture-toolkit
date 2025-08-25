#!/usr/bin/env python3
"""
Debug script to reproduce the UI freeze when starting final mux job
"""

import time
import threading
from job_queue_manager import get_job_queue_manager

def monitor_job_progress(job_id):
    """Monitor a job's progress in a separate thread"""
    job_manager = get_job_queue_manager()
    
    for _ in range(30):  # Monitor for 30 seconds max
        time.sleep(1)
        
        # Try to get job status
        jobs = job_manager.get_jobs_nonblocking(timeout=0.1)
        if jobs is None:
            print("MONITOR: Job manager locked, cannot get status")
            continue
        
        # Find our job
        our_job = None
        for job in jobs:
            if hasattr(job, 'job_id') and job.job_id == job_id:
                our_job = job
                break
        
        if our_job:
            status = getattr(our_job, 'status', 'unknown')
            progress = getattr(our_job, 'progress', 0)
            print(f"MONITOR: Job {job_id} - Status: {status}, Progress: {progress}%")
            
            if str(status).lower() in ['completed', 'failed', 'cancelled']:
                break
        else:
            print(f"MONITOR: Job {job_id} not found")
            break

def main():
    print("DEBUG: Testing UI freeze scenario...")
    
    job_manager = get_job_queue_manager()
    
    # Create a real final-mux job that will actually run
    import os
    capture_base = os.environ.get('CAPTURE_DIR', '/path/to/captures')
    video_file = os.path.join(capture_base, "test_video.mkv")
    audio_file = os.path.join(capture_base, "test_audio.wav")
    output_file = "/tmp/test_final_debug.mkv"
    
    print(f"DEBUG: Video file exists: {os.path.exists(video_file)}")
    print(f"DEBUG: Audio file exists: {os.path.exists(audio_file)}")
    
    parameters = {
        'video_file': video_file,
        'audio_file': audio_file,
        'final_output': output_file,
        'overwrite': True
    }
    
    print("DEBUG: Submitting final-mux job...")
    start_time = time.time()
    
    job_id = job_manager.add_job_nonblocking(
        job_type="final-mux",
        input_file=video_file,
        output_file=output_file,
        parameters=parameters,
        priority=5,
        timeout=0.5
    )
    
    submission_time = time.time() - start_time
    print(f"DEBUG: Job submission took {submission_time:.3f} seconds")
    
    if not job_id:
        print("DEBUG: Job submission failed!")
        return
    
    print(f"DEBUG: Job submitted: {job_id}")
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_job_progress, args=(job_id,), daemon=True)
    monitor_thread.start()
    
    # Simulate what the workflow control centre does - frequent status checks
    print("DEBUG: Starting simulated UI refresh loop...")
    
    for i in range(60):  # Run for 60 seconds
        loop_start = time.time()
        
        # Try to get queue status (what the UI does)
        status = job_manager.get_queue_status_nonblocking(timeout=0.1)
        status_time = time.time() - loop_start
        
        if status is None:
            print(f"UI LOOP {i}: Status check TIMED OUT after {status_time:.3f}s - UI WOULD FREEZE HERE")
            break
        else:
            print(f"UI LOOP {i}: Status check OK ({status_time:.3f}s) - Running: {status.get('running', 0)}")
        
        # Try to get jobs (what the UI does for display)
        jobs_start = time.time()
        jobs = job_manager.get_jobs_nonblocking(timeout=0.1)
        jobs_time = time.time() - jobs_start
        
        if jobs is None:
            print(f"UI LOOP {i}: Jobs check TIMED OUT after {jobs_time:.3f}s - UI WOULD FREEZE HERE")
            break
        
        # Simulate UI refresh delay
        time.sleep(0.5)
    
    print("DEBUG: Test completed")

if __name__ == "__main__":
    import os
    main()
