#!/usr/bin/env python3

import subprocess
import sys
import os

def create_sync_test_video(test_pattern, output_file, format_type="PAL", duration_hours=1):
    """
    Create a sync test video with proper audio on/off timing
    
    Args:
        test_pattern: Path to test pattern image
        output_file: Output video filename
        format_type: "PAL" or "NTSC"
        duration_hours: Duration in hours
    """
    
    # Set parameters based on format
    if format_type.upper() == "PAL":
        width, height = 720, 576
        framerate = "25"
    else:  # NTSC
        width, height = 720, 480
        framerate = "29.97"
    
    duration_seconds = duration_hours * 3600
    
    # Create a temporary audio file with proper on/off pattern
    temp_audio = f"temp_audio_{format_type.lower()}.wav"
    
    print(f"Creating {format_type} sync test video...")
    print(f"Duration: {duration_hours} hour(s)")
    print(f"Pattern: 1s ON, 1s OFF for both video and audio")
    
    # First, create audio with proper on/off pattern using SOX
    # Generate 1s tone + 1s silence, repeated for full duration
    print("Generating audio pattern...")
    
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
    
    # Repeat the 2-second pattern for the full duration
    pattern_repeats = duration_seconds // 2
    
    # Create the full audio file by repeating the pattern
    # Use SOX's repeat effect instead of command line repetition to avoid command length issues
    print(f"Repeating 2s pattern {pattern_repeats} times for {duration_hours}h duration...")
    
    # Use SOX repeat effect: sox input.wav output.wav repeat COUNT
    # Note: repeat COUNT means repeat COUNT additional times (so total = COUNT + 1)
    repeat_count = pattern_repeats - 1  # -1 because repeat adds to the original
    
    if repeat_count > 0:
        subprocess.run([
            "sox", "temp_pattern_2s.wav", temp_audio,
            "repeat", str(repeat_count)
        ], check=True)
    else:
        # If we only need one repetition, just copy the file
        subprocess.run([
            "sox", "temp_pattern_2s.wav", temp_audio
        ], check=True)
    
    print("Creating video with synchronised pattern...")
    
    # Now create the video with FFmpeg using the pre-made audio
    ffmpeg_cmd = [
        "ffmpeg", "-y",  # Overwrite output
        
        # Video inputs
        "-f", "lavfi", "-i", f"color=black:size={width}x{height}:rate={framerate}:duration={duration_seconds}",
        "-i", test_pattern,
        
        # Audio input (our pre-made pattern)
        "-i", temp_audio,
        
        # Video filter: overlay test pattern for first second of each 2-second cycle
        "-filter_complex", f"[0][1]overlay=enable='between(mod(t,2),0,1)'[v]",
        
        # Map streams
        "-map", "[v]",  # Video
        "-map", "2:a",  # Audio from our pattern file
        
        # Encoding settings - use fallback encoders for better cross-platform compatibility
        "-c:v", "mpeg4",  # More widely available than libx264
        "-c:a", "pcm_s16le",
        "-r", framerate,
        "-qscale:v", "3",  # High quality for mpeg4
        
        # Output
        output_file
    ]
    
    subprocess.run(ffmpeg_cmd, check=True)
    
    # Clean up temporary files
    for temp_file in ["temp_tone_1s.wav", "temp_silence_1s.wav", "temp_pattern_2s.wav", temp_audio]:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    print(f" Created: {output_file}")
    
    # Verify the file
    probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", output_file]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(" File verification passed")
    else:
        print(" Warning: File verification failed")

def main():
    # Get the script directory and project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Ensure mp4 directory exists
    mp4_dir = os.path.join(project_root, "media", "mp4")
    os.makedirs(mp4_dir, exist_ok=True)
    
    # Build paths relative to project root
    pal_pattern = os.path.join(project_root, "media", "Test Patterns", "testchartpal.tif")
    ntsc_pattern = os.path.join(project_root, "media", "Test Patterns", "testchartntsc.tif")
    pal_output = os.path.join(project_root, "media", "mp4", "pal_sync_test_1hour.mp4")
    ntsc_output = os.path.join(project_root, "media", "mp4", "ntsc_sync_test_1hour.mp4")
    
    # Create PAL version
    create_sync_test_video(
        pal_pattern,
        pal_output,
        "PAL",
        1
    )
    
    # Create NTSC version
    create_sync_test_video(
        ntsc_pattern, 
        ntsc_output,
        "NTSC", 
        1
    )
    
    print("\n Both sync test videos created successfully!")
    print("Files saved to media/ folder")
    print("\nPattern timing:")
    print("- Video: Test pattern visible for 1s, black for 1s (repeating)")
    print("- Audio: 1kHz tone for 1s, silence for 1s (repeating)")
    print("- Both are perfectly synchronised")

if __name__ == "__main__":
    main()
