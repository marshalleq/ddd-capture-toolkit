#!/usr/bin/env python3

import subprocess
import os
import tempfile
import sys
import struct
import math

def extract_audio_segment(video_or_audio_file, start_seconds=10, duration_seconds=60):
    """
    Extract a segment of audio from video or audio file for analysis
    """
    temp_wav = tempfile.mktemp(suffix='.wav')
    
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-v', 'quiet',
        '-i', video_or_audio_file,
        '-ss', str(start_seconds),
        '-t', str(duration_seconds),
        '-vn',  # No video
        '-acodec', 'pcm_s16le',
        '-ar', '48000',
        '-ac', '1',  # Mono
        temp_wav
    ]
    
    result = subprocess.run(ffmpeg_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"Error extracting audio: {result.stderr.decode()}")
        return None
    
    return temp_wav

def read_wav_file(wav_file):
    """
    Simple WAV file reader (16-bit PCM only)
    """
    try:
        with open(wav_file, 'rb') as f:
            # Read and parse WAV header
            riff = f.read(4)
            if riff != b'RIFF':
                print("Not a valid WAV file")
                return None
            
            file_size = struct.unpack('<L', f.read(4))[0]
            wave = f.read(4)
            if wave != b'WAVE':
                print("Not a valid WAV file")
                return None
            
            # Find data chunk
            while True:
                chunk_id = f.read(4)
                if not chunk_id:
                    break
                chunk_size = struct.unpack('<L', f.read(4))[0]
                
                if chunk_id == b'data':
                    # Found data chunk
                    data = f.read(chunk_size)
                    break
                else:
                    # Skip this chunk
                    f.seek(chunk_size, 1)
            else:
                print("No data chunk found")
                return None
            
        # Convert bytes to 16-bit signed integers
        samples = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                sample = struct.unpack('<h', data[i:i+2])[0]  # Little-endian 16-bit
                samples.append(sample)
        
        print(f"Read {len(samples)} audio samples")
        return samples
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        return None

def detect_tone_energy(samples, sample_rate=48000, window_size_ms=100):
    """
    Detect audio energy levels in sliding windows
    """
    window_samples = int(sample_rate * window_size_ms / 1000)
    hop_samples = window_samples // 2  # 50% overlap
    
    energy_levels = []
    times = []
    
    for i in range(0, len(samples) - window_samples, hop_samples):
        window = samples[i:i + window_samples]
        
        # Calculate RMS energy
        rms = math.sqrt(sum(s * s for s in window) / len(window))
        energy_levels.append(rms)
        times.append(i / sample_rate)
    
    return energy_levels, times

def find_tone_bursts(energy_levels, times, threshold_factor=0.3):
    """
    Find tone bursts based on energy levels
    """
    if not energy_levels:
        return []
    
    max_energy = max(energy_levels)
    threshold = max_energy * threshold_factor
    
    burst_starts = []
    in_burst = False
    
    for i, energy in enumerate(energy_levels):
        if energy > threshold and not in_burst:
            burst_starts.append(times[i])
            in_burst = True
        elif energy <= threshold and in_burst:
            in_burst = False
    
    return burst_starts

def analyze_simple_timing(capture_file):
    """
    Analyze captured audio using simple energy detection
    """
    print(f"Analyzing capture file: {capture_file}")
    
    if not os.path.exists(capture_file):
        print(f"ERROR: File not found: {capture_file}")
        return None
    
    # Extract audio segment for analysis
    # For short files, start from the beginning
    start_time = 0 if 'sync_test_10s' in capture_file else 10
    duration = 10 if 'sync_test_10s' in capture_file else 60
    
    temp_wav = extract_audio_segment(capture_file, start_seconds=start_time, duration_seconds=duration)
    if not temp_wav:
        return None
    
    try:
        # Read audio data
        samples = read_wav_file(temp_wav)
        if not samples:
            return None
        
        print(f"Analyzing {len(samples)/48000:.1f}s of audio...")
        
        # Detect energy levels
        energy_levels, times = detect_tone_energy(samples)
        
        # Find tone bursts
        burst_starts = find_tone_bursts(energy_levels, times)
        
        print(f"Detected {len(burst_starts)} potential tone bursts")
        
        if len(burst_starts) >= 2:
            # Calculate intervals between bursts
            intervals = [burst_starts[i+1] - burst_starts[i] for i in range(len(burst_starts)-1)]
            avg_interval = sum(intervals) / len(intervals)
            
            print(f"Average interval between bursts: {avg_interval:.3f}s")
            print(f"Expected interval: 2.000s")
            print(f"First burst at: {burst_starts[0]:.3f}s")
            
            # Simple offset calculation
            # The first burst should ideally start at t=0 (or a multiple of 2s)
            expected_interval = 2.0
            offset = burst_starts[0] % expected_interval
            
            # If offset is > 1s, it's probably meant to be negative
            if offset > expected_interval / 2:
                offset -= expected_interval
            
            print(f"\n=== TIMING ANALYSIS RESULTS ===")
            print(f"Detected timing offset: {offset:.3f}s ({offset*1000:.0f}ms)")
            
            if abs(offset) < 0.01:  # Less than 10ms
                print(" Timing is very good (< 10ms offset)")
            elif abs(offset) < 0.05:  # Less than 50ms
                print(" Timing is acceptable (< 50ms offset)")
            else:
                print(" Significant timing offset detected")
            
            return offset
        else:
            print(" Could not detect tone pattern reliably")
            print("Make sure the test pattern was recorded with adequate volume")
            return None
            
    finally:
        if temp_wav and os.path.exists(temp_wav):
            os.remove(temp_wav)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 simple_audio_analyzer.py <capture_file>")
        print("Example: python3 simple_audio_analyzer.py av_alignment_capture.flac")
        sys.exit(1)
    
    capture_file = sys.argv[1]
    offset = analyze_simple_timing(capture_file)
    
    if offset is not None:
        print(f"\nRecommended delay adjustment: {-offset:.3f}s")
        if offset > 0:
            print("Audio is ahead of video - increase delay")
        else:
            print("Audio is behind video - decrease delay")
    else:
        print("\nCould not determine timing offset")
        print("This could mean:")
        print("- Test pattern was not recorded or is too quiet")
        print("- Audio quality is too poor for automatic analysis")
        print("- Manual alignment may be needed")

if __name__ == "__main__":
    main()
