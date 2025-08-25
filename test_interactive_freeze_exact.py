#!/usr/bin/env python3
"""
Final test to reproduce the exact interactive conditions that cause the freeze
"""

import os
import sys
import time
import threading
import signal
import subprocess

def test_exact_interactive_conditions():
    """Test the exact conditions that cause the freeze in interactive mode"""
    print("Testing exact interactive mode conditions during FFmpeg execution...")
    
    def timeout_handler(signum, frame):
        print("\n❌ FREEZE DETECTED in exact interactive conditions!")
        print("Found the source of the freeze!")
        os._exit(1)
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30 second timeout
    
    try:
        from workflow_control_centre import WorkflowControlCentre
        from workflow_analyzer import WorkflowStep
        
        print("✓ Creating workflow control centre...")
        control_centre = WorkflowControlCentre()
        control_centre.refresh_data()
        
        if not control_centre.current_projects:
            print("❌ No projects found")
            return
        
        project = control_centre.current_projects[0]
        print(f"✓ Using project: {project.name}")
        
        # Submit a final mux job that will actually run
        print("\n=== Submitting final mux job ===")
        success = control_centre._submit_workflow_job(project, WorkflowStep.FINAL, force_overwrite=True)
        print(f"✓ Job submitted: {success}")
        
        # Now simulate the exact interactive loop conditions
        print("\n=== Simulating Interactive Loop During Job Execution ===")
        
        # This simulates what happens in run_simple_interactive_mode()
        for loop_iteration in range(20):  # Simulate 20 UI refresh cycles
            print(f"\\nLoop iteration {loop_iteration + 1}/20...")
            
            try:\n                # Step 1: refresh_data() - exactly like the interactive loop\n                print(\"  → refresh_data()...\")\n                start_time = time.time()\n                control_centre.refresh_data()\n                elapsed = time.time() - start_time\n                print(f\"  ✓ refresh_data(): {elapsed:.3f}s\")\n                \n                if elapsed > 0.5:\n                    print(f\"    ⚠ refresh_data() took {elapsed:.3f}s - this might be the issue!\")\n                \n                # Step 2: clear_screen() and display operations\n                print(\"  → UI display operations...\")\n                \n                # Clear screen (this might interact badly with terminal)\n                from workflow_control_centre import clear_screen\n                clear_screen()\n                \n                # Display header\n                from workflow_control_centre import display_header\n                display_header()\n                \n                # Display project matrix (Rich tables)\n                print(\"\\nVHS WORKFLOW CONTROL CENTRE - Phase 1.3\")\n                print(\"=\" * 45)\n                \n                display_start = time.time()\n                control_centre.display_project_matrix()\n                display_elapsed = time.time() - display_start\n                \n                if display_elapsed > 0.5:\n                    print(f\"    ⚠ display_project_matrix() took {display_elapsed:.3f}s - potential issue!\")\n                \n                control_centre.display_active_jobs()\n                control_centre.display_system_status()\n                \n                # Step 3: Check job status to see if it's still running\n                status = control_centre.job_manager.get_queue_status_nonblocking(timeout=0.1)\n                if status:\n                    running_jobs = status.get('running', 0)\n                    if running_jobs > 0:\n                        print(f\"  📊 Job still running ({running_jobs} active jobs)\")\n                    else:\n                        print(f\"  ✅ Job completed - no more running jobs\")\n                        break\n                else:\n                    print(f\"  ⚠ Could not get job status\")\n                \n            except Exception as e:\n                print(f\"  ❌ Error in loop iteration {loop_iteration + 1}: {e}\")\n                import traceback\n                traceback.print_exc()\n                break\n            \n            # Brief pause between iterations (like auto-refresh)\n            time.sleep(0.5)\n        \n        signal.alarm(0)\n        print(\"\\n✅ Interactive loop simulation completed successfully!\")\n        \n    except Exception as e:\n        signal.alarm(0)\n        print(f\"❌ Test failed: {e}\")\n        import traceback\n        traceback.print_exc()\n\ndef test_terminal_operations_with_ffmpeg():\n    \"\"\"Test if terminal operations conflict with running FFmpeg\"\"\"\n    print(\"\\n=== Testing Terminal Operations During FFmpeg ===\\n\")\n    \n    try:\n        # Start a simple FFmpeg process in background\n        print(\"Starting FFmpeg process...\")\n        \n        # Create a simple test video generation command\n        ffmpeg_cmd = [\n            'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=10:size=320x240:rate=1',\n            '-y', '/tmp/test_output.mp4'\n        ]\n        \n        ffmpeg_process = subprocess.Popen(\n            ffmpeg_cmd,\n            stdout=subprocess.PIPE,\n            stderr=subprocess.PIPE,\n            text=True\n        )\n        \n        print(f\"✓ FFmpeg started with PID: {ffmpeg_process.pid}\")\n        \n        # Now test terminal operations while FFmpeg is running\n        for i in range(10):\n            print(f\"\\nTerminal test cycle {i+1}/10...\")\n            \n            try:\n                # Test clear_screen() while FFmpeg runs\n                from workflow_control_centre import clear_screen, display_header\n                \n                print(\"  → Testing clear_screen()...\")\n                start_time = time.time()\n                clear_screen()\n                elapsed = time.time() - start_time\n                \n                if elapsed > 0.1:\n                    print(f\"    ⚠ clear_screen() took {elapsed:.3f}s\")\n                \n                # Test display_header()\n                display_header()\n                \n                # Check if FFmpeg is still running\n                if ffmpeg_process.poll() is not None:\n                    print(\"  ✅ FFmpeg process completed\")\n                    break\n                else:\n                    print(f\"  📊 FFmpeg still running...\")\n                \n            except Exception as e:\n                print(f\"  ❌ Error in terminal test {i+1}: {e}\")\n            \n            time.sleep(0.5)\n        \n        # Clean up FFmpeg process\n        if ffmpeg_process.poll() is None:\n            print(\"\\nTerminating FFmpeg process...\")\n            ffmpeg_process.terminate()\n            ffmpeg_process.wait(timeout=5)\n        \n        print(\"✅ Terminal operations test completed\")\n        \n    except FileNotFoundError:\n        print(\"❌ FFmpeg not found - skipping terminal interaction test\")\n    except Exception as e:\n        print(f\"❌ Terminal test failed: {e}\")\n\nif __name__ == \"__main__\":\n    test_exact_interactive_conditions()\n    test_terminal_operations_with_ffmpeg()\n
