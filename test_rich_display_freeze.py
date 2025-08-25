#!/usr/bin/env python3
"""
Test to isolate if Rich table display causes freeze during active jobs
"""

import os
import sys
import time
import signal

def test_rich_display_freeze():
    """Test Rich table display operations during active job"""
    print("Testing Rich display during final mux job execution...")
    
    def timeout_handler(signum, frame):
        print("\n❌ FREEZE DETECTED during Rich display operations!")
        print("The issue is in the Rich table rendering!")
        os._exit(1)
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(15)  # 15 second timeout
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        
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
        
        # Wait a moment for the job to start
        time.sleep(1)
        
        # Test the specific UI components that are called in the interactive loop
        print("\n=== Testing UI Display Components ===")
        
        for i in range(5):  # Test multiple display cycles
            print(f"Display cycle {i+1}/5...")
            
            try:
                # Test 1: refresh_data
                print(f"  → Testing refresh_data()...")
                start_time = time.time()
                control_centre.refresh_data()
                elapsed = time.time() - start_time
                print(f"  ✓ refresh_data() completed in {elapsed:.3f}s")
                
                # Test 2: display_project_matrix (this uses Rich tables)
                print(f"  → Testing display_project_matrix()...")
                start_time = time.time()
                control_centre.display_project_matrix()
                elapsed = time.time() - start_time
                print(f"  ✓ display_project_matrix() completed in {elapsed:.3f}s")
                
                # Test 3: display_active_jobs
                print(f"  → Testing display_active_jobs()...")
                start_time = time.time()
                control_centre.display_active_jobs()
                elapsed = time.time() - start_time
                print(f"  ✓ display_active_jobs() completed in {elapsed:.3f}s")
                
                # Test 4: display_system_status
                print(f"  → Testing display_system_status()...")
                start_time = time.time()
                control_centre.display_system_status()
                elapsed = time.time() - start_time
                print(f"  ✓ display_system_status() completed in {elapsed:.3f}s")
                
                # Test 5: Rich table creation specifically
                print(f"  → Testing Rich table creation...")
                start_time = time.time()
                if hasattr(control_centre, '_create_numbered_project_table'):
                    table = control_centre._create_numbered_project_table()
                    elapsed = time.time() - start_time
                    print(f"  ✓ _create_numbered_project_table() completed in {elapsed:.3f}s")
                
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  ❌ Error in display cycle {i+1} after {elapsed:.3f}s: {e}")
                import traceback
                traceback.print_exc()
            
            # Brief pause
            time.sleep(0.5)
        
        signal.alarm(0)
        print("\n✅ All Rich display operations completed successfully!")
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_select_input_freeze():
    """Test if the select.select() input handling causes freeze"""
    print("\n=== Testing Select Input Handling ===")
    
    try:
        import select
        import sys
        
        # Test the exact select.select() call used in the interactive mode
        print("Testing select.select() call...")
        start_time = time.time()
        
        # This is the exact call from run_simple_interactive_mode
        ready = sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]  # Short timeout for test
        
        elapsed = time.time() - start_time
        print(f"✓ select.select() completed in {elapsed:.3f}s (ready: {ready})")
        
    except Exception as e:
        print(f"❌ select.select() test failed: {e}")

if __name__ == "__main__":
    test_rich_display_freeze()
    test_select_input_freeze()
