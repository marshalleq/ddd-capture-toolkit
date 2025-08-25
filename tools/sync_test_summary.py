#!/usr/bin/env python3

import subprocess
import os
import json

def get_file_info(filename):
    """
    Get detailed info about a video file using ffprobe
    """
    if not os.path.exists(filename):
        return None
    
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", 
        "-show_format", "-show_streams", filename
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None

def format_duration(seconds):
    """
    Convert seconds to human-readable format
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def format_size(bytes_size):
    """
    Convert bytes to human-readable format
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def main():
    print("DdD Sync Test Files Summary")
    print("=" * 60)
    
    # Get the correct path regardless of where script is run from
    script_dir = os.path.dirname(os.path.abspath(__file__))
    media_dir = os.path.join(os.path.dirname(script_dir), 'media')
    mp4_dir = os.path.join(media_dir, 'mp4')
    
    test_files = [
        {
            "name": os.path.join(mp4_dir, "sync_test_10s.mp4"), 
            "description": "10-second verification test"
        },
        {
            "name": os.path.join(mp4_dir, "pal_sync_test_1hour.mp4"), 
            "description": "PAL format 1-hour sync test"
        },
        {
            "name": os.path.join(mp4_dir, "ntsc_sync_test_1hour.mp4"), 
            "description": "NTSC format 1-hour sync test"
        },
        {
            "name": os.path.join(mp4_dir, "pal_sync_test_1hour_fixed.mp4"), 
            "description": "PAL format 1-hour sync test (previous version)"
        }
    ]
    
    found_files = 0
    
    for file_info in test_files:
        filename = file_info["name"]
        description = file_info["description"]
        
        print(f"\n {os.path.basename(filename)}")
        print(f"   {description}")
        
        if not os.path.exists(filename):
            print("    File not found")
            continue
            
        found_files += 1
        file_size = os.path.getsize(filename)
        print(f"   📁 Size: {format_size(file_size)}")
        
        # Analyze MP4 files with ffprobe
        probe_info = get_file_info(filename)
        if probe_info:
            format_info = probe_info.get('format', {})
            duration = float(format_info.get('duration', 0))
            print(f"   ⏱  Duration: {format_duration(duration)}")
            
            # Find video and audio streams
            video_stream = None
            audio_stream = None
            
            for stream in probe_info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                elif stream.get('codec_type') == 'audio':
                    audio_stream = stream
            
            if video_stream:
                width = video_stream.get('width', 'Unknown')
                height = video_stream.get('height', 'Unknown')
                fps = video_stream.get('r_frame_rate', 'Unknown')
                if fps != 'Unknown' and '/' in fps:
                    # Convert fraction to decimal
                    try:
                        num, den = map(float, fps.split('/'))
                        fps = f"{num/den:.2f}"
                    except:
                        pass
                print(f"   🎥 Video: {width}x{height} @ {fps} fps")
            
            if audio_stream:
                sample_rate = audio_stream.get('sample_rate', 'Unknown')
                channels = audio_stream.get('channels', 'Unknown')
                print(f"   🔊 Audio: {sample_rate} Hz, {channels} channel(s)")
        
        print("    Ready to use")
    
    print(f"\n{"=" * 60}")
    print(f"Summary: {found_files} sync test files available")
    
    print("\n TEST PATTERN DETAILS:")
    print("   • Video: Test pattern visible for 1s, black screen for 1s (repeating)")
    print("   • Audio: 1kHz sine tone for 1s, silence for 1s (repeating)")
    print("   • Perfect synchronization between video and audio")
    
    print("\n📋 USAGE:")
    print("   1. Use sync_test_10s.mp4 for quick verification")
    print("   2. Use PAL or NTSC 1-hour versions for full testing")
    print("   3. Import into your video editing software")
    print("   4. Use for sync alignment with captured footage")
    
    print("\n GENERATED WITH:")
    print("   • SOX: Audio tone generation")
    print("   • FFmpeg: Video generation and synchronization")
    print("   • Test patterns: testchartpal.tif / testchartntsc.tif")

if __name__ == "__main__":
    main()
