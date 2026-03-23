#!/usr/bin/env python3
"""
Analyze FSK Frame ID Distribution

This script examines the detected frame IDs to understand the pattern
of detections and identify issues with the FSK decoder.
"""

import sys
import os
import subprocess
import tempfile
import numpy as np
from scipy.io import wavfile
from collections import Counter

# Add the timecode generator directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'timecode-generator'))

from vhs_timecode_robust import VHSTimecodeRobust

def analyze_frame_ids():
    """Analyze frame ID distribution in the MP4 timecode section"""
    
    # Try to find test MP4 file in various locations
    possible_mp4_files = [
        os.environ.get('TEST_MP4_FILE'),
        os.path.join(os.path.dirname(__file__), '..', 'media', 'mp4', 'vhs_pattern_pal_10cycles_35s.mp4'),
        os.path.expanduser('~/test_pattern.mp4')
    ]
    
    mp4_file = None
    for path in possible_mp4_files:
        if path and os.path.exists(path):
            mp4_file = path
            break
    
    if not mp4_file:
        print("No test MP4 file found. Set TEST_MP4_FILE environment variable.")
        return
    
    # Extract timecode audio
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
        temp_audio_path = temp_audio.name
    
    cmd = ['ffmpeg', '-y', '-v', 'quiet', '-i', mp4_file, '-ss', '4.0', '-t', '30.0', '-c:a', 'pcm_s16le', temp_audio_path]
    
    try:
        subprocess.run(cmd, check=True)
        sample_rate, audio_data = wavfile.read(temp_audio_path)
        
        # Decode FSK
        decoder = VHSTimecodeRobust(format_type='PAL')
        decoded_frames = decoder.decode_robust_fsk_audio(audio_data)
        
        print(f"Decoded {len(decoded_frames)} FSK frames from 30s audio")
        print(f"Expected: 750 frames (30s × 25fps)")
        
        # Analyze frame ID distribution
        frame_ids = [frame_id for _, frame_id, _ in decoded_frames]
        frame_id_counts = Counter(frame_ids)
        
        print(f"\nFrame ID Statistics:")
        print(f"  Unique frame IDs: {len(frame_id_counts)}")
        print(f"  Min frame ID: {min(frame_ids)}")
        print(f"  Max frame ID: {max(frame_ids)}")
        
        # Show most common frame IDs
        print(f"\nMost frequently detected frame IDs:")
        for frame_id, count in frame_id_counts.most_common(10):
            print(f"  Frame ID {frame_id}: {count} detections")
        
        # Check for reasonable frame ID range (should be 0-749)
        valid_ids = [fid for fid in frame_ids if 0 <= fid <= 749]
        invalid_ids = [fid for fid in frame_ids if not (0 <= fid <= 749)]
        
        print(f"\nFrame ID Range Analysis:")
        print(f"  Valid frame IDs (0-749): {len(valid_ids)}")
        print(f"  Invalid frame IDs: {len(invalid_ids)}")
        
        if invalid_ids:
            print(f"  Sample invalid IDs: {sorted(set(invalid_ids))[:10]}")
        
        # Check temporal distribution
        positions = [pos / sample_rate for pos, _, _ in decoded_frames]
        frame_ids_by_time = [(pos, fid) for pos, fid in zip(positions, frame_ids)]
        frame_ids_by_time.sort()
        
        print(f"\nTemporal Distribution (first 20 detections):")
        for i, (time_pos, frame_id) in enumerate(frame_ids_by_time[:20]):
            expected_frame = int(time_pos * 25)  # Expected frame based on time
            print(f"  {time_pos:.3f}s: Frame ID {frame_id} (expected ~{expected_frame})")
        
    finally:
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)

if __name__ == "__main__":
    analyze_frame_ids()
