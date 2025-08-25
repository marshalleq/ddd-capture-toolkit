#!/usr/bin/env python3
"""
Test to identify lock contention causing UI freeze
"""

import os
import sys
import time
import threading
import select
from concurrent.futures import ThreadPoolExecutor, as_completed
from job_queue_manager import get_job_queue_manager

# Try Rich
try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def test_lock_contention():
    """Test for lock contention between UI refresh and job processing"""
    print("LOCK CONTENTION TEST")
    print("=" * 30)
    print("This test identifies if lock contention is causing the UI freeze.")
    print()
    
    job_manager = get_job_queue_manager()
    console = Console() if RICH_AVAILABLE else None
    
    print("Creating a scenario with high lock contention...")
    
    # Submit multiple jobs to create contention
    print("Submitting 5 test jobs to create lock contention...")
    for i in range(5):
        job_id = job_manager.add_job_nonblocking(
            job_type="final-mux",
            input_file=f"dummy_video_{i}.mkv", 
            output_file=f"dummy_output_{i}.mkv",
            parameters={
                'video_file': f"dummy_video_{i}.mkv",
                'audio_file': f"dummy_audio_{i}.wav", 
                'final_output': f"dummy_output_{i}.mkv",
                'overwrite': True
            },
            priority=1,
            timeout=0.1  # Very short timeout
        )
        if job_id:
            print(f"  Submitted job {i+1}: {job_id}")
        else:
            print(f"  Job {i+1} submission failed/timed out")
    
    print(f"\nStarting high-contention UI loop...")
    print("This simulates rapid screen refreshes while jobs are processing.")
    
    def stress_job_manager():
        """Function to stress the job manager from another thread"""
        for i in range(100):
            try:
                # Rapidly call job manager methods
                status = job_manager.get_queue_status_nonblocking(timeout=0.01)
                jobs = job_manager.get_jobs_nonblocking(timeout=0.01) 
                time.sleep(0.01)
            except Exception:
                pass
    
    # Start stress thread
    stress_thread = threading.Thread(target=stress_job_manager, daemon=True)
    stress_thread.start()
    
    freeze_detected = False
    start_time = time.time()
    
    for loop in range(20):  # 20 iterations
        loop_start = time.time()
        
        # Clear screen (potential contention point 1)
        clear_screen()
        
        print(f"CONTENTION TEST - Loop {loop + 1}/20")
        print("=" * 35)
        
        # Get job data (potential contention point 2)
        get_start = time.time()
        try:
            jobs = job_manager.get_jobs_nonblocking(timeout=0.05)
            status = job_manager.get_queue_status_nonblocking(timeout=0.05)
        except Exception as e:
            print(f"Error getting job data: {e}")
            jobs = None
            status = None
        get_elapsed = time.time() - get_start
        
        if get_elapsed > 0.1:  # More than 100ms
            print(f"⚠ SLOW: Job data retrieval took {get_elapsed:.3f}s")
        
        # Create Rich table (potential contention point 3)
        if RICH_AVAILABLE and console:
            table_start = time.time()
            try:
                table = Table(title="TEST TABLE", show_header=True)
                table.add_column("Job", width=10)
                table.add_column("Status", width=10) 
                table.add_column("Type", width=15)
                
                if jobs:
                    for job in jobs[:5]:
                        table.add_row(
                            str(getattr(job, 'job_id', 'Unknown'))[:8],
                            str(getattr(job, 'status', 'Unknown')),
                            str(getattr(job, 'job_type', 'Unknown'))
                        )
                else:
                    table.add_row("No jobs", "---", "---")
                
                console.print(table)
            except Exception as e:
                print(f"Rich table error: {e}")
            
            table_elapsed = time.time() - table_start
            if table_elapsed > 0.1:
                print(f"⚠ SLOW: Rich table creation took {table_elapsed:.3f}s")
        
        # Show status
        if status:
            print(f"Status: {status['running']} running, {status['queued']} queued, {status['failed']} failed")
        else:
            print("Status: Unavailable")
        
        # Check for freeze (loop taking too long)
        loop_elapsed = time.time() - loop_start
        print(f"Loop time: {loop_elapsed:.3f}s")
        
        if loop_elapsed > 2.0:  # If loop takes more than 2 seconds
            print(f"🚨 FREEZE DETECTED: Loop {loop + 1} took {loop_elapsed:.3f}s")
            freeze_detected = True
            break
        
        # Brief pause to simulate input waiting
        time.sleep(0.1)
    
    total_elapsed = time.time() - start_time
    
    if freeze_detected:
        print(f"\n🚨 FREEZE CONFIRMED after {total_elapsed:.3f}s")
        print("The UI froze due to lock contention!")
    else:
        print(f"\n✓ NO FREEZE DETECTED after {total_elapsed:.3f}s")
        print("Lock contention test passed.")
    
    # Wait for stress thread to complete
    stress_thread.join(timeout=1)
    
    # Final status
    final_status = job_manager.get_queue_status()
    print(f"\nFinal status: {final_status['total_jobs']} total, {final_status['failed']} failed")

def test_simplified_scenario():
    """Test a simplified version without potential contention points"""
    print("\n" + "="*50)
    print("SIMPLIFIED SCENARIO TEST")
    print("="*50)
    print("Testing without Rich tables and rapid refreshes...")
    
    job_manager = get_job_queue_manager()
    
    print("Submitting one test job...")
    job_id = job_manager.add_job_nonblocking(
        job_type="final-mux",
        input_file="simple_test.mkv",
        output_file="simple_output.mkv", 
        parameters={
            'video_file': "simple_test.mkv",
            'audio_file': "simple_test.wav",
            'final_output': "simple_output.mkv", 
            'overwrite': True
        },
        priority=1,
        timeout=2.0
    )
    
    if job_id:
        print(f"✓ Job submitted: {job_id}")
        
        print("\nMonitoring job with simple status checks...")
        for i in range(10):
            time.sleep(0.5)
            status = job_manager.get_queue_status_nonblocking(timeout=0.5)
            if status:
                print(f"  Check {i+1}: {status['running']} running, {status['failed']} failed")
            else:
                print(f"  Check {i+1}: Status unavailable")
        
        print("✓ Simple monitoring completed without freeze")
    else:
        print("✗ Job submission failed")

if __name__ == "__main__":
    # Clean up any old failed jobs first
    try:
        job_manager = get_job_queue_manager()
        job_manager.cleanup_old_jobs(days=0)  # Clean up all old jobs
    except:
        pass
    
    test_lock_contention()
    test_simplified_scenario()
    print("\nLock contention testing completed!")
