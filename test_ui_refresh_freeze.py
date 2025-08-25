#!/usr/bin/env python3
"""
Test to isolate the specific UI refresh operation that causes the freeze
"""

import os
import sys
import time
import threading
import signal

def test_ui_refresh_during_job():
    """Test UI refresh operations while a final mux job is running"""
    print("Testing UI refresh during final mux job execution...")
    
    def timeout_handler(signum, frame):
        print("\n❌ FREEZE DETECTED during UI refresh operations!")
        os._exit(1)
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(20)  # 20 second timeout
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        from job_queue_manager import get_job_queue_manager
        
        # Create workflow control centre
        control_centre = WorkflowControlCentre()
        control_centre.refresh_data()
        
        if not control_centre.current_projects:
            print("❌ No projects found")
            return
        
        project = control_centre.current_projects[0]
        print(f"✓ Using project: {project.name}")
        
        # Submit a final mux job
        print("\n=== Submitting final mux job ===")
        success = control_centre._submit_workflow_job(project, WorkflowStep.FINAL, force_overwrite=True)
        print(f"✓ Job submitted: {success}")
        
        # Now test various UI refresh operations while the job might be running
        print("\n=== Testing UI refresh operations ===")
        
        for i in range(10):  # Test multiple refresh cycles
            print(f"Refresh cycle {i+1}/10...")
            start_time = time.time()
            
            try:
                # Test 1: refresh_data (this is called every UI loop)
                print(f"  → Testing refresh_data()...")
                refresh_start = time.time()
                control_centre.refresh_data()
                refresh_elapsed = time.time() - refresh_start
                print(f"  ✓ refresh_data() completed in {refresh_elapsed:.3f}s")
                
                # Test 2: workflow analysis specifically
                print(f"  → Testing workflow analysis...")
                analysis_start = time.time()
                if control_centre.workflow_analyzer:
                    workflow_status = control_centre.workflow_analyzer.analyze_project_workflow(project)
                    analysis_elapsed = time.time() - analysis_start
                    print(f"  ✓ analyze_project_workflow() completed in {analysis_elapsed:.3f}s")
                
                # Test 3: job manager status checks
                print(f"  → Testing job manager status...")
                status_start = time.time()
                if control_centre.job_manager:
                    status = control_centre.job_manager.get_queue_status_nonblocking(timeout=0.1)
                    status_elapsed = time.time() - status_start
                    if status:
                        print(f"  ✓ Queue status: {status['running']} running, {status['queued']} queued ({status_elapsed:.3f}s)")
                    else:
                        print(f"  ⚠ Queue status unavailable ({status_elapsed:.3f}s)")
                
            except Exception as e:
                print(f"  ❌ Error in refresh cycle {i+1}: {e}")
            
            total_elapsed = time.time() - start_time
            print(f"  ✓ Refresh cycle {i+1} completed in {total_elapsed:.3f}s")
            
            # Brief pause between cycles
            time.sleep(0.5)
        
        signal.alarm(0)
        print("\n✅ All UI refresh cycles completed successfully!")
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_workflow_analysis_freeze():
    """Test specifically the workflow analysis that might be freezing"""
    print("\n=== Testing Workflow Analysis Freeze ===")
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowAnalyzer
        from job_queue_manager import get_job_queue_manager
        
        control_centre = WorkflowControlCentre()
        control_centre.refresh_data()
        
        if not control_centre.current_projects:
            print("❌ No projects found")
            return
        
        project = control_centre.current_projects[0]
        job_manager = get_job_queue_manager()
        analyzer = WorkflowAnalyzer(job_manager)
        
        print(f"✓ Testing workflow analysis for: {project.name}")
        
        # Test the individual methods that might block
        from workflow_analyzer import WorkflowStep
        
        for step in WorkflowStep:
            print(f"  → Testing {step.value} status check...")
            start_time = time.time()
            
            try:
                status = analyzer.get_step_status(step, project)
                elapsed = time.time() - start_time
                print(f"  ✓ {step.value}: {status.value} ({elapsed:.3f}s)")
                
                if elapsed > 0.1:  # Flag anything taking longer than 100ms
                    print(f"    ⚠ Step {step.value} took {elapsed:.3f}s - this might be the issue!")
                    
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  ❌ {step.value} failed after {elapsed:.3f}s: {e}")
        
        print("✓ Workflow analysis test completed")
        
    except Exception as e:
        print(f"❌ Workflow analysis test failed: {e}")

if __name__ == "__main__":
    test_ui_refresh_during_job()
    test_workflow_analysis_freeze()
