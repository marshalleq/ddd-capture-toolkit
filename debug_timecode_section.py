#!/usr/bin/env python3
"""
Debug script to test FSK decoding on just the timecode section
"""

import os
import sys
import subprocess
import tempfile
import scipy.io.wavfile as wavfile

# Add the timecode generator directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'tools/timecode-generator'))

from vhs_timecode_robust import VHSTimecodeRobust

def main():
    mp4_file = "media/mp4/vhs_pattern_pal_10cycles_35s.mp4"
    
    if not os.path.exists(mp4_file):
        print(f"MP4 file not found: {mp4_file}")
        sys.exit(1)
    
    # Parameters matching the validator
    timecode_start_time = 4.0
    timecode_duration = 30.0
    
    with tempfile.TemporaryDirectory(prefix='debug_timecode_') as temp_dir:
        # Extract full audio first
        full_audio_path = os.path.join(temp_dir, 'full_audio.wav')
        cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-i', mp4_file,
            '-c:a', 'copy', '-vn', full_audio_path
        ]
        subprocess.run(cmd, check=True)
        
        # Load full audio and test
        print("=== TESTING FULL AUDIO ===")
        sample_rate, full_audio = wavfile.read(full_audio_path)
        print(f"Full audio: {len(full_audio)} samples at {sample_rate}Hz")
        print(f"Full duration: {len(full_audio)/sample_rate:.2f}s")
        
        decoder = VHSTimecodeRobust(format_type='PAL')
        full_decoded = decoder.decode_fsk_audio(full_audio, strict=False)
        print(f"Full audio decode result: {len(full_decoded)} frames")
        
        # Extract only the timecode section (like the validator does)
        timecode_audio_path = os.path.join(temp_dir, 'timecode_only.wav')
        cmd = [
            'ffmpeg', '-y', '-v', 'quiet',
            '-i', full_audio_path,
            '-ss', str(timecode_start_time),
            '-t', str(timecode_duration),
            '-c:a', 'copy',
            timecode_audio_path
        ]
        subprocess.run(cmd, check=True)
        
        # Load and test timecode section
        print("\n=== TESTING TIMECODE SECTION ONLY ===")
        sample_rate, timecode_audio = wavfile.read(timecode_audio_path)
        print(f"Timecode audio: {len(timecode_audio)} samples at {sample_rate}Hz")
        print(f"Timecode duration: {len(timecode_audio)/sample_rate:.2f}s")
        
        timecode_decoded = decoder.decode_fsk_audio(timecode_audio, strict=False)
        print(f"Timecode section decode result: {len(timecode_decoded)} frames")
        
        if len(timecode_decoded) > 0:
            print("\nFirst few decoded frames from timecode section:")
            for i, (sample_pos, frame_id, confidence) in enumerate(timecode_decoded[:10]):
                print(f"  Frame {i}: sample={sample_pos}, id={frame_id}, conf={confidence}")
        
        # Compare the two approaches
        print(f"\n=== COMPARISON ===")
        print(f"Full audio frames decoded: {len(full_decoded)}")
        print(f"Timecode section frames decoded: {len(timecode_decoded)}")
        
        if len(full_decoded) > 0 and len(timecode_decoded) > 0:
            print("\nFrame ID comparison (first 10):")
            full_ids = [frame_id for _, frame_id, _ in full_decoded]
            timecode_ids = [frame_id for _, frame_id, _ in timecode_decoded]
            
            print("Full audio frame IDs:", full_ids[:10])
            print("Timecode section frame IDs:", timecode_ids[:10])

if __name__ == "__main__":
    main()
