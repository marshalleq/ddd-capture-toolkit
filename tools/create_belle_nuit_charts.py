#!/usr/bin/env python3
"""
Create Belle Nuit static test charts without ON/OFF pattern
"""

import subprocess
import os

def common_video_params(format_type):
    """Return common video parameters based on format"""
    if format_type.upper() == "PAL":
        return {
            'width': 720,
            'height': 576,
            'framerate': "25"
        }
    else:  # NTSC
        return {
            'width': 720,
            'height': 480,
            'framerate': "29.97"
        }

def create_static_chart(output_file, test_pattern, format_type="PAL", duration_minutes=200):
    """
    Create a static test chart video (Belle Nuit) with continuous 1kHz tone
    
    Args:
        output_file: Output video filename
        test_pattern: Path to test pattern image
        format_type: "PAL" or "NTSC"
        duration_minutes: Duration in minutes (default: 200 for E-180 tapes)
    """
    
    params = common_video_params(format_type)
    duration_seconds = duration_minutes * 60
    
    print(f"Creating {format_type} Belle Nuit chart...")
    print(f"Duration: {duration_minutes} minutes ({duration_seconds/3600:.1f} hours)")
    print(f"Audio: Continuous 1kHz tone")
    print(f"Video: Static test chart")
    
    # FFmpeg command to create static chart video with audio
    ffmpeg_cmd = [
        "ffmpeg", "-y",  # Overwrite output
        
        # Video input (black background)
        "-f", "lavfi", "-i", f"color=black:size={params['width']}x{params['height']}:rate={params['framerate']}:duration={duration_seconds}",
        
        # Test pattern overlay
        "-i", test_pattern,
        
        # Audio input (continuous 1kHz tone with reduced volume)
        "-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=48000:duration={duration_seconds}",
        
        # Video filter: overlay test chart statically
        # Audio filter: reduce volume to avoid clipping
        "-filter_complex", f"[0][1]overlay[v];[2:a]volume=0.5[a]",
        
        # Map streams
        "-map", "[v]",  # Video
        "-map", "[a]",  # Audio with reduced volume
        
        # Encoding settings
        "-c:v", "libx264",
        "-c:a", "pcm_s16le",  # PCM audio
        "-r", params['framerate'],
        
        # Output
        output_file
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f" Created: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f" Failed to create video: {e}")

def main():
    # Get the script directory and project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Paths
    pal_pattern = os.path.join(project_root, "media", "Test Patterns", "testchartpal.tif")
    ntsc_pattern = os.path.join(project_root, "media", "Test Patterns", "testchartntsc.tif")
    pal_output = os.path.join(project_root, "media", "pal_belle_nuit.mp4")
    ntsc_output = os.path.join(project_root, "media", "ntsc_belle_nuit.mp4")
    
    # Create PAL version (200 minutes for E-180 tapes)
    create_static_chart(pal_output, pal_pattern, "PAL", 200)
    
    # Create NTSC version (200 minutes for E-180 tapes)
    create_static_chart(ntsc_output, ntsc_pattern, "NTSC", 200)
    
    print("\n Static test videos created successfully!")
    print("Files saved to media/ folder")

if __name__ == "__main__":
    main()
