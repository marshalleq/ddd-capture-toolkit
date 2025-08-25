#!/usr/bin/env python3
"""
Test to check if subprocess execution of missing commands causes hanging
"""

import subprocess
import time
import threading
import signal

def test_missing_command():
    """Test what happens when we try to run a missing command"""
    print("TESTING SUBPROCESS BEHAVIOR WITH MISSING COMMANDS")
    print("=" * 50)
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Process timed out")
    
    # Test 1: Direct subprocess call
    print("Test 1: Direct subprocess call to missing 'ffmpeg'")
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)  # 5 second timeout
        
        start_time = time.time()
        process = subprocess.Popen(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        elapsed = time.time() - start_time
        print(f"  Popen completed in {elapsed:.3f}s")
        
        # Try to communicate
        try:
            stdout, stderr = process.communicate(timeout=2)
            print(f"  communicate() completed, return code: {process.returncode}")
        except subprocess.TimeoutExpired:
            print("  communicate() timed out, process may be hanging")
            process.kill()
        
    except FileNotFoundError as e:
        elapsed = time.time() - start_time
        print(f"  ✓ FileNotFoundError raised immediately after {elapsed:.3f}s: {e}")
    except TimeoutError:
        print("  ✗ Process timed out - likely hanging")
    finally:
        signal.alarm(0)
    
    print()
    
    # Test 2: What the job manager actually does
    print("Test 2: Simulating job manager FFmpeg execution")
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)
        
        start_time = time.time()
        
        # This is what the job manager does
        ffmpeg_cmd = ['ffmpeg', '-threads', '4', '-i', 'dummy_video.mkv', 
                     '-i', 'dummy_audio.wav', '-c:v', 'copy', '-c:a', 'flac', 
                     '-y', 'dummy_final.mkv']
        
        print(f"  Running: {' '.join(ffmpeg_cmd)}")
        
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        elapsed = time.time() - start_time
        print(f"  Popen completed in {elapsed:.3f}s")
        print(f"  Process PID: {process.pid}")
        
        # Try the monitoring loop that job manager uses
        stderr_lines = []
        loop_count = 0
        while loop_count < 10:  # Max 10 iterations
            return_code = process.poll()
            
            # Read stderr output from FFmpeg
            try:
                stderr_line = process.stderr.readline()
                if stderr_line:
                    stderr_lines.append(stderr_line.strip())
                    print(f"    Read line: {stderr_line.strip()[:50]}...")
            except Exception as e:
                print(f"    Error reading output: {e}")
            
            # Check if process has finished
            if return_code is not None:
                print(f"    Process finished with return code: {return_code}")
                break
            
            loop_count += 1
            time.sleep(0.1)
        
        if return_code is None:
            print("    Process still running after monitoring loop")
            process.kill()
            process.wait()
            print("    Process killed")
        
    except FileNotFoundError as e:
        elapsed = time.time() - start_time
        print(f"  ✓ FileNotFoundError raised after {elapsed:.3f}s: {e}")
    except TimeoutError:
        print("  ✗ Process timed out - likely hanging")
        try:
            process.kill()
        except:
            pass
    finally:
        signal.alarm(0)
    
    print()
    print("Test completed!")

if __name__ == "__main__":
    test_missing_command()
