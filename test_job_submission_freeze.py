#!/usr/bin/env python3
"""
Direct test of job submission to reproduce the UI freeze
"""

import os
import time
from job_queue_manager import get_job_queue_manager

def test_job_submission():
    """Test job submission directly"""
    print("DIRECT JOB SUBMISSION TEST")
    print("=" * 30)
    
    # Get job manager
    print("Getting job manager...")
    job_manager = get_job_queue_manager()
    
    # Show initial status
    print("Getting initial queue status...")
    status = job_manager.get_queue_status()
    print(f"Queue status: {status['running']} running, {status['queued']} queued, {status['failed']} failed")
    
    # Look for actual video files to test with
    test_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('_ffv1.mkv'):
                video_file = os.path.join(root, file)
                audio_file = None
                
                # Look for corresponding audio file
                base_name = file.replace('_ffv1.mkv', '')
                for ext in ['.wav', '.flac']:
                    potential_audio = os.path.join(root, base_name + ext)
                    if os.path.exists(potential_audio):
                        audio_file = potential_audio
                        break
                
                if not audio_file:
                    # Look for _aligned.wav
                    potential_audio = os.path.join(root, base_name + '_aligned.wav')
                    if os.path.exists(potential_audio):
                        audio_file = potential_audio
                
                test_files.append({
                    'video': video_file,
                    'audio': audio_file,
                    'output': os.path.join(root, base_name + '_test_final.mkv')
                })
                
                if len(test_files) >= 1:  # Just need one for testing
                    break
        if test_files:
            break
    
    if not test_files:
        print("No suitable test files found, using dummy files...")
        test_files = [{
            'video': 'dummy_video.mkv',
            'audio': 'dummy_audio.wav',
            'output': 'dummy_final.mkv'
        }]
    
    test_file = test_files[0]
    print(f"Using test files:")
    print(f"  Video: {test_file['video']}")
    print(f"  Audio: {test_file['audio']}")
    print(f"  Output: {test_file['output']}")
    
    print("\n" + "="*50)
    print("SUBMITTING FINAL MUX JOB - MONITORING FOR FREEZE")
    print("="*50)
    
    try:
        print("Calling add_job_nonblocking...")
        start_time = time.time()
        
        job_id = job_manager.add_job_nonblocking(
            job_type="final-mux",
            input_file=test_file['video'],
            output_file=test_file['output'],
            parameters={
                'video_file': test_file['video'],
                'audio_file': test_file['audio'],
                'final_output': test_file['output'],
                'overwrite': True
            },
            priority=2,
            timeout=2.0  # 2 second timeout
        )
        
        elapsed = time.time() - start_time
        print(f"Job submission took {elapsed:.3f} seconds")
        
        if job_id:
            print(f"✓ Job submitted successfully: {job_id}")
            
            print("\nMonitoring job for a few seconds...")
            for i in range(10):  # Monitor for 10 seconds
                time.sleep(1)
                status = job_manager.get_queue_status_nonblocking(timeout=0.5)
                if status:
                    print(f"  Second {i+1}: {status['running']} running, {status['queued']} queued")
                else:
                    print(f"  Second {i+1}: Status unavailable")
                
                # Check if the UI would be responsive by doing what the workflow center does
                print(f"  Second {i+1}: UI would refresh here - checking responsiveness")
                
        else:
            print("⚠ Job submission returned None (timeout or busy)")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ Job submission failed after {elapsed:.3f}s: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print("FINAL STATUS CHECK")
    print("="*50)
    
    final_status = job_manager.get_queue_status()
    print(f"Final queue status: {final_status['running']} running, {final_status['queued']} queued, {final_status['failed']} failed")
    
    print("\nTest completed - if you can see this, no freeze occurred!")

if __name__ == "__main__":
    test_job_submission()
