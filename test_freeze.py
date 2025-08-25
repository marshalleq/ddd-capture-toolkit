#!/usr/bin/env python3
"""
Test script to isolate where the UI freezing occurs during workflow job submission
"""

import os
import sys
import time
import threading

def test_job_submission_freeze():
    """Test exactly where the freeze occurs during job submission"""
    print("Testing workflow job submission freeze...")
    
    try:
        # Import the workflow control centre
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        
        print("✓ Imported modules successfully")
        
        # Create a control centre instance
        control_centre = WorkflowControlCentre()
        print("✓ Created WorkflowControlCentre instance")
        
        # Get the first project if available
        control_centre.refresh_data()
        print(f"✓ Refreshed data - found {len(control_centre.current_projects)} projects")
        
        if not control_centre.current_projects:
            print("❌ No projects found - cannot test job submission")
            return
        
        project = control_centre.current_projects[0]
        print(f"✓ Using test project: {project.name}")
        
        # Test different stages of job submission
        print("\n=== Testing Job Submission Stages ===")
        
        print("1. Testing background thread creation...")
        start_time = time.time()
        
        # Create a simple background thread to see if threading itself is the issue
        def simple_background_task():
            print("  → Background thread started")
            time.sleep(1)
            print("  → Background thread completed")
        
        thread = threading.Thread(target=simple_background_task, daemon=True)
        thread.start()
        thread.join(timeout=5)
        
        elapsed = time.time() - start_time
        print(f"  ✓ Simple threading test completed in {elapsed:.2f}s")
        
        print("\n2. Testing job manager access...")
        start_time = time.time()
        
        if control_centre.job_manager:
            status = control_centre.job_manager.get_queue_status_nonblocking(timeout=0.1)
            if status is not None:
                print(f"  ✓ Job manager accessible - {status.get('total_jobs', 0)} jobs in queue")
            else:
                print("  ⚠ Job manager busy or timeout")
        else:
            print("  ❌ Job manager not available")
            
        elapsed = time.time() - start_time
        print(f"  ✓ Job manager test completed in {elapsed:.2f}s")
        
        print("\n3. Testing filesystem operations...")
        start_time = time.time()
        
        # Test some filesystem operations that are done during job submission
        if hasattr(project, 'capture_files') and 'video' in project.capture_files:
            video_file = project.capture_files['video']
            print(f"  → Testing file existence: {video_file}")
            exists = os.path.exists(video_file)
            print(f"  ✓ File exists check: {exists}")
            
            if exists:
                print(f"  → Testing file size check...")
                size = os.path.getsize(video_file)
                print(f"  ✓ File size: {size} bytes")
        
        elapsed = time.time() - start_time
        print(f"  ✓ Filesystem test completed in {elapsed:.2f}s")
        
        print("\n4. Testing actual job submission...")
        start_time = time.time()
        
        # Try to submit a final mux job and see where it hangs
        print("  → Calling _submit_workflow_job...")
        
        def test_job_submission():
            try:
                success = control_centre._submit_workflow_job(project, WorkflowStep.FINAL)
                print(f"  ✓ Job submission returned: {success}")
            except Exception as e:
                print(f"  ❌ Job submission failed: {e}")
        
        # Run job submission in a separate thread with timeout
        submit_thread = threading.Thread(target=test_job_submission, daemon=True)
        submit_thread.start()
        
        # Wait for completion with timeout
        timeout = 10.0  # 10 second timeout
        submit_thread.join(timeout=timeout)
        
        if submit_thread.is_alive():
            print(f"  ❌ Job submission FROZE after {timeout} seconds!")
            print("  → This is where the freeze occurs!")
        else:
            elapsed = time.time() - start_time
            print(f"  ✓ Job submission completed in {elapsed:.2f}s")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

def test_background_thread_submission():
    """Test if the issue is in the background thread submission itself"""
    print("\n=== Testing Background Thread Submission ===")
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        import queue as thread_queue
        
        control_centre = WorkflowControlCentre()
        control_centre.refresh_data()
        
        if not control_centre.current_projects:
            print("❌ No projects found")
            return
            
        project = control_centre.current_projects[0]
        
        # Test just the background thread part
        result_queue = thread_queue.Queue()
        
        def background_job_submission():
            try:
                print("  → Background thread: Starting...")
                
                # Test the filesystem operations that happen in background
                print("  → Background thread: Testing file operations...")
                
                # Simulate what _submit_workflow_job_background does
                from job_queue_manager import get_job_queue_manager
                job_manager = get_job_queue_manager()
                print("  → Background thread: Got job manager")
                
                # Try non-blocking job addition
                print("  → Background thread: Testing non-blocking job addition...")
                job_id = job_manager.add_job_nonblocking(
                    job_type="test",
                    input_file="/tmp/test_input",
                    output_file="/tmp/test_output",
                    timeout=0.5
                )
                
                print(f"  → Background thread: Job addition result: {job_id}")
                result_queue.put((True, "Background thread completed successfully"))
                
            except Exception as e:
                print(f"  → Background thread: Exception: {e}")
                result_queue.put((False, str(e)))
        
        print("1. Starting background thread...")
        start_time = time.time()
        
        thread = threading.Thread(target=background_job_submission, daemon=True)
        thread.start()
        
        # Wait for result with timeout
        try:
            success, message = result_queue.get(timeout=5.0)
            elapsed = time.time() - start_time
            print(f"  ✓ Background thread result in {elapsed:.2f}s: {success} - {message}")
        except:
            elapsed = time.time() - start_time
            print(f"  ❌ Background thread TIMED OUT after {elapsed:.2f}s!")
            
    except Exception as e:
        print(f"❌ Background thread test failed: {e}")

if __name__ == "__main__":
    test_job_submission_freeze()
    test_background_thread_submission()
