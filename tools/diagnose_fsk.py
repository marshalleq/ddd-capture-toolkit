#!/usr/bin/env python3
"""
Simple FSK Diagnostic Script

Extracts the timecode audio from the MP4 and analyzes FSK frame detection.
"""

import sys
import os
import subprocess
import tempfile
import numpy as np
from scipy.io import wavfile

# Add the timecode generator directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'timecode-generator'))

from vhs_timecode_robust import VHSTimecodeRobust

def extract_timecode_audio(mp4_file):
    """Extract the timecode section audio from MP4"""
    
    # Create temporary file for audio extraction
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
        temp_audio_path = temp_audio.name
    
    # Extract audio from 4s to 34s (timecode section)
    cmd = [
        'ffmpeg', '-y', '-v', 'quiet',
        '-i', mp4_file,
        '-ss', '4.0',  # Start at 4 seconds
        '-t', '30.0',  # Duration 30 seconds
        '-c:a', 'pcm_s16le',  # PCM format
        temp_audio_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Extracted timecode audio to: {temp_audio_path}")
        return temp_audio_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to extract audio: {e}")
        return None

def analyze_fsk_detection(audio_file):
    """Analyze FSK detection in the audio file"""
    
    print("FSK Detection Analysis")
    print("=" * 40)
    
    # Load audio
    sample_rate, audio_data = wavfile.read(audio_file)
    print(f"Audio: {len(audio_data)} samples at {sample_rate}Hz")
    print(f"Duration: {len(audio_data)/sample_rate:.2f}s")
    
    # Initialize FSK decoder
    decoder = VHSTimecodeRobust(format_type='PAL')
    
    print(f"\nFSK Parameters:")
    print(f"  Samples per frame: {decoder.samples_per_frame}")
    print(f"  Samples per bit: {decoder.samples_per_bit}")
    print(f"  Search step: {decoder.samples_per_frame // 8}")
    print(f"  Expected frames (30s @ 25fps): {30 * 25}")
    
    # Decode FSK frames
    print(f"\nDecoding FSK...")
    decoded_frames = decoder.decode_robust_fsk_audio(audio_data)
    print(f"Detected {len(decoded_frames)} FSK frames")
    
    if len(decoded_frames) == 0:
        print("❌ No FSK frames detected!")
        return
    
    # Analyze detected frames
    print(f"\nDetected Frames Analysis:")
    frame_ids = []
    for i, (sample_pos, frame_id, confidence) in enumerate(decoded_frames[:10]):
        time_pos = sample_pos / sample_rate
        print(f"  Frame {i+1}: Pos {sample_pos} ({time_pos:.3f}s), ID {frame_id}, Conf {confidence:.3f}")
        frame_ids.append(frame_id)
    
    if len(decoded_frames) > 10:
        print(f"  ... and {len(decoded_frames) - 10} more frames")
    
    # Check frame ID sequence
    print(f"\nFrame ID Analysis:")
    print(f"  Frame IDs: {frame_ids[:10]}")
    print(f"  Min frame ID: {min(fid for _, fid, _ in decoded_frames)}")
    print(f"  Max frame ID: {max(fid for _, fid, _ in decoded_frames)}")
    
    # Check timing distribution
    positions = [pos / sample_rate for pos, _, _ in decoded_frames]
    if len(positions) > 1:
        intervals = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
        print(f"  Average interval: {np.mean(intervals):.3f}s")
        print(f"  Expected interval: {1/25:.3f}s (40ms @ 25fps)")

def main():
    # Check if MP4 file exists
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
        print(f"MP4 file not found. Set TEST_MP4_FILE environment variable or place file in expected location.")
        return 1
    
    if not os.path.exists(mp4_file):
        print(f"MP4 file not found: {mp4_file}")
        return 1
    
    print(f"Analyzing MP4: {os.path.basename(mp4_file)}")
    
    # Extract timecode audio
    audio_file = extract_timecode_audio(mp4_file)
    if audio_file is None:
        return 1
    
    try:
        # Analyze FSK detection
        analyze_fsk_detection(audio_file)
    finally:
        # Cleanup temporary file
        if os.path.exists(audio_file):
            os.unlink(audio_file)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
