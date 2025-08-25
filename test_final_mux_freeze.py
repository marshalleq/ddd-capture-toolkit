#!/usr/bin/env python3
"""
Test script to specifically trigger the final mux job that causes UI freezing
"""

import os
import sys
import time
import threading
import signal

def test_final_mux_freeze():
    """Test the specific final mux job submission that freezes the UI"""
    print("Testing final mux job freeze...")
    
    # Set up a signal handler to detect if we get stuck
    def timeout_handler(signum, frame):
        print("\n❌ FREEZE DETECTED! Script timed out after 15 seconds.")
        print("This confirms the final mux job submission is causing the freeze.")
        os._exit(1)
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(15)  # 15 second timeout
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        from job_queue_manager import get_job_queue_manager
        
        print("✓ Imported modules")
        
        # Create workflow control centre
        control_centre = WorkflowControlCentre()
        control_centre.refresh_data()
        
        if not control_centre.current_projects:
            print("❌ No projects found")
            return
        
        project = control_centre.current_projects[0]
        print(f"✓ Using project: {project.name}")
        
        # Show current job queue status
        job_manager = get_job_queue_manager()
        status = job_manager.get_queue_status()
        print(f"✓ Current queue: {status['running']} running, {status['queued']} queued")
        
        # Force submit a final mux job (even if one exists) to trigger the issue
        print("\n=== Attempting to submit final mux job ===")
        print("⚠ This should cause the freeze if the issue still exists...")
        
        start_time = time.time()
        
        # Use force_overwrite to make sure it actually submits the job
        success = control_centre._submit_workflow_job(project, WorkflowStep.FINAL, force_overwrite=True)
        
        elapsed = time.time() - start_time
        print(f"✓ Job submission completed successfully in {elapsed:.2f}s: {success}")
        
        # Check if job was actually queued
        status_after = job_manager.get_queue_status()
        print(f"✓ Queue after submission: {status_after['running']} running, {status_after['queued']} queued")
        
        # Wait a moment to see if the job starts
        print("\n=== Waiting for job to start ===")
        time.sleep(2)
        
        status_final = job_manager.get_queue_status()
        print(f"✓ Final queue status: {status_final['running']} running, {status_final['queued']} queued")
        
        # Cancel the timeout - we made it through!
        signal.alarm(0)
        print("\n✅ Test completed successfully - no freeze detected!")
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

def test_job_manager_operations():
    """Test job manager operations that might be causing the freeze"""
    print("\n=== Testing Job Manager Operations ===")
    
    try:
        from job_queue_manager import get_job_queue_manager
        
        job_manager = get_job_queue_manager()
        print("✓ Got job manager")
        
        # Test various job manager operations that might block
        print("1. Testing get_queue_status()...")
        start_time = time.time()
        status = job_manager.get_queue_status()
        elapsed = time.time() - start_time
        print(f"  ✓ get_queue_status() completed in {elapsed:.2f}s")
        
        print("2. Testing get_jobs()...")
        start_time = time.time()
        jobs = job_manager.get_jobs()
        elapsed = time.time() - start_time
        print(f"  ✓ get_jobs() returned {len(jobs)} jobs in {elapsed:.2f}s")
        
        print("3. Testing save_queue()...")
        start_time = time.time()
        job_manager.save_queue()
        elapsed = time.time() - start_time
        print(f"  ✓ save_queue() completed in {elapsed:.2f}s")
        
        print("4. Testing add_job_nonblocking()...")
        start_time = time.time()
        job_id = job_manager.add_job_nonblocking(
            job_type="test-freeze",
            input_file="/tmp/test_input",
            output_file="/tmp/test_output",
            timeout=1.0
        )
        elapsed = time.time() - start_time
        print(f"  ✓ add_job_nonblocking() returned {job_id} in {elapsed:.2f}s")
        
    except Exception as e:
        print(f"❌ Job manager test failed: {e}")

if __name__ == "__main__":
    test_final_mux_freeze()
    test_job_manager_operations()
