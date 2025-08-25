#!/usr/bin/env python3

import subprocess
import sys
import os

def create_quick_test(output_file="../media/mp4/sync_test_10s.mp4", duration=10):
    """
    Create a quick 10-second test to verify sync timing
    """
    
    # PAL settings
    width, height = 720, 576
    framerate = "25"
    test_pattern = "../media/Test Patterns/testchartpal.tif"
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Creating {duration}-second sync verification test...")  
    print("Pattern: 1s test pattern + 1s black, 1s 1kHz tone + 1s silence")
    
    # Create a temporary audio file with proper on/off pattern
    temp_audio = "temp_verification_audio.wav"
    
    # Create 1 second of 1kHz tone
    subprocess.run([
        "sox", "-n", "temp_tone_1s.wav", 
        "synth", "1", "sine", "1000",
        "vol", "0.5"  # 50% volume to avoid clipping
    ], check=True)
    
    # Create 1 second of silence
    subprocess.run([
        "sox", "-n", "temp_silence_1s.wav",
        "synth", "1", "sine", "0",  # 0 Hz = silence
        "vol", "0"
    ], check=True)
    
    # Combine tone and silence into a 2-second pattern
    subprocess.run([
        "sox", "temp_tone_1s.wav", "temp_silence_1s.wav", "temp_pattern_2s.wav"
    ], check=True)
    
    # Repeat the 2-second pattern for the duration
    pattern_repeats = duration // 2
    repeat_files = ["temp_pattern_2s.wav"] * pattern_repeats
    sox_cmd = ["sox"] + repeat_files + [temp_audio]
    subprocess.run(sox_cmd, check=True)
    
    print("Creating synchronized test video...")
    
    # Create the video with FFmpeg
    ffmpeg_cmd = [
        "ffmpeg", "-y",  # Overwrite output
        
        # Video inputs
        "-f", "lavfi", "-i", f"color=black:size={width}x{height}:rate={framerate}:duration={duration}",
        "-i", test_pattern,
        
        # Audio input (our pre-made pattern)
        "-i", temp_audio,
        
        # Video filter: overlay test pattern for first second of each 2-second cycle
        "-filter_complex", f"[0][1]overlay=enable='between(mod(t,2),0,1)'[v]",
        
        # Map streams
        "-map", "[v]",  # Video
        "-map", "2:a",  # Audio from our pattern file
        
        # Encoding settings
        "-c:v", "libx264",
        "-c:a", "pcm_s16le",
        "-r", framerate,
        
        # Output
        output_file
    ]
    
    subprocess.run(ffmpeg_cmd, check=True)
    
    # Clean up temporary files
    for temp_file in ["temp_tone_1s.wav", "temp_silence_1s.wav", "temp_pattern_2s.wav", temp_audio]:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    print(f" Created test file: {output_file}")
    
    # Show file info
    probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", output_file]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(" File verification passed")
        
        # Also show a quick summary
        info_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", output_file]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True)
        if info_result.returncode == 0:
            print(f"\nFile details:")
            lines = info_result.stdout.strip().split('\n')
            for line in lines:
                if line:
                    print(f"  {line}")
    else:
        print(" Warning: File verification failed")
    
    return output_file

def play_test_file(filename):
    """
    Attempt to play the test file
    """
    print(f"\nAttempting to play {filename} for verification...")
    print("You should see:")
    print("- Test pattern visible for 1s, black screen for 1s (repeating)")
    print("- 1kHz tone audible for 1s, silence for 1s (repeating)")
    print("- Perfect synchronization between video and audio")
    
    # Try to open with default video player
    try:
        subprocess.run(["open", filename], check=True)  # macOS
        print("\n Opened with default video player")
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(["xdg-open", filename], check=True)  # Linux
            print("\n Opened with default video player")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("\n Could not open automatically. Please play the file manually to verify.")
            print(f"File location: {os.path.abspath(filename)}")

if __name__ == "__main__":
    test_file = create_quick_test()
    
    print("\n" + "="*50)
    print("SYNC TEST VERIFICATION")
    print("="*50)
    
    play_test_file(test_file)
    
    print("\nIf the sync looks good, your main 1-hour files should work perfectly!")
    print("\nExisting files:")
    for f in ["pal_sync_test_1hour.mp4", "pal_sync_test_1hour_fixed.mp4"]:
        if os.path.exists(f):
            size = os.path.getsize(f) / (1024*1024)  # MB
            print(f"   {f} ({size:.1f} MB)")
