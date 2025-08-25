#!/usr/bin/env python3
"""
Exact reproduction of workflow control centre freeze scenario
"""

import os
import sys
import time
import select
import threading
from job_queue_manager import get_job_queue_manager

# Try to import Rich components
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def test_exact_workflow_scenario():
    """Test the exact workflow control centre scenario"""
    print("EXACT WORKFLOW CONTROL CENTRE REPRODUCTION")
    print("=" * 50)
    print("This test reproduces the exact sequence of operations that")
    print("the workflow control centre performs during job submission.")
    print()
    
    # Initialize components just like workflow control centre
    print("1. Initializing job manager (like workflow control centre)...")
    job_manager = get_job_queue_manager()
    
    console = Console() if RICH_AVAILABLE else None
    current_projects = []  # Empty for this test
    current_jobs = []
    
    print("2. Starting interactive loop with Rich tables and screen clearing...")
    print("   (This is the exact sequence that causes freezing)")
    print("   Type 'submit' to submit a job, 'q' to quit")
    
    loop_count = 0
    while loop_count < 50:  # Limit to 50 loops to prevent infinite running
        loop_count += 1
        
        # === EXACT WORKFLOW CONTROL CENTRE SEQUENCE ===
        
        # Step 1: Clear screen (like workflow control centre)
        clear_screen()
        
        # Step 2: Get job data with non-blocking methods
        try:
            jobs = job_manager.get_jobs_nonblocking(timeout=0.1)
            if jobs is not None:
                current_jobs = [job for job in jobs if str(job.status).lower() in ['running', 'queued', 'failed']][:9]
            
            status = job_manager.get_queue_status_nonblocking(timeout=0.1)
        except Exception as e:
            print(f"Error getting job data: {e}")
            current_jobs = []
            status = None
        
        # Step 3: Create Rich table (like workflow control centre)
        print(f"EXACT UI REPRODUCTION TEST - Loop {loop_count}")
        print("=" * 45)
        
        if RICH_AVAILABLE and console:
            try:
                # Create project table
                table = Table(title="WORKFLOW PROGRESSION BY PROJECT", show_header=True, header_style="bold")
                table.add_column("", style="dim", width=3)
                table.add_column("Project Name", style="bold", width=20)
                table.add_column("Capture", width=11, justify="center")
                table.add_column("(D)ecode", width=11, justify="center")
                table.add_column("(E)xport", width=11, justify="center")
                table.add_column("(F)inal", width=11, justify="center")
                
                # Add empty rows
                for idx in range(7):
                    project_num = idx + 1
                    label = Text(f" {project_num}", style="dim")
                    table.add_row(label, "---", "---", "---", "---", "---")
                
                console.print(table)
                
            except Exception as e:
                print(f"Error creating Rich table: {e}")
        
        # Step 4: Show job status
        print("\nACTIVE JOBS:")
        print("=" * 70)
        
        if not current_jobs:
            print("No active jobs in queue.")
        else:
            for idx, job in enumerate(current_jobs[:9]):
                job_num = idx + 1
                job_id = str(getattr(job, 'job_id', '?'))
                job_type = getattr(job, 'job_type', 'Unknown')
                job_status = getattr(job, 'status', 'Unknown')
                progress = getattr(job, 'progress', 0)
                print(f" {job_num} {job_id:<15} {job_type:<12} {job_status:<10} {progress}%")
        
        # Step 5: Show system status (with non-blocking call)
        print(f"\nSYSTEM STATUS:")
        if status:
            print(f"Queue Status: {status['running']} running, {status['queued']} queued, {status['failed']} failed")
        else:
            print("Queue Status: Unavailable (busy)")
        
        # Step 6: Use select for input (like workflow control centre)
        print("\nCommands: submit = Submit job, q = Quit")
        try:
            print("Enter command (or wait 2s for auto-refresh): ", end='', flush=True)
            
            # This is the exact select call used by workflow control centre
            if sys.stdin in select.select([sys.stdin], [], [], 2.0)[0]:
                cmd = input().strip().lower()
            else:
                cmd = ""
                print()  # New line for clean display
        except (ImportError, OSError):
            # Fallback for systems without select
            cmd = input("\nEnter command: ").strip().lower()
        
        # Step 7: Handle commands
        if cmd == 'q':
            break
        elif cmd == 'submit':
            print(f"\n{'='*50}")
            print("SUBMITTING JOB (POTENTIAL FREEZE POINT)")
            print(f"{'='*50}")
            
            # This is the exact job submission that might cause freezing
            try:
                start_time = time.time()
                
                # Use add_job_nonblocking just like workflow control centre
                job_id = job_manager.add_job_nonblocking(
                    job_type="final-mux",
                    input_file="test_video.mkv",
                    output_file="test_output.mkv",
                    parameters={
                        'video_file': "test_video.mkv",
                        'audio_file': "test_audio.wav",
                        'final_output': "test_output.mkv",
                        'overwrite': True
                    },
                    priority=2,
                    timeout=1.0
                )
                
                elapsed = time.time() - start_time
                
                if job_id:
                    print(f"✓ Job submitted in {elapsed:.3f}s: {job_id}")
                else:
                    print(f"⚠ Job submission returned None after {elapsed:.3f}s")
                
                print("If you can see this message, no freeze occurred!")
                input("Press Enter to continue...")
                
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"✗ Job submission error after {elapsed:.3f}s: {e}")
                input("Press Enter to continue...")
        
        elif cmd == "":
            # Auto-refresh - just continue the loop
            continue
        else:
            print(f"Unknown command: {cmd}")
            time.sleep(1)
    
    print(f"\nTest completed after {loop_count} loops - no freeze detected!")
    
    # Final check
    final_status = job_manager.get_queue_status()
    print(f"Final status: {final_status['running']} running, {final_status['queued']} queued, {final_status['failed']} failed")

if __name__ == "__main__":
    test_exact_workflow_scenario()
