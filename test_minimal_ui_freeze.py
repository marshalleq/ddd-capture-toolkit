#!/usr/bin/env python3
"""
Minimal test to reproduce UI freezing during job submission
This will help us identify the exact cause of the freeze
"""

import os
import sys
import time
import threading
import subprocess
import select
from job_queue_manager import get_job_queue_manager

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def test_scenario():
    """Test the exact scenario that causes freezing"""
    print("MINIMAL UI FREEZE TEST")
    print("=" * 30)
    print("This test reproduces the exact scenario that causes UI freezing.")
    print("We'll simulate the workflow control centre's job submission process.")
    print()
    
    # Get job manager
    print("1. Getting job manager...")
    job_manager = get_job_queue_manager()
    print("   ✓ Job manager obtained")
    
    # Show initial status
    print("2. Getting initial status...")
    status = job_manager.get_queue_status_nonblocking(timeout=0.5)
    if status:
        print(f"   ✓ Queue status: {status['running']} running, {status['queued']} queued")
    else:
        print("   ⚠ Queue status unavailable")
    
    print()
    print("3. Starting interactive loop (similar to workflow control centre)...")
    print("   This will clear screen, show status, and wait for input")
    print("   Type 'submit' to submit a test job, 'q' to quit")
    print()
    
    loop_count = 0
    while True:
        loop_count += 1
        
        # Clear and redraw (like the workflow control centre does)
        clear_screen()
        print(f"MINIMAL UI TEST - Loop {loop_count}")
        print("=" * 30)
        
        # Get current status (non-blocking)
        try:
            status = job_manager.get_queue_status_nonblocking(timeout=0.1)
            if status:
                print(f"Queue Status: {status['running']} running, {status['queued']} queued, {status['failed']} failed")
            else:
                print("Queue Status: Unavailable (busy)")
        except Exception as e:
            print(f"Queue Status: Error - {e}")
        
        print()
        print("Commands:")
        print("  submit - Submit a test final mux job (this may cause freeze)")
        print("  q - Quit test")
        
        # Use select for non-blocking input (like workflow control centre)
        try:
            print("\nEnter command (or wait 5s for auto-refresh): ", end='', flush=True)
            
            if sys.stdin in select.select([sys.stdin], [], [], 5.0)[0]:
                cmd = input().strip().lower()
            else:
                cmd = ""
                print()  # New line for clean display
        except (ImportError, OSError):
            cmd = input("\nEnter command: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == 'submit':
            print("\n" + "="*50)
            print("SUBMITTING TEST JOB - THIS MAY CAUSE FREEZE")
            print("="*50)
            print("Submitting a final mux job similar to workflow control centre...")
            
            # Find test files
            test_video = None
            test_audio = None
            
            # Look for test files in current directory
            for f in os.listdir('.'):
                if f.endswith('_ffv1.mkv'):
                    test_video = f
                elif f.endswith('.wav') or f.endswith('.flac'):
                    test_audio = f
                if test_video and test_audio:
                    break
            
            if not test_video:
                print("⚠ No _ffv1.mkv file found for testing, creating dummy parameters...")
                test_video = "dummy_video.mkv"
                test_audio = "dummy_audio.wav"
            
            print(f"Test video file: {test_video}")
            print(f"Test audio file: {test_audio}")
            
            # Submit job using the same method as workflow control centre
            try:
                print("Calling add_job_nonblocking...")
                start_time = time.time()
                
                job_id = job_manager.add_job_nonblocking(
                    job_type="final-mux",
                    input_file=test_video,
                    output_file="test_final.mkv",
                    parameters={
                        'video_file': test_video,
                        'audio_file': test_audio,
                        'final_output': "test_final.mkv",
                        'overwrite': True
                    },
                    priority=2,
                    timeout=1.0
                )
                
                elapsed = time.time() - start_time
                print(f"Job submission completed in {elapsed:.3f}s")
                
                if job_id:
                    print(f"✓ Job submitted successfully: {job_id}")
                else:
                    print("⚠ Job submission returned None (timeout or busy)")
                    
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"✗ Job submission failed after {elapsed:.3f}s: {e}")
            
            print("\nIf you can see this message, the job submission didn't freeze!")
            input("Press Enter to continue...")
        
        elif cmd == "":
            # Auto-refresh - just continue loop
            continue
        else:
            print(f"\nUnknown command: {cmd}")
            time.sleep(1)
    
    print("\nTest completed successfully - no freeze detected!")

def test_ffmpeg_direct():
    """Test running FFmpeg directly to see if that causes issues"""
    print("\n" + "="*50)
    print("TESTING FFMPEG EXECUTION DIRECTLY")
    print("="*50)
    
    # Create a simple test command
    cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1', 
           '-c:v', 'libx264', '-t', '1', '/tmp/test_output.mp4', '-y']
    
    print(f"Running: {' '.join(cmd)}")
    print("This should complete quickly...")
    
    try:
        start_time = time.time()
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Simple output reading
        while True:
            return_code = process.poll()
            
            # Read any available output
            try:
                if process.stderr:
                    line = process.stderr.readline()
                    if line:
                        print(f"FFmpeg: {line.strip()}")
            except:
                pass
            
            if return_code is not None:
                break
                
            time.sleep(0.1)
        
        elapsed = time.time() - start_time
        print(f"\nFFmpeg completed in {elapsed:.3f}s with return code: {return_code}")
        
        # Clean up
        if os.path.exists('/tmp/test_output.mp4'):
            os.remove('/tmp/test_output.mp4')
        
    except FileNotFoundError:
        print("FFmpeg not found - skipping direct test")
    except Exception as e:
        print(f"Error running FFmpeg directly: {e}")

def main():
    """Main test function"""
    print("MINIMAL UI FREEZE DIAGNOSTIC TEST")
    print("=" * 40)
    print("This test will help identify the exact cause of UI freezing")
    print("in the workflow control centre during job submission.")
    print()
    
    choice = input("Test options:\n1. Interactive UI simulation\n2. Direct FFmpeg test\n3. Both\nChoice (1-3): ").strip()
    
    if choice in ['1', '3']:
        test_scenario()
    
    if choice in ['2', '3']:
        test_ffmpeg_direct()
    
    print("\nDiagnostic test completed!")

if __name__ == "__main__":
    main()
